from dataclasses import dataclass, field
from typing import Any
import ctypes
from ctypes import wintypes
import comtypes

from comtypes import COMError
from comtypes import HRESULT, GUID

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
oleacc = ctypes.OleDLL("oleacc.dll")

import logging

logging.getLogger("comtypes").setLevel(logging.WARNING)

"""
 Generate or load the Accessibility wrapper before importing from it.
 comtypes.gen is dynamical generated, if using generated comtypes.gen
 using nuitka will rasied ImportError: Typelib different than module.
 gen_dir = None prevents wrappers generated at runtime from being written to disk
 Nuitka compile need nofollow-import-to=comtypes.gen.
"""
import comtypes.client

comtypes.client.gen_dir = None
# Workaround for set gen_dir = None.
if not comtypes.gen.__path__:
    comtypes.gen.__path__ = [""]

accessibility = comtypes.client.GetModule("oleacc.dll")
IAccessible = accessibility.IAccessible

# # Imports IAccessible from the generated wrapper. It does not generate that wrapper.
# comtypes.client.GetModule("oleacc.dll")
# from comtypes.gen.Accessibility import IAccessible

# comtypes.client.GetModule() generates Python wrapper modules on demand

# from a COM type library and makes them importable under comtypes.gen
# python -c "from comtypes.client import GetModule; GetModule('oleacc.dll')"

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------
GW_HWNDNEXT = 2
GA_ROOT = 2
DWMWA_CLOAKED = 14
OBJID_CLIENT = 0xFFFFFFFC
VT_I4 = 3
VT_DISPATCH = 9
CHILDID_SELF = 0


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


# ---------------------------------------------------------------------------
# Load Microsoft Active Accessibility interfaces
# ---------------------------------------------------------------------------
oleacc.AccessibleObjectFromWindow.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.POINTER(comtypes.GUID),
    ctypes.POINTER(ctypes.POINTER(IAccessible)),
]
oleacc.AccessibleObjectFromWindow.restype = HRESULT
Rect = tuple[int, int, int, int]


@dataclass
class AccessibleElement:
    accessible: Any
    child_id: int
    rect: tuple[int, int, int, int]
    name: str | None = None
    role: int | None = None
    state: int | None = None


@dataclass
class AccHitElement:
    acc: object
    child_id: int
    rect: Rect
    original_rect: Rect | None = None
    clip_rect: Rect | None = None
    name: str | None = None
    role: object | None = None


@dataclass
class AccHitPath:
    elements: list[AccHitElement] = field(default_factory=list)
    index: int = -1

    @property
    def current(self) -> AccHitElement | None:
        if not self.elements:
            return None
        return self.elements[self.index]

    @property
    def rect(self) -> Rect | None:
        element = self.current
        return element.rect if element else None

    def deepest(self) -> AccHitElement | None:
        if not self.elements:
            return None
        self.index = len(self.elements) - 1
        return self.current

    def parent(self) -> AccHitElement | None:
        """Move one level toward HWND/root."""
        if not self.elements:
            return None
        self.index = max(0, self.index - 1)
        return self.current

    def child(self) -> AccHitElement | None:
        """Move one level toward deepest element."""
        if not self.elements:
            return None
        self.index = min(
            len(self.elements) - 1,
            self.index + 1,
        )
        return self.current


def make_hit_element(acc, child_id, clip_rect=None) -> AccHitElement | None:
    info = get_accessible_info(acc, child_id)
    if info is None:
        return None
    rect = info.rect
    if rect is None:
        return None
    original_rect = rect
    # Clip against current ancestor boundaries
    if clip_rect is not None:
        left = max(rect[0], clip_rect[0])
        top = max(rect[1], clip_rect[1])
        right = min(rect[2], clip_rect[2])
        bottom = min(rect[3], clip_rect[3])
        if right <= left or bottom <= top:
            return None
        rect = (left, top, right, bottom)
    return AccHitElement(
        acc=acc,
        child_id=child_id,
        rect=rect,
        original_rect=original_rect,
        clip_rect=clip_rect,
        name=info.name,
        role=info.role,
    )


