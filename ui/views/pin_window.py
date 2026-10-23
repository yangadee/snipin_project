from PyQt6.QtCore import QEvent, QPoint, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsScene,
    QWidget,
    QVBoxLayout,
)

from core.models import AppContext
from ui.views.scenes.pin_scene import PinScene
from .pin_view import PinView


class PinWindow(QWidget):
    SHADOW_SIZE = 30
    activated = pyqtSignal(object)
    closed = pyqtSignal(object)

    def __init__(
        self,
        scene: QGraphicsScene | None = None,
        context: AppContext | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.pin_scene = scene
        self.pin_view = PinView(
            scene=self.pin_scene,
            context=context,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.SHADOW_SIZE, self.SHADOW_SIZE, self.SHADOW_SIZE, self.SHADOW_SIZE
        )
        layout.addWidget(self.pin_view)
        self._shadow = None
        # self.set_shadow(True)
        # ----------------------------------
        # Shadow created only once
        # ----------------------------------
        self._shadow = QGraphicsDropShadowEffect(self.pin_view)
        self._shadow.setBlurRadius(25)
        self._shadow.setOffset(0, 5)
        self._shadow.setColor(QColor(0, 0, 0, 75))
        self.pin_view.setGraphicsEffect(self._shadow)

    # ============================================
    # Synchronize pin scene
    # ============================================
    def attach_scene(self, scene: QGraphicsScene):
        self.pin_view.attach_scene(scene)
        view_size = scene.sceneRect().size().toSize()
        self.resize_for_view(view_size)

    def detach_scene(self) -> None:
        self.pin_view.setScene(None)

    def reset_default(self) -> None:
        """
        reset pinview & pin window vars to default.
        """
        self.pin_view.reset_transform()
        self.pin_view.set_init_states()
        self.setWindowOpacity(1.0)  # reset opacity
        self.set_shadow(True)

    def ready_back_to_pool(self):
        """
        Clean up pin to store back to pool.
        """
        self.detach_scene()
        self.reset_default()

    # ============================================
    # Synchronize pin view
    # ============================================
    def resize_for_view(self, view_size):
        self.pin_view.setFixedSize(view_size)
        self.adjustSize()

    def show_toolbar(self):
        self.pin_view.show_toolbar()
        # self.pin_view.toolbar.raise_()
        # self.pin_view.update_toolbar_position()

    def hide_toolbar(self):
        self.pin_view.hide_toolbar()

    def move_view_to_global(self, global_pos: QPoint) -> None:
        """
        Move PinWindow so PinView's viewport top-left is located
        exactly at global_pos.
        """
        # Position of viewport relative to PinWindow.
        viewport_global = self.pin_view.viewport().mapToGlobal(QPoint(0, 0))
        window_global = self.mapToGlobal(QPoint(0, 0))
        offset = viewport_global - window_global
        self.move(global_pos - offset)

    # def set_shadow(self, enabled):
    #     if enabled:
    #         shadow = QGraphicsDropShadowEffect(self)
    #         shadow.setBlurRadius(25)
    #         shadow.setOffset(0, 5)
    #         shadow.setColor(QColor(0, 0, 0, 75))
    #         self.pin_view.setGraphicsEffect(shadow)
    #         self._shadow = shadow
    #     else:
    #         self.pin_view.setGraphicsEffect(None)
    #         self._shadow = None
    # def get_shadow(self) -> bool:
    #     return self._shadow is not None

    # ============================================
    # Pin window Shadow
    # ============================================

    def set_shadow(self, enabled: bool) -> None:
        self._shadow.setEnabled(enabled)

    def get_shadow(self) -> bool:
        return self._shadow.isEnabled()

    # ============================================
    # Pin window Events
    # ============================================

    def moveEvent(self, event):
        super().moveEvent(event)
        pin_view = getattr(self, "pin_view", None)
        if pin_view is not None:
            pin_view.update_toolbar_position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        pin_view = getattr(self, "pin_view", None)
        if pin_view is not None:
            pin_view.update_toolbar_position()

    def closeEvent(self, event):
        self.hide()
        # self.detach_scene()
        # self.reset_default()
        self.closed.emit(self)
        QTimer.singleShot(100, self.ready_back_to_pool)
        event.accept()
        # return super().closeEvent(event)

    def hideEvent(self, event):
        self.hide_toolbar()
        return super().hideEvent(event)

    def event(self, event):
        if event.type() in (
            QEvent.Type.WindowActivate,
            QEvent.Type.WindowDeactivate,
        ):
            self.pin_view.update_toolbar_visibility()
        return super().event(event)


# if __name__ == "__main__":
#     from PyQt6.QtWidgets import QApplication
#     from PyQt6.QtGui import QPixmap
#     import sys

#     app = QApplication(sys.argv)
#     app.setQuitOnLastWindowClosed(True)
#     image_path = r"C:\Users\agieng\Desktop\failed_image.png"
#     pixmap = QPixmap(image_path)
#     pin_scene = PinScene(pixmap)
#     pin = PinWindow(pin_scene=pin_scene, context=None)
#     pin.show()
#     pin.raise_()
#     pin.activateWindow()
#     sys.exit(app.exec())
