"""
Grab view overlay for snip selection.

Re-use in the whole app life cycle.
"""

import time
import sys
import ctypes
from ctypes import wintypes

from PyQt6.QtCore import QPoint, QTimer, Qt, QRect, QRectF, pyqtSignal
from PyQt6.QtGui import QCursor, QImage, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import QApplication, QGraphicsView


from core.models import AppContext
from core.hit_testing import get_deepest_element_at_point

from .widgets.hint_panel import HintMode, ShortcutHintPanel

from .widgets.cursor_magnifier import CursorMagnifier
from .image_view import ImageView
from .scenes import GrabScene
from ui.models.tools import Tool

# -------------------------------------------------
# UI Automation setup
# -------------------------------------------------
user32 = ctypes.windll.user32


# ===================================================
SNIP_SHORTCUTS = [
    (["Enter", "Return"], "/", "Copy to clipboard"),
    ([["Ctrl", "C"], ["S"]], "+", "Copy or Save snip"),
    (["Ctrl", "A"], "+", "Select current screen"),
    ([["Right-Click"], ["R"]], "", "Reselect area"),
    (["Shift", "R"], "+", "Reuse the last selected area"),
    (["Tab"], "", "Move to the next UI element"),
    (["Esc"], "", "Cancel selection or Exit"),
    (["`", "!"], "/", "Toggle system cursor visibility"),
]

EDIT_SHORTCUTS = [
    # (["W", "A", "S", "D"], "", "Adjust selection size by 1 pixel"),
    # ([["WASD"], ["Shift", "WASD"]], "+", "Enlarge / Shrink selection 1px"),
    # (["←", "↑", "↓", "→"], "", "Move selection by 1 pixel"),
    ([["Shift"], ["←", "↑", "↓", "→"]], "", "Resize or Move selection"),
    # ([["Shift"], ["← ↑ ↓ →"]], "", "Resize / Move selection by 1 pixel"),
    (["Enter", "Return"], "/", "Copy to clipboard"),
    ([["Ctrl", "C"], ["S"]], "+", "Copy or Save snip"),
    ([["Right-Click"], ["R"]], "", "Reselect area"),
    (["Ctrl", "A"], "+", "Select current screen"),
    (["Esc"], "", "Cancel selection or Exit"),
    (["`", "!"], "/", "Toggle system cursor visibility"),
]