# ---------------------------------------------------------------------------
# Get Child info accName/Role/State
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Accessible element info
# ---------------------------------------------------------------------------
def get_accessible_info(acc, child_id) -> AccessibleElement | None:
    """
    Read accessibility information.
    rect:
        (left, top, right, bottom)
    All coordinates are global physical screen coordinates.
    """
    try:
        left, top, width, height = acc.accLocation(child_id)
    except (COMError, OSError, TypeError):
        return None
    left = int(left)
    top = int(top)
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        return None
    try:
        name = acc.accName(child_id)
    except (COMError, OSError, TypeError):
        name = None
    try:
        role = acc.accRole(child_id)
    except (COMError, OSError, TypeError):
        role = None
    try:
        state = acc.accState(child_id)
    except (COMError, OSError, TypeError):
        state = None
    return AccessibleElement(
        accessible=acc,
        child_id=child_id,
        rect=(left, top, left + width, top + height),
        name=name,
        role=role,
        state=state,
    )


def acc_hit_test_deep(root_hwnd, screen_x, screen_y, max_depth=30):
    acc = accessible_from_hwnd(root_hwnd)
    if acc is None:
        return None
    path = AccHitPath()
    clip_rect = None
    for _ in range(max_depth):
        # ====================================================
        # Current accessible object boundary
        # ====================================================
        try:
            left, top, width, height = acc.accLocation(CHILDID_SELF)
            left = int(left)
            top = int(top)
            right = left + int(width)
            bottom = top + int(height)
            if right > left and bottom > top:
                current_rect = (left, top, right, bottom)
                if clip_rect is None:
                    clip_rect = current_rect
                else:
                    clip_rect = (
                        max(clip_rect[0], left),
                        max(clip_rect[1], top),
                        min(clip_rect[2], right),
                        min(clip_rect[3], bottom),
                    )
                    if clip_rect[2] <= clip_rect[0] or clip_rect[3] <= clip_rect[1]:
                        break
        except (COMError, OSError, TypeError):
            pass

        # ====================================================
        # Add current level to path
        # ====================================================
        element = make_hit_element(acc, CHILDID_SELF, clip_rect)
        append_hit_element(path, element)

        # ====================================================
        # Hit-test next child
        # ====================================================
        try:
            hit = acc.accHitTest(int(screen_x), int(screen_y))
        except (COMError, OSError):
            break
        if hit is None:
            break
        # ====================================================
        # Child ID
        # ====================================================
        if isinstance(hit, int):
            child_id = hit
            if child_id == CHILDID_SELF:
                break
            try:
                child = acc.accChild(child_id)
            except (COMError, OSError):
                child = None
            # --------------------------------------------
            # Simple MSAA child
            # --------------------------------------------
            if child is None:
                element = make_hit_element(acc, child_id, clip_rect)
                append_hit_element(path, element)
                break

            # --------------------------------------------
            # Try to promote to IAccessible
            # --------------------------------------------
            try:
                child_acc = child.QueryInterface(IAccessible)
            except (COMError, AttributeError, TypeError, ValueError):
                child_acc = None
            if child_acc is None:
                element = make_hit_element(acc, child_id, clip_rect)
                append_hit_element(path, element)
                break
            acc = child_acc
            continue

        # ====================================================
        # Full IAccessible child
        # ====================================================
        try:
            next_acc = hit.QueryInterface(IAccessible)

        except (COMError, AttributeError, TypeError):
            break
        if next_acc is None:
            break
        acc = next_acc
    # ========================================================
    # Finalize
    # ========================================================
    if not path.elements:
        return None
    path.index = len(path.elements) - 1
    return path


def append_hit_element(path: AccHitPath, element) -> bool:
    """
    Append valid Hit element only.
    """
    if element is None:
        return False
    rect = element.rect
    if rect is None:
        return False
    left, top, right, bottom = rect
    # Empty
    if right <= left or bottom <= top:
        return False
    if path.elements:
        parent_rect = path.elements[-1].rect
        if not rects_intersect(parent_rect, rect):
            return False
        # if parent_rect is not None:
        #     pl, pt, pr, pb = parent_rect
        #     # Child outside parent
        #     if left < pl or top < pt or right > pr or bottom > pb:
        #         return False
    # Same rectangle already represented in hierarchy
    if any(e.rect == rect for e in path.elements):
        return False
    path.elements.append(element)
    return True


def rects_intersect(a, b):
    al, at, ar, ab = a
    bl, bt, br, bb = b
    return max(al, bl) < min(ar, br) and max(at, bt) < min(ab, bb)


# ---------------------------------------------------------------------------
# Obtain root IAccessible
# ---------------------------------------------------------------------------
def accessible_from_hwnd(hwnd):
    """
    Return the IAccessible object for a window's client area.
    """
    accessible = ctypes.POINTER(IAccessible)()
    iid = IAccessible._iid_
    hr = oleacc.AccessibleObjectFromWindow(
        hwnd, OBJID_CLIENT, ctypes.byref(iid), ctypes.byref(accessible)
    )
    if hr < 0 or not accessible:
        return None
    return accessible


