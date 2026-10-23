from collections.abc import Callable
from PyQt6.QtCore import QTimer, Qt
from ui.views.pin_window import PinWindow


class PinWindowPool:
    """
    Maintenance the current pin window pool,

    control the idle available by refill algorithm and max nr of pins.
    """

    MIN_SIZE = 3  # keep in memory
    MAX_SIZE = 15  # memory safe, total.

    REFILL_THRESHOLD = 1
    REFILL_STEP = 2

    def __init__(self, factory: Callable[[], PinWindow]) -> None:
        self._factory = factory
        self._idle: list[PinWindow] = []
        self._active: set[PinWindow] = set()
        self._closed = False

        self._refill_target = 0

        self._refill_timer = QTimer()
        self._refill_timer.setSingleShot(True)
        self._refill_timer.timeout.connect(self._refill_one)

        for _ in range(min(self.MIN_SIZE, self.MAX_SIZE)):
            self._idle.append(self._create())

    @property
    def idle_count(self) -> int:
        return len(self._idle)

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def total_count(self) -> int:
        return self.idle_count + self.active_count

    def _create(self) -> PinWindow:
        window = self._factory()
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        window.hide()
        window.closed.connect(self.release)
        return window

    def acquire(self) -> PinWindow:
        if self._closed:
            raise RuntimeError("PinWindowPool is closed.")
        if self._idle:
            window = self._idle.pop()
        elif self.total_count < self.MAX_SIZE:
            window = self._create()

        else:
            raise RuntimeError(f"PinWindowPool reached MAX_SIZE={self.MAX_SIZE}.")
        self._active.add(window)
        self._schedule_refill()
        return window

    def _schedule_refill(self) -> None:
        if self._closed:
            return

        if self._refill_timer.isActive():
            return

        if self.idle_count >= self.REFILL_THRESHOLD:
            return

        # Cannot create beyond the hard total limit.
        available_capacity = self.MAX_SIZE - self.total_count

        if available_capacity <= 0:
            return

        refill_count = min(self.REFILL_STEP, available_capacity)
        self._refill_target = self.idle_count + refill_count
        self._refill_timer.start(0)

    def _refill_one(self) -> None:
        if self._closed:
            return
        if self.idle_count >= self._refill_target:
            return
        if self.total_count >= self.MAX_SIZE:
            return
        self._idle.append(self._create())
        if self.idle_count < self._refill_target and self.total_count < self.MAX_SIZE:
            self._refill_timer.start(0)

    def release(self, window: PinWindow) -> None:
        if window not in self._active:
            return
        self._active.remove(window)
        window.hide()
        # Keep only MIN_SIZE idle windows long-term.
        if self.idle_count < self.MIN_SIZE:
            self._idle.append(window)
        else:
            window.deleteLater()

    def close_all(self) -> None:
        """
        close all active pins
        window not close actually but handle by release().
        """
        for window in list(self._active):
            window.close()

    def shutdown(self) -> None:
        if self._closed:
            return

        self._closed = True
        self._refill_timer.stop()

        for window in [*self._idle, *self._active]:
            window.hide()
            window.deleteLater()

        self._idle.clear()
        self._active.clear()


# class PinWindowPool:
#     MIN_SIZE = 3
#     MAX_SIZE = 5
#     REFILL_THRESHOLD = 1  # Trigger when idle <= 1.
#     REFILL_STEP = 2  # Add up to 2 spare windows per refill cycle.

#     def __init__(self, factory: Callable[[], PinWindow]) -> None:
#         self._factory = factory
#         self._idle: list[PinWindow] = []
#         self._active: set[PinWindow] = set()
#         self._closed = False
#         for _ in range(self.MIN_SIZE):
#             self._idle.append(self._create())

#         self._refill_target = 0
#         self._refill_timer = QTimer()
#         self._refill_timer.setSingleShot(True)
#         self._refill_timer.timeout.connect(self._refill_one)

#     @property
#     def idle_count(self) -> int:
#         return len(self._idle)

#     @property
#     def active_count(self) -> int:
#         return len(self._active)

#     def _create(self) -> PinWindow:
#         window = self._factory()
#         window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
#         window.hide()
#         window.closed.connect(self.release)
#         return window

#     def acquire(self) -> PinWindow:
#         if self._closed:
#             raise RuntimeError("PinWindowPool is closed.")

#         window = self._idle.pop() if self._idle else self._create()
#         self._active.add(window)
#         self._schedule_refill()
#         return window

#     def _schedule_refill(self) -> None:
#         idle_count = len(self._idle)
#         if idle_count >= self.REFILL_THRESHOLD:
#             return

#         # Freeze the target for this refill cycle.
#         self._refill_target = min(
#             self.MAX_SIZE,
#             max(self.MIN_SIZE, len(self._idle) + self.REFILL_STEP),
#         )

#         if (
#             self._closed
#             or self._refill_timer.isActive()
#             or idle_count >= self._refill_target
#         ):
#             return
#         self._refill_timer.start(0)

#     def _refill_one(self) -> None:
#         if self._closed:  # or len(self._idle) >= self.MIN_SIZE:
#             return

#         # Released windows may have already satisfied the target.
#         if len(self._idle) >= self._refill_target:
#             return

#         print("refill called")
#         # Create only one window per timer callback.
#         self._idle.append(self._create())
#         self._schedule_refill()

#     def release(self, window: PinWindow) -> None:

#         if window not in self._active:
#             return
#         self._active.remove(window)
#         window.hide()

#         if len(self._idle) < self.MIN_SIZE:
#             self._idle.append(window)
#         else:
#             window.deleteLater()

#     def shutdown(self) -> None:
#         if self._closed:
#             return
#         self._closed = True
#         self._refill_timer.stop()
#         for window in [*self._idle, *self._active]:
#             window.hide()
#             window.deleteLater()

#         self._idle.clear()
#         self._active.clear()