# ===================================================
# View port
# ===================================================
class GrabView(ImageView):
    createPinRequested = pyqtSignal(object, QPoint)

    def __init__(
        self,
        context: AppContext,
        pixmap: QPixmap | None = None,
        parent=None,
    ):
        # _, _ = capture_qt_virtual_desktop_pixmap()
        # ---------------------------------------------------
        # Init Screen grabber
        # ---------------------------------------------------
        scene = GrabScene()
        super().__init__(scene, context, parent)
        self.context = context
        self._settings = self.context.settings
        self.virtual_rect: QRect | None = None
        self.setMouseTracking(True)
        # self.viewport().setCursor(Qt.CursorShape.CrossCursor)

        # self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)

        # IMPORTANT: Magnifier exists first before conenct signal.
        self._magnifier = CursorMagnifier(self.viewport())
        self._magnifier.hide()

        # These method is grabview specific: selection rect.
        scene.selectionFinished.connect(self.on_selection_finished)
        scene.selectionCanceled.connect(self.on_selection_canceled)
        scene.selectionGeometryChanged.connect(self.on_selection_geometry_changed)
        scene.selectionMouseMoved.connect(self.update_cursor_magnifier)
        scene.cursorRequested.connect(self._set_interaction_cursor)
        scene.cursorRestoreRequested.connect(self.update_tool_cursor)
        self.hwnd = None

        # Hint panel
        self._shortcut_hint = ShortcutHintPanel(self.viewport())
        self._shortcut_hint.hide()
        self._hint_corner = None

        # ACC hit testing
        self._setup_hit_testing()

        # -------------------------------------------------
        # Local Hotkeys
        # -------------------------------------------------
        self._setup_shortcuts()
        # -------------------------------------------------
        # Initial settings.
        # -------------------------------------------------
        if self.capture_cursor_enabled is not None:
            self.set_frozen_cursor_visible(self.capture_cursor_enabled)

        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.esc_shortcut.activated.connect(
            self.close
        )  # Or your existing dismiss method

    # -------------------------------------------------
    # Properties for settings from settings manager.
    # -------------------------------------------------

    @property
    def hit_testing_enabled(self) -> bool:
        return self._settings.settings.value(
            "General/hit_testing_enabled", True, type=bool
        )

    @property
    def hint_panel_enabled(self) -> bool:
        return self._settings.settings.value(
            "General/hint_panel_enabled", True, type=bool
        )

    @property
    def cursor_magnifier_enabled(self) -> bool:
        return self._settings.settings.value(
            "General/cursor_magnifier_enabled", True, type=bool
        )

    @property
    def capture_cursor_enabled(self) -> bool:
        return self._settings.settings.value(
            "General/capture_cursor_enabled", True, type=bool
        )

    # ========================================================
    # Hit testing setup
    # ========================================================
    def _setup_hit_testing(self):
        # Setup init.
        self.current_element = None
        self.current_element_rect = QRect()  # viewport local
        self.current_element_global_rect = QRect()
        self.current_element_scene_rect = QRectF()  # viewport local

        self.uia_min_move_px = 3
        self._last_uia_point = None
        self.last_cursor_pos = None

        # Prevent concurrent or recursive UIA hit tests.
        self.hit_test_running = False
        # Do not update element highlighting while dragging.

        # Polling interval for UIA hover detection.
        self.hit_test_timer = QTimer(self)
        self.hit_test_timer.setInterval(50)
        self.hit_test_timer.timeout.connect(self.update_acc_hit_test)

        self._pending_acc_selection = None
        self._press_pos = QPoint()
        self._manual_drag_started = False
        self.manual_drag_threshold = 4

        # ACC hit-test state
        self._acc_hit_path = None
        self._acc_tab_index = None
        self._acc_tab_mode = False

        self._last_uia_point = None

    def enable_hit_testing(self):
        if not self.hit_testing_enabled:
            return
        if not self.hit_test_timer.isActive():
            self.hit_test_timer.start()

    def disable_hit_testing(self):
        if self.hit_test_timer.isActive():
            self.hit_test_timer.stop()

    # ========================================================
    # Set/Unset viewport cursor.
    # ========================================================
    def _set_interaction_cursor(self, cursor):
        """
        For selectionRect.
        """
        self.viewport().setCursor(QCursor(cursor))

    # def restore_tool_cursor(self):
    #     self.viewport().setCursor(self._cursor_for_tool(self.scene().tool))
    # ========================================================
    # Enter Edit mode
    # ========================================================
    def on_selection_finished(self):
        """
        Enter edit mode.
        """
        self.disable_hit_testing()
        self.set_hint_mode(HintMode.EDIT)
        self.show_toolbar()
        self.hide_cursor_magnifier()
        self.remember_selection()

    def on_selection_canceled(self):
        """
        On snip selection been cancelled
        """
        self.hide_cursor_magnifier()
        self.reset_for_new_snip()

    def on_selection_geometry_changed(self):
        """
        On selection geometry changed.
        """
        self.remember_selection()
        self.update_toolbar_position()

    # ========================================================
    # Setup hotkey
    # ========================================================
    def _setup_shortcuts(self):
        self._shortcut_select_screen = QShortcut(QKeySequence("Ctrl+A"), self)
        self._shortcut_select_screen.activated.connect(self.select_current_screen)
        self._shortcut_reselect = QShortcut(QKeySequence("R"), self)
        self._shortcut_reselect.activated.connect(self.restart_new_snip)
        self._shortcut_reuse = QShortcut(QKeySequence("Shift+R"), self)
        self._shortcut_reuse.activated.connect(self.reuse_last_selection)

        self._shortcut_copy_image = QShortcut(QKeySequence("ctrl+c"), self)
        self._shortcut_copy_image.activated.connect(lambda: self.copy_image(close=True))
        self.enter_shortcuts = [
            QShortcut(QKeySequence("Return"), self),
            QShortcut(QKeySequence("Enter"), self),
        ]
        for shortcut in self.enter_shortcuts:
            shortcut.activated.connect(lambda: self.copy_image(close=True))
        self._shortcut_save_image = QShortcut(QKeySequence("ctrl+s"), self)
        self._shortcut_save_image.activated.connect(self.save_image)
        self._last_snip_rect = QRectF()

        self.show_captured_cursor = True
        self.grave_shortcut = QShortcut(QKeySequence("Shift+`"), self)  # ~
        self.grave_shortcut.activated.connect(
            lambda: self.set_frozen_cursor_visible(True)
        )
        self.excl_shortcut = QShortcut(QKeySequence("Shift+1"), self)  # !
        self.excl_shortcut.activated.connect(
            lambda: self.set_frozen_cursor_visible(False)
        )

    def remember_selection(self):
        selection = self.scene().selection
        if selection is None or not selection.is_finished():
            return
        rect = selection.scene_selection_rect()
        if not rect.isEmpty():
            self._last_snip_rect = QRectF(rect)

    def select_current_screen(self):
        """
        Select entire current (cursor) screeen.
        """
        # self.restart_new_snip()
        global_pos = QCursor.pos()
        screen = QApplication.screenAt(global_pos)
        if screen is None:
            return
        # Physical screen geometry in global coordinates
        screen_global = screen.geometry()
        # --------------------------------
        # Global -> viewport
        # --------------------------------
        top_left_global = screen_global.topLeft()
        bottom_right_global = QPoint(
            screen_global.x() + screen_global.width(),
            screen_global.y() + screen_global.height(),
        )  # screen_global.bottomRight() is incorrect size.
        top_left_view = self.viewport().mapFromGlobal(top_left_global)

        bottom_right_view = self.viewport().mapFromGlobal(bottom_right_global)
        # --------------------------------
        # Viewport -> scene
        # --------------------------------
        top_left_scene = self.mapToScene(top_left_view)
        bottom_right_scene = self.mapToScene(bottom_right_view)
        rect = QRectF(top_left_scene, bottom_right_scene).normalized()
        self.reset_for_new_snip()
        self.scene().set_selection_rect(rect, finished=True)
        self.on_selection_finished()

    def reuse_last_selection(self):
        rect = QRectF(self._last_snip_rect).intersected(self.scene().sceneRect())
        if rect.isEmpty():
            return
        self.clear_current_element()
        self.scene().set_selection_rect(rect, finished=True)
        self.on_selection_finished()

    def restart_new_snip(self):
        """
        Clear current selection, and enable re-select.
        """
        self.clear_current_element()
        self.remember_selection()
        # ready for selection.

        # reset toolbar & magnifier
        self.set_hint_mode(HintMode.SNIP)
        self.hide_toolbar()
        self.hide_cursor_magnifier()
        self.enable_hit_testing()
        self.reset_for_new_snip()  # after toolbar action.

    def set_frozen_cursor_visible(self, visible: bool = False) -> None:
        scene = self.scene()
        scene.set_frozen_cursor_visible(visible)

    def render_image(self, *_) -> QImage:
        """
        Override imageview render image.
        Default render from scenen image due to no transform needed.
        """
        return self._render_scene_image()

    # =================================================
    # Cursor Magnifier
    # =================================================
    def update_cursor_magnifier(self, scene_pos, *_):
        if not self.cursor_magnifier_enabled:
            return
        if not self._magnifier.isVisible():
            self._magnifier.show()
        local_pos = self.mapFromScene(scene_pos)
        self._magnifier.update_data(local_pos, self.scene().bg_item.pixmap())

    def hide_cursor_magnifier(self):
        self._magnifier.hide()

    # =================================================
    # Hint Panel
    # =================================================
    def set_hint_mode(self, mode: HintMode):
        if not self._shortcut_hint:
            return
        if mode == HintMode.SNIP:
            shortcuts = SNIP_SHORTCUTS
        elif mode == HintMode.EDIT:
            shortcuts = EDIT_SHORTCUTS
        else:
            return
        self._shortcut_hint.set_shortcuts(shortcuts)
        self.adjust_panel_position(self._shortcut_hint, QCursor.pos())

    def adjust_panel_position(self, panel, mouse_pos: QPoint) -> None:
        if panel is None:  # or not panel.isVisible():
            return
        margin = 0
        mouse_margin = 32
        selection_margin = 8
        # Important if panel contents can change its size.
        panel.adjustSize()
        panel_size = panel.size()
        # ---------------------------------------------------------
        # Screen containing the mouse
        # ---------------------------------------------------------
        screen = QApplication.screenAt(mouse_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return
        screen_rect = screen.geometry()
        # ---------------------------------------------------------
        # Mouse exclusion area
        # ---------------------------------------------------------
        mouse_rect = QRect(
            mouse_pos.x() - mouse_margin,
            mouse_pos.y() - mouse_margin,
            mouse_margin * 2,
            mouse_margin * 2,
        )
        # ---------------------------------------------------------
        # Selection rect -> GLOBAL coordinates
        # ---------------------------------------------------------
        selection_rect = None
        selection = getattr(self.scene(), "selection", None)
        if selection is not None:
            rect = selection.scene_selection_rect()
            if not rect.isEmpty():
                top_left = self.viewport().mapToGlobal(
                    self.mapFromScene(rect.topLeft())
                )
                bottom_right = self.viewport().mapToGlobal(
                    self.mapFromScene(rect.bottomRight())
                )
                selection_rect = QRect(top_left, bottom_right).normalized()
                selection_rect.adjust(
                    -selection_margin,
                    -selection_margin,
                    selection_margin,
                    selection_margin,
                )

        has_current_position = panel.isVisible()
        if has_current_position:
            current_rect = QRect(panel.pos(), panel_size)
            current_on_screen = screen_rect.contains(current_rect)
            overlaps_mouse = current_rect.intersects(mouse_rect)
            overlaps_selection = selection_rect is not None and current_rect.intersects(
                selection_rect
            )
            # Current location is already ideal.
            if current_on_screen and not overlaps_mouse and not overlaps_selection:
                return
        else:
            # First show:
            # don't trust the initial QWidget position.
            current_rect = None
            current_on_screen = False
            overlaps_mouse = False
            overlaps_selection = False

        # ---------------------------------------------------------
        # Candidate GLOBAL positions
        # ---------------------------------------------------------
        candidates = [
            # Top-left
            QPoint(
                screen_rect.left() + margin,
                screen_rect.top() + margin,
            ),
            # Top-right
            QPoint(
                screen_rect.right() - panel_size.width() - margin + 1,
                screen_rect.top() + margin,
            ),
            # Bottom-left
            QPoint(
                screen_rect.left() + margin,
                screen_rect.bottom() - panel_size.height() - margin + 1,
            ),
            # Bottom-right
            QPoint(
                screen_rect.right() - panel_size.width() - margin + 1,
                screen_rect.bottom() - panel_size.height() - margin + 1,
            ),
        ]
        valid = []
        fallback = []
        # ---------------------------------------------------------
        # Evaluate candidates
        # ---------------------------------------------------------
        for pos in candidates:
            rect = QRect(pos, panel_size)
            # HARD RULE:
            # Never put panel under/near mouse.
            if rect.intersects(mouse_rect):
                continue
            center = rect.center()
            dx = center.x() - mouse_pos.x()
            dy = center.y() - mouse_pos.y()
            distance_sq = dx * dx + dy * dy
            candidate = (distance_sq, pos)
            # Prefer location outside selection.
            if selection_rect is not None and rect.intersects(selection_rect):
                fallback.append(candidate)
            else:
                valid.append(candidate)

        # ---------------------------------------------------------
        # Stability
        #
        # Existing panel is good enough and every better candidate
        # overlaps the selection. Keep it where it is.
        #
        # Only apply this for an ALREADY SHOWN panel.
        # ---------------------------------------------------------

        if (
            has_current_position
            and current_on_screen
            and not overlaps_mouse
            and overlaps_selection
            and not valid
        ):
            return

        # ---------------------------------------------------------
        # Prefer candidate outside selection
        # ---------------------------------------------------------
        pool = valid or fallback
        if not pool:
            return
        # ---------------------------------------------------------
        # Choose candidate farthest from mouse
        # ---------------------------------------------------------
        _, best_pos = max(pool, key=lambda candidate: candidate[0])
        # ---------------------------------------------------------
        # Qt.Tool -> move using GLOBAL position directly
        # ---------------------------------------------------------
        if panel.pos() != best_pos:
            panel.move(best_pos)
        panel.raise_()

    def show_shortcut_hint(self):
        if not self.hint_panel_enabled:
            return
        self.adjust_panel_position(self._shortcut_hint, QCursor.pos())
        self._shortcut_hint.show()
        self._shortcut_hint.raise_()

    def hide_shortcut_hint(self):
        self._shortcut_hint.hide()

    # ===========================================================
    # ACC hit testing -> Hitpath
    # ===========================================================
    def update_acc_hit_test(self):
        if self.scene().is_selecting or self.hit_test_running:
            return

        self.hit_test_running = True
        cursor = wintypes.POINT()

        try:
            # =====================================================
            # 1. Physical cursor position
            # =====================================================
            if not user32.GetCursorPos(ctypes.byref(cursor)):
                self.clear_current_element()
                return

            # =====================================================
            # 2. Small movement filter
            # =====================================================
            if self._last_uia_point is not None:
                dx = abs(cursor.x - self._last_uia_point.x)
                dy = abs(cursor.y - self._last_uia_point.y)

                if dx < self.uia_min_move_px and dy < self.uia_min_move_px:
                    return

            # =====================================================
            # 3. Mouse moved enough -> leave Tab navigation
            # =====================================================
            if self._acc_tab_mode:
                self._acc_tab_mode = False
                self._acc_tab_index = None

            # =====================================================
            # 4. Fast leave test
            # =====================================================
            if (
                self.current_element_global_rect is not None
                and not self.current_element_global_rect.isEmpty()
            ):
                if not self.current_element_global_rect.contains(
                    cursor.x,
                    cursor.y,
                ):
                    self.clear_current_element()

            # =====================================================
            # 5. ACC hit test
            # =====================================================
            hit_path = get_deepest_element_at_point(
                x=cursor.x,
                y=cursor.y,
                overlay_hwnd=self.hwnd,
            )

            if not hit_path:
                self._acc_hit_path = None
                self.clear_current_element()
                return

            # Cache the complete path for Tab navigation.
            self._acc_hit_path = hit_path

            element = hit_path.current

            if not element:
                self._acc_hit_path = None
                self.clear_current_element()
                return

            # =====================================================
            # 6. Show deepest element
            # =====================================================
            if not self.show_acc_element(element):
                self.clear_current_element()
                return

        finally:
            self._last_uia_point = wintypes.POINT(cursor.x, cursor.y)
            self.hit_test_running = False

    def show_acc_element(self, element):
        if not element:
            return False

        element_rect = element.rect
        if element_rect is None:
            return False

        left, top, right, bottom = element_rect

        if right <= left or bottom <= top:
            return False

        # =====================================================
        # 1. Global physical element rect
        # =====================================================
        element_global_rect = QRect(left, top, right - left, bottom - top).normalized()

        # Restrict to overlay / virtual desktop.
        element_global_rect = element_global_rect.intersected(self.virtual_rect)

        if element_global_rect.isEmpty():
            return False

        # Don't highlight entire virtual desktop.
        if element_global_rect == self.virtual_rect:
            return False

        # =====================================================
        # 2. Global -> viewport local
        # =====================================================
        viewport_rect = QRect(
            self.viewport().mapFromGlobal(element_global_rect.topLeft()),
            self.viewport().mapFromGlobal(element_global_rect.bottomRight()),
        ).normalized()

        if viewport_rect.isEmpty():
            return False

        # =====================================================
        # 3. Viewport -> scene
        # =====================================================
        scene_rect = self.mapToScene(viewport_rect).boundingRect()

        element_scene_rect = scene_rect.intersected(self.scene().sceneRect())

        if element_scene_rect.isEmpty():
            return False

        # =====================================================
        # 4. Change detection
        # =====================================================
        changed = (
            element_global_rect != self.current_element_global_rect
            or element != self.current_element
        )

        # =====================================================
        # 5. Synchronize state
        # =====================================================
        self.current_element_global_rect = QRect(element_global_rect)
        self.current_element_rect = QRect(viewport_rect)
        self.current_element_scene_rect = QRectF(element_scene_rect)
        self.current_element = element

        # =====================================================
        # 6. Update highlight
        # =====================================================
        if changed:
            self.scene().set_selection_rect(
                self.current_element_scene_rect, finished=False
            )

        return True

    def clear_current_element(self):
        """
        Reset ACC/UIA hit testing variables and update painter.
        """
        if self.current_element is None and self.current_element_rect.isEmpty():
            return
        self._acc_hit_path = None
        self.current_element = None
        self.current_element_rect = QRect()
        self.current_element_global_rect = QRect()
        # only clear snip selection.
        self.scene().clear_snip_selection()

    def reset_for_new_snip(self) -> None:
        """Clear selection/annotations and return to SELECT."""
        # self.scene().reset_selection()
        self.scene().reset_for_new_snip()
        self._toolbar.set_tool(tool=Tool.SELECT)
        # must set after set_tool
        self._set_interaction_cursor(Qt.CursorShape.CrossCursor)

    def set_capture(
        self, pixmap: QPixmap, virtual_rect: QRect, frozen_cursor=None
    ) -> None:
        """
        Initializes the screen capture session with a background pixmap,
        window geometry, and default selection states.
        """
        scene = self.scene()
        self.reset_for_new_snip()

        self.virtual_rect = QRect(virtual_rect)
        self.setGeometry(self.virtual_rect)  # global native-window coordinates
        scene.set_pixmap(pixmap)

        if frozen_cursor is not None:
            scene.set_frozen_cursor(frozen_cursor, self.virtual_rect)

    def cycle_acc_element(self, backward=False):
        hit_path = self._acc_hit_path
        if not hit_path:
            return
        elements = hit_path.elements
        if not elements:
            return

        # =====================================================
        # 1. First Tab
        #
        # Current displayed element is already deepest.
        # =====================================================
        if not self._acc_tab_mode:
            self._acc_tab_mode = True
            self._acc_tab_index = len(elements) - 1

        # =====================================================
        # 2. Navigate hierarchy
        # Tab       -> parent
        # Shift+Tab -> child
        # =====================================================
        if backward:
            self._acc_tab_index += 1
        else:
            self._acc_tab_index -= 1

        # Clamp instead of wrap.
        self._acc_tab_index = max(
            0,
            min(self._acc_tab_index, len(elements) - 1),
        )

        # =====================================================
        # 3. Show selected element
        # =====================================================
        element = elements[self._acc_tab_index]
        self.show_acc_element(element)

    # --------------------------------------------------------
    # Create completely independent scene for PinWindow
    # --------------------------------------------------------

    def pin_selection(self):
        selection = self.scene().selection
        if not selection:
            return
        rect = selection.scene_selection_rect()
        if rect.isEmpty():
            return
        # Position of captured area
        capture_rect = rect.intersected(self.scene().sceneRect())
        if capture_rect.isEmpty():
            return
        # Scene -> viewport -> global
        global_pos = self.viewport().mapToGlobal(
            self.mapFromScene(capture_rect.topLeft())
        )
        # Scene handles creation of graphics content
        pin_scene = self.scene().create_pin_scene()
        if pin_scene is None:
            return
        # View does NOT create PinWindow, pass to controller
        self.createPinRequested.emit(pin_scene, global_pos)
        self.hide()

    # --------------------------------------------------------
    # Overide Funcs from ImageView.
    # --------------------------------------------------------
    def export_rect(self):
        """
        Implement in GrabView for update_toolbar_position ref rect.
        """
        selection = self.scene().selection
        if not selection:
            return QRectF()
        return selection.scene_selection_rect().intersected(self.scene().sceneRect())

    def toolbar_anchor_rect(self):
        """
        overide get anchor for toolbar function，
        Return selection rect in viewport coordinate.
        """
        selection = self.scene().selection
        if selection is None:
            return None
        rect = selection.scene_selection_rect()  # scene rect.
        if rect.isEmpty():
            return None
        return self.mapFromScene(rect).boundingRect()  # return Viewport local rect.

    def pin_self(self):
        """
        overide pin_self function.
        """
        self.pin_selection()

    # ========================================================
    # Mouse / Keyboard interaction
    # Overule event
    # ========================================================

    def adjust_selection_by_key(
        self,
        key: int,
        modifiers: Qt.KeyboardModifier,
    ) -> bool:
        selection = self.scene().selection
        if selection is None or not selection.is_finished():
            return False

        rect = selection.scene_selection_rect()
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        # ==================================================
        # Shift + Arrow -> resize
        # ==================================================
        if shift:
            if key == Qt.Key.Key_Left:
                rect.setRight(rect.right() - 1)
            elif key == Qt.Key.Key_Right:
                rect.setRight(rect.right() + 1)
            elif key == Qt.Key.Key_Up:
                rect.setBottom(rect.bottom() - 1)
            elif key == Qt.Key.Key_Down:
                rect.setBottom(rect.bottom() + 1)
            else:
                return False
        # ==================================================
        # Arrow -> move
        # ==================================================
        else:
            if key == Qt.Key.Key_Left:
                rect.translate(-1, 0)
            elif key == Qt.Key.Key_Right:
                rect.translate(1, 0)
            elif key == Qt.Key.Key_Up:
                rect.translate(0, -1)
            elif key == Qt.Key.Key_Down:
                rect.translate(0, 1)
            else:
                return False
        rect = rect.normalized().intersected(self.scene().sceneRect())
        if rect.isEmpty():
            return True
        self.scene().set_selection_rect(rect, finished=True)
        return True

    def keyPressEvent(self, event):
        scene = self.scene()
        key = event.key()
        modifiers = event.modifiers()

        # -----------------------------------------------------
        # If editting, no keypress event.
        # -----------------------------------------------------
        item = scene.annotation_handles.item
        # If text or node are editing, just continue...
        if item is not None and hasattr(item, "is_editing"):
            if item.is_editing():
                return super().keyPressEvent(event)

        # -----------------------------------------------------
        # ESC
        # -----------------------------------------------------
        if key == Qt.Key.Key_Escape:
            # ----------------------------------------------
            # 2. Annotation selected -> deselect.
            # ---------------------------------------------
            if scene.has_annotation_selection():
                scene.clear_annotation_selection()
                event.accept()
                return

            self.close()
            event.accept()
            return

        # -----------------------------------------------------
        # Tab / Shift+Tab
        # -----------------------------------------------------
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            backward = key == Qt.Key.Key_Backtab or bool(
                modifiers & Qt.KeyboardModifier.ShiftModifier
            )
            self.cycle_acc_element(backward=backward)
            event.accept()
            return

        # ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        # shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        # ["←", "↑", "↓", "→"] adjust selection.
        if self.adjust_selection_by_key(event.key(), event.modifiers()):
            event.accept()
            return

        # # =========================================================
        # # Ctrl+A
        # # Select physical screen currently under mouse
        # # =========================================================
        # if key == Qt.Key.Key_A and ctrl:
        #     self.select_current_screen()
        #     event.accept()
        #     return

        # # =========================================================
        # # Shift+R
        # # Reuse previous snip rectangle
        # # =========================================================
        # if key == Qt.Key.Key_R and shift:
        #     self.reuse_last_selection()
        #     event.accept()
        #     return

        # # =========================================================
        # # WASD
        # # =========================================================
        # selection = scene.selection
        # if selection is None:
        #     return super().keyPressEvent(event)
        # if key not in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
        #     return super().keyPressEvent(event)

        # step = 10.0 if (modifiers & Qt.KeyboardModifier.ControlModifier) else 1.0

        # # =========================================================
        # # Shift + WASD -> resize selection
        # # =========================================================
        # if modifiers & Qt.KeyboardModifier.ShiftModifier:
        #     self._move_selection_by_key(selection, key, step)
        #     event.accept()
        # # =========================================================
        # # WASD -> move selection
        # # =========================================================
        # else:
        #     self._resize_selection_by_key(selection, key, step)
        #     event.accept()

        super().keyPressEvent(event)

    def _move_selection_by_key(self, selection, key, step):
        dx = 0.0
        dy = 0.0
        if key == Qt.Key.Key_W:
            dy = -step
        elif key == Qt.Key.Key_S:
            dy = step
        elif key == Qt.Key.Key_A:
            dx = -step
        elif key == Qt.Key.Key_D:
            dx = step
        selection.moveBy(dx, dy)

    def _resize_selection_by_key(self, selection, key, step):
        rect = QRectF(selection.rect())
        min_size = 5.0
        if key == Qt.Key.Key_W:
            rect.setTop(min(rect.bottom() - min_size, rect.top() - step))
        elif key == Qt.Key.Key_S:
            rect.setBottom(rect.bottom() + step)
        elif key == Qt.Key.Key_A:
            rect.setLeft(min(rect.right() - min_size, rect.left() - step))
        elif key == Qt.Key.Key_D:
            rect.setRight(rect.right() + step)
        selection.set_selection_rect(rect)

    def mousePressEvent(self, event):
        """
        Grabview mouse event will receive prior to scene.
        """
        if event.button() != Qt.MouseButton.LeftButton:
            self.restart_new_snip()
            return super().mousePressEvent(event)

        self._press_pos = event.position().toPoint()
        self._manual_drag_started = False
        self._pending_acc_selection = None

        # Remember ACC candidate, but DON'T select it yet.
        if (
            # self.hit_test_enabled and
            self.current_element is not None
            and self.current_element_scene_rect is not None
            and not self.current_element_scene_rect.isEmpty()
        ):
            self.disable_hit_testing()
            self._pending_acc_selection = QRectF(self.current_element_scene_rect)
            self.clear_current_element()
            # self.scene().clear_selection() #already in clear current element.
        # Always forward press so GrabScene can begin
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        current_pos = event.position().toPoint()
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._pending_acc_selection is not None
        ):
            delta = current_pos - self._press_pos
            if (
                abs(delta.x()) >= self.manual_drag_threshold
                or abs(delta.y()) >= self.manual_drag_threshold
            ):
                self._manual_drag_started = True

                # User clearly wants manual selection.
                self._pending_acc_selection = None
        if self._shortcut_hint.isVisible():
            self.adjust_panel_position(
                self._shortcut_hint,
                event.globalPosition().toPoint(),
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)

        pending_acc = self._pending_acc_selection
        manual_drag = self._manual_drag_started

        self._pending_acc_selection = None
        self._manual_drag_started = False

        # Press was forwarded to GrabScene,
        super().mouseReleaseEvent(event)

        # Simple click -> replace temporary manual selection with ACC selection
        if pending_acc is not None and not manual_drag:
            self.scene().set_selection_rect(pending_acc, finished=True)
            self.on_selection_finished()

    def showEvent(self, event):
        # t0 = time.perf_counter_ns()
        super().showEvent(event)
        self.hwnd = int(self.winId())  # get after shown.

        # -----------------------------------------------------
        # Subtract 1px to prevent taskbar flicker.
        # Global coordinates: position and size of the overlay window.
        # -----------------------------------------------------
        r = self.virtual_rect
        clip_r = QRect(r.x(), r.y(), r.width(), r.height() - 1)
        self.setGeometry(clip_r)
        # -----------------------------------------------------
        self.set_hint_mode(HintMode.SNIP)
        self.show_shortcut_hint()
        self.enable_hit_testing()
        # print(f"GrabView.show: {(time.perf_counter_ns()- t0) / 1e6:.1f} ms", flush=True)

    def hideEvent(self, event):
        """
        Reset all ui.
        """
        self.hide_shortcut_hint()
        self.hide_cursor_magnifier()
        self.hide_toolbar()
        super().hideEvent(event)

    def closeEvent(self, event):
        """
        Re-use Grabview, Do not close.
        """
        self.hide()
        event.ignore()

    def _lock_visible_rect(self) -> None:
        size = self.viewport().size()
        self.setSceneRect(QRectF(0, 0, size.width(), size.height()))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._lock_visible_rect()