# ---------------------------------------------------------------------------
# Complete function
# ---------------------------------------------------------------------------
def get_deepest_element_at_point(overlay_hwnd, x, y):
    root_hwnd = root_hwnd_below_overlay_at_point(
        overlay_hwnd,
        x,
        y,
    )
    if not root_hwnd:
        return None
    hit_path = acc_hit_test_deep(root_hwnd, x, y)
    if hit_path is None:
        return None
    # Deepest hit
    return hit_path


# ---------------------------------------------------------------------------
# Find top-level window below overlay without WindowFromPoint
# ---------------------------------------------------------------------------
def root_hwnd_below_overlay_at_point(overlay_hwnd, x, y):
    desktop_hwnd = user32.GetDesktopWindow()
    shell_hwnd = user32.GetShellWindow()
    overlay_pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(overlay_hwnd, ctypes.byref(overlay_pid))
    hwnd = user32.GetWindow(overlay_hwnd, GW_HWNDNEXT)
    while hwnd:
        if (
            hwnd != overlay_hwnd
            and hwnd != desktop_hwnd
            and hwnd != shell_hwnd
            and user32.IsWindow(hwnd)
            and user32.IsWindowVisible(hwnd)
            and user32.IsWindowEnabled(hwnd)
        ):
            hwnd_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(hwnd_pid))
            # Skip the overlay and other helper windows from this process.
            if hwnd_pid.value != overlay_pid.value:
                cloaked = wintypes.DWORD()
                hr = dwmapi.DwmGetWindowAttribute(
                    hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
                )
                if hr != 0 or not cloaked.value:
                    rect = RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                        if (
                            rect.right > rect.left
                            and rect.bottom > rect.top
                            and rect.left <= x < rect.right
                            and rect.top <= y < rect.bottom
                        ):
                            return hwnd
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
    return 0


# def _acc_hit_test_deep(root_hwnd, screen_x, screen_y, max_depth=30):
#     """
#     Walk the MSAA hierarchy at the given physical screen point.

#     Returns:
#         AccHitPath | None

#     Notes:
#         - Element rectangles come directly from accLocation().
#         - No progressive parent clipping is applied.
#         - Filtering/duplicate removal is handled by append_hit_element().
#         - A rejected element does NOT stop traversal.
#     """
#     acc = accessible_from_hwnd(root_hwnd)

#     if acc is None:
#         return None

#     path = AccHitPath()

#     for _ in range(max_depth):

#         # ====================================================
#         # 1. Add current accessible object
#         # ====================================================
#         element = make_hit_element(
#             acc,
#             CHILDID_SELF,
#             clip_rect=None,
#         )

#         append_hit_element(path, element)

#         # ====================================================
#         # 2. Hit-test current accessible object
#         # ====================================================
#         try:
#             hit = acc.accHitTest(int(screen_x), int(screen_y))

#         except (COMError, OSError):
#             break

#         if hit is None:
#             break

#         # ====================================================
#         # 3. Simple child ID
#         # ====================================================
#         if isinstance(hit, int):
#             child_id = hit

#             # Current accessible object is the deepest result.
#             if child_id == CHILDID_SELF:
#                 break

#             # ------------------------------------------------
#             # Try child ID -> IAccessible
#             # ------------------------------------------------
#             try:
#                 child = acc.accChild(child_id)

#             except (COMError, OSError):
#                 child = None

#             if child is not None:
#                 try:
#                     child_acc = child.QueryInterface(IAccessible)

#                 except (COMError, AttributeError, TypeError):
#                     child_acc = None

#                 # Full accessible child:
#                 # continue walking down from that object.
#                 if child_acc is not None:
#                     acc = child_acc
#                     continue

#             # ------------------------------------------------
#             # Simple MSAA child
#             #
#             # No independent IAccessible object is available.
#             # Add the child using its child ID and stop here.
#             # ------------------------------------------------
#             element = make_hit_element(
#                 acc,
#                 child_id,
#                 clip_rect=None,
#             )

#             append_hit_element(
#                 path,
#                 element,
#             )

#             break

#         # ====================================================
#         # 4. Full IAccessible child returned directly
#         # ====================================================
#         try:
#             next_acc = hit.QueryInterface(IAccessible)

#         except (COMError, AttributeError, TypeError):
#             break

#         if next_acc is None:
#             break

#         acc = next_acc

#     # ========================================================
#     # 5. Finalize
#     # ========================================================
#     if not path.elements:
#         return None

#     path.index = len(path.elements) - 1
#     return path