# ============================================================
# Main
# ============================================================


if __name__ == "__main__":

    def main():
        app = QApplication(sys.argv)
        view = GrabView()
        view.show()
        sys.exit(app.exec())

    main()

    def adjust_panel_position_(self, panel, mouse_pos: QPoint):
        """
        Protol, current not use.
        """
        if panel is None:
            return

        panel.adjustSize()
        margin = 0
        mouse_margin = 32
        selection_margin = 8
        panel_size = panel.size()
        # =========================================================
        # Current mouse screen
        # =========================================================
        screen = QApplication.screenAt(mouse_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return
        screen_rect = screen.availableGeometry()
        # =========================================================
        # Mouse exclusion area
        # =========================================================
        mouse_rect = QRect(
            mouse_pos.x() - mouse_margin,
            mouse_pos.y() - mouse_margin,
            mouse_margin * 2,
            mouse_margin * 2,
        )
        # =========================================================
        # Selection -> global
        # =========================================================
        selection_rect = None
        selection = getattr(self.scene(), "selection", None)
        if selection is not None:
            rect = selection.scene_selection_rect()
            if not rect.isEmpty():
                top_left = self.viewport().mapToGlobal(
                    self.mapFromScene(rect.topLeft())
                )
                bottom_right = self.viewport().mapToGlobal(
                    self.mapFromScene(rect.bottomRight())
                )
                selection_rect = QRect(top_left, bottom_right).normalized()

                selection_rect.adjust(
                    -selection_margin,
                    -selection_margin,
                    selection_margin,
                    selection_margin,
                )
        # =========================================================
        # Check current panel position FIRST
        # =========================================================
        panel_global_pos = self.viewport().mapToGlobal(panel.pos())
        current_rect = QRect(panel_global_pos, panel_size)
        current_on_screen = screen_rect.contains(current_rect)
        overlaps_mouse = current_rect.intersects(mouse_rect)
        overlaps_selection = selection_rect is not None and current_rect.intersects(
            selection_rect
        )
        # ---------------------------------------------------------
        # IMPORTANT:
        # Keep panel exactly where it is if still valid.
        # This prevents corner jumping.
        # ---------------------------------------------------------
        if current_on_screen and not overlaps_mouse and not overlaps_selection:
            return
        # =========================================================
        # Four screen corners
        # =========================================================
        candidates = [
            # Top-left
            QPoint(screen_rect.left() + margin, screen_rect.top() + margin),
            # Top-right
            QPoint(
                screen_rect.right() - panel_size.width() - margin + 1,
                screen_rect.top() + margin,
            ),
            # Bottom-left
            QPoint(
                screen_rect.left() + margin,
                screen_rect.bottom() - panel_size.height() - margin + 1,
            ),
            # Bottom-right
            QPoint(
                screen_rect.right() - panel_size.width() - margin + 1,
                screen_rect.bottom() - panel_size.height() - margin + 1,
            ),
        ]
        # =========================================================
        # Find valid candidates
        # =========================================================
        valid = []
        fallback = []
        for pos in candidates:
            rect = QRect(pos, panel_size)
            if rect.intersects(mouse_rect):
                continue
            center = rect.center()
            dx = center.x() - mouse_pos.x()
            dy = center.y() - mouse_pos.y()
            distance_sq = dx * dx + dy * dy
            candidate = (distance_sq, pos)
            if selection_rect is not None and rect.intersects(selection_rect):
                fallback.append(candidate)
            else:
                valid.append(candidate)

        # =========================================================
        # Choose a new position ONLY because current one was invalid
        # =========================================================
        pool = valid or fallback
        if not pool:
            return
        _, best_pos = max(pool, key=lambda candidate: candidate[0])
        # =========================================================
        # Global -> viewport local
        # =========================================================
        local_pos = self.viewport().mapFromGlobal(best_pos)
        panel.move(local_pos)
        panel.raise_()

    def adjust_panel_position__(self, panel, mouse_pos: QPoint):
        if panel is None:
            return
        # panel.adjustSize()
        margin = 0
        mouse_margin = 32
        selection_margin = 8
        panel_size = panel.size()
        # =========================================================
        # 1. Current mouse screen
        # =========================================================
        screen = QApplication.screenAt(mouse_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return
        # screen_rect = screen.availableGeometry()
        screen_rect = screen.geometry()
        # =========================================================
        # 2. Mouse exclusion area
        # =========================================================
        mouse_rect = QRect(
            mouse_pos.x() - mouse_margin,
            mouse_pos.y() - mouse_margin,
            mouse_margin * 2,
            mouse_margin * 2,
        )
        # =========================================================
        # 3. Selection rect -> global coordinates
        # =========================================================
        selection_rect = None
        selection = getattr(self.scene(), "selection", None)
        if selection is not None:
            rect = selection.scene_selection_rect()
            if not rect.isEmpty():
                top_left = self.viewport().mapToGlobal(
                    self.mapFromScene(rect.topLeft())
                )
                bottom_right = self.viewport().mapToGlobal(
                    self.mapFromScene(rect.bottomRight())
                )
                selection_rect = QRect(top_left, bottom_right).normalized()
                selection_rect.adjust(
                    -selection_margin,
                    -selection_margin,
                    selection_margin,
                    selection_margin,
                )

        # =========================================================
        # 4. Current panel global rect
        # =========================================================
        panel_global_pos = self.viewport().mapToGlobal(panel.pos())
        current_rect = QRect(panel_global_pos, panel_size)

        current_on_screen = screen_rect.contains(current_rect)
        overlaps_mouse = current_rect.intersects(mouse_rect)
        # print(current_rect, QCursor.pos(), mouse_pos, mouse_rect)

        overlaps_selection = selection_rect is not None and current_rect.intersects(
            selection_rect
        )

        # =========================================================
        # 5. STABILITY RULE
        #
        # Keep current position whenever possible.
        #
        # Selection overlap alone should NOT continuously move the
        # panel once it has already been placed.
        # =========================================================

        # Hard condition:
        # mouse must never be covered.
        if current_on_screen and not overlaps_mouse:

            # Perfect location -> definitely keep it.
            if not overlaps_selection:
                return

            # The current location overlaps selection.
            #
            # Before moving it, check whether there actually exists
            # another corner outside BOTH mouse and selection.
            #
            # If none exists, current position is already as good as
            # possible, so DON'T jump between fallback corners.
            pass

        # =========================================================
        # 6. Four candidate corners
        # =========================================================
        candidates = [
            # Top-left
            QPoint(
                screen_rect.left() + margin,
                screen_rect.top() + margin,
            ),
            # Top-right
            QPoint(
                screen_rect.right() - panel_size.width() - margin + 1,
                screen_rect.top() + margin,
            ),
            # Bottom-left
            QPoint(
                screen_rect.left() + margin,
                screen_rect.bottom() - panel_size.height() - margin + 1,
            ),
            # Bottom-right
            QPoint(
                screen_rect.right() - panel_size.width() - margin + 1,
                screen_rect.bottom() - panel_size.height() - margin + 1,
            ),
        ]

        # =========================================================
        # 7. Evaluate candidates
        # =========================================================
        valid = []
        fallback = []

        for pos in candidates:
            rect = QRect(pos, panel_size)

            # -----------------------------------------------------
            # HARD RULE:
            # never put the hint under/near the mouse
            # -----------------------------------------------------
            if rect.intersects(mouse_rect):
                continue

            # Distance from mouse
            center = rect.center()
            dx = center.x() - mouse_pos.x()
            dy = center.y() - mouse_pos.y()
            distance_sq = dx * dx + dy * dy
            candidate = (distance_sq, pos)

            # -----------------------------------------------------
            # Prefer positions outside selection
            # -----------------------------------------------------
            if selection_rect is not None and rect.intersects(selection_rect):
                fallback.append(candidate)
            else:
                valid.append(candidate)

        # =========================================================
        # 8. IMPORTANT STABILITY CHECK
        #
        # Current panel overlaps selection, but don't move if every
        # alternative also overlaps selection.
        # =========================================================
        if (
            current_on_screen
            and not overlaps_mouse
            and overlaps_selection
            and not valid
        ):
            return

        # =========================================================
        # 9. Selection priority
        #
        # First:
        #     outside mouse + outside selection
        #
        # Fallback:
        #     outside mouse, selection overlap allowed
        # =========================================================
        pool = valid or fallback
        if not pool:
            return

        # =========================================================
        # 10. Pick farthest candidate from mouse
        #
        # IMPORTANT:
        # We only reach here because the current position should
        # actually be changed.
        # =========================================================
        _, best_pos = max(pool, key=lambda candidate: candidate[0])

        # =========================================================
        # 11. Global -> viewport local
        # =========================================================
        local_pos = self.viewport().mapFromGlobal(best_pos)
        # Avoid redundant move()
        if panel.pos() != local_pos:
            panel.move(local_pos)

        panel.raise_()

    # # ===========================================================
    # # ACC hit testing
    # # ===========================================================
    # def _update_acc_hit_test(self):
    #     """
    #     Perform ACC hit testing at the current physical cursor position.

    #     Coordinate contract:
    #         cursor:
    #             global physical coordinates
    #         element["rect"]:
    #             global physical coordinates
    #         current_element_global_rect:
    #             global physical coordinates
    #         current_element_rect:
    #             viewport-local coordinates
    #         selection rect:
    #             scene coordinates
    #     """
    #     # if not self.hit_test_enabled:
    #     #     return

    #     if self.scene().is_selecting or self.hit_test_running:
    #         return

    #     self.hit_test_running = True
    #     cursor = wintypes.POINT()
    #     try:
    #         # =====================================================
    #         # 1. Physical cursor position
    #         # =====================================================
    #         if not user32.GetCursorPos(ctypes.byref(cursor)):
    #             self.clear_current_element()
    #             return
    #         # =====================================================
    #         # 2. Small movement filter
    #         # =====================================================
    #         if self._last_uia_point is not None:
    #             dx = abs(cursor.x - self._last_uia_point.x)
    #             dy = abs(cursor.y - self._last_uia_point.y)

    #             if dx < self.uia_min_move_px and dy < self.uia_min_move_px:
    #                 return
    #         # =====================================================
    #         # 3. Fast leave test
    #         #
    #         # Keep this rect GLOBAL.
    #         # No coordinate conversion required.
    #         # =====================================================
    #         if (
    #             self.current_element_global_rect is not None
    #             and not self.current_element_global_rect.isEmpty()
    #         ):
    #             if not self.current_element_global_rect.contains(cursor.x, cursor.y):
    #                 self.clear_current_element()

    #         # =====================================================
    #         # 4. ACC hit test
    #         # =====================================================
    #         element = get_deepest_element_at_point(
    #             x=cursor.x, y=cursor.y, overlay_hwnd=self.hwnd
    #         )

    #         if not element:
    #             self.clear_current_element()
    #             return
    #         element_rect = element.get("rect")
    #         if element_rect is None:
    #             self.clear_current_element()
    #             return
    #         left, top, right, bottom = element_rect
    #         if right <= left or bottom <= top:
    #             self.clear_current_element()
    #             return
    #         # =====================================================
    #         # 5. Global physical element rect
    #         # =====================================================
    #         element_global_rect = QRect(
    #             left, top, right - left, bottom - top
    #         ).normalized()

    #         # Restrict to overlay / virtual desktop.
    #         element_global_rect = element_global_rect.intersected(self.virtual_rect)

    #         if element_global_rect.isEmpty():
    #             self.clear_current_element()
    #             return

    #         # Don't highlight entire virtual desktop.
    #         if element_global_rect == self.virtual_rect:
    #             self.clear_current_element()
    #             return

    #         # =====================================================
    #         # 6. Global -> viewport local
    #         # =====================================================
    #         viewport_rect = QRect(
    #             self.viewport().mapFromGlobal(element_global_rect.topLeft()),
    #             self.viewport().mapFromGlobal(element_global_rect.bottomRight()),
    #         ).normalized()

    #         if viewport_rect.isEmpty():
    #             self.clear_current_element()
    #             return

    #         # =====================================================
    #         # 7. Viewport -> scene
    #         # =====================================================
    #         scene_rect = self.mapToScene(viewport_rect).boundingRect()
    #         self.current_element_scene_rect = scene_rect.intersected(
    #             self.scene().sceneRect()
    #         )
    #         if self.current_element_scene_rect.isEmpty():
    #             self.clear_current_element()
    #             return

    #         # =====================================================
    #         # 8. Change detection
    #         # =====================================================
    #         changed = (
    #             element_global_rect != self.current_element_global_rect
    #             or element != self.current_element
    #         )

    #         # Always keep state synchronized.
    #         self.current_element_global_rect = QRect(element_global_rect)
    #         self.current_element_rect = QRect(viewport_rect)
    #         self.current_element = element
    #         # =====================================================
    #         # 9. Update hover/selection rectangle
    #         # =====================================================
    #         if changed:
    #             self.scene().set_selection_rect(
    #                 self.current_element_scene_rect, finished=False
    #             )

    #     finally:
    #         self._last_uia_point = wintypes.POINT(cursor.x, cursor.y)
    #         self.hit_test_running = False
