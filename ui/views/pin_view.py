import math
from PyQt6.QtCore import QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import QPainter, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
    QLabel,
    QWidget,
)

from .image_view import ImageView
from core.models import AppContext
from ui.models.tools import Tool, ToolAction


class PinView(ImageView):
    def __init__(
        self,
        scene: QGraphicsScene | None = None,
        context: AppContext | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(scene, context, parent)
        self.context = context
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._scene = scene
        if self._scene:
            self.setScene(self._scene)
            scene_rect = self._scene.sceneRect()
            self.setSceneRect(scene_rect)
            # Fix Pinview size not full.
            self.setFixedSize(scene_rect.size().toSize())

        # --------------------------------
        # Transform : zoom flip rotate
        # --------------------------------
        self._zoom = 1.0
        self._zoom_step = 1.15
        self._zoom_min = 0.25
        self._zoom_max = 4.0

        self._rotation = 0
        self._flip_h = False
        self._flip_v = False

        # --------------------------------
        # Opacity status
        # --------------------------------
        self._status_label = QLabel(self.viewport())
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self._status_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(25, 25, 25, 210);
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 16px;
                font-weight: 600;
            }
        """)
        self._status_label.hide()
        # Restart this timer on every wheel tick.
        self._status_label_timer = QTimer(self)
        self._status_label_timer.setSingleShot(True)
        self._status_label_timer.timeout.connect(self._status_label.hide)

        # --------------------------------
        # Set initial state.
        # --------------------------------
        self.set_init_states()

    @property
    def toolbar_enabled(self) -> bool:
        return self._toolbar_enabled

    def set_toolbar_enabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._toolbar_enabled:
            return
        self._toolbar_enabled = enabled
        self.update_toolbar_visibility()

    def update_toolbar_visibility(self):
        window = self.window()
        if self._toolbar_enabled and window is not None and window.isActiveWindow():
            self.show_toolbar()
        else:
            self.hide_toolbar()

    def set_init_states(self):
        """
        set init states: draging, toolbar...
        """

        self._drag_window = False
        self._drag_offset = None

        self._toolbar_enabled = True
        self._toolbar.set_tool_action_visible(ToolAction.PIN, False)

    # def show_status_label(self, opacity: float):
    def show_status_message(self, message, timeout=1000):
        self._status_label.setText(message)
        self._status_label.adjustSize()
        viewport_rect = self.viewport().rect()
        x = (viewport_rect.width() - self._status_label.width()) // 2
        y = (
            self._status_label.height()
        )  # (viewport_rect.height() - self._status_label.height()) // 2
        self._status_label.move(x, y)
        self._status_label.show()
        self._status_label.raise_()
        # Restart countdown every wheel event.
        self._status_label_timer.start(timeout)

    def close_selection(self):
        self._toolbar.hide()
        self.close()
        # QApplication.quit()

    def toolbar_anchor_rect(self):
        """
        Implement in PinView for update_toolbar_position ref rect.
        Return viewport rect().
        """
        # return self.scene().sceneRect()
        return self.viewport().rect()

    def _adjust_window_opacity(self, event) -> bool:
        delta = event.angleDelta().y()
        if delta == 0:
            return False
        step = 0.05 if delta > 0 else -0.05
        window = self.window()
        new_opacity = max(0.20, min(1.0, window.windowOpacity() + step))
        window.setWindowOpacity(new_opacity)
        opacity_percent = round(new_opacity * 100)
        self.show_status_message(f"Opacity  {opacity_percent}%")
        return True

    def wheelEvent(self, event):
        # ==================================================
        # 0. Ctrl + Wheel -> PinWindow opacity
        # ==================================================
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if self._adjust_window_opacity(event):
                event.accept()
                return
        return super().wheelEvent(event)

    def _wheel_without_selection(self, event):
        """
        ImageView call.
        """
        # ==================================================
        # 2. Normal PinView wheel -> zoom
        # ==================================================
        from .pin_window import PinWindow  # Need to solve

        old_zoom = self._zoom
        factor = (
            self._zoom_step if event.angleDelta().y() > 0 else 1.0 / self._zoom_step
        )
        new_zoom = max(self._zoom_min, min(self._zoom_max, old_zoom * factor))
        if new_zoom == old_zoom:
            event.accept()
            return
        # ----------------------------------
        # Mouse anchor
        # ----------------------------------
        mouse_pos = event.position()
        fx = mouse_pos.x() / max(1, self.viewport().width())
        fy = mouse_pos.y() / max(1, self.viewport().height())
        global_mouse = event.globalPosition().toPoint()
        # ----------------------------------
        # Scale graphics
        # ----------------------------------
        self._zoom = new_zoom
        self._update_view_transform()

        # --------------------------------
        # Calculate transformed view size
        # Resize / move pin window.
        # --------------------------------
        # size = self.sceneRect().size()
        # width = size.width()
        # height = size.height()
        # if self._rotation % 180 != 0:
        #     width, height = height, width
        # new_size = QSize(int(width * new_zoom), int(height * new_zoom))
        rect = self.transform().mapRect(self.sceneRect())
        new_size = QSize(
            math.floor(rect.width()), math.floor(rect.height())
        )  # floor() make sure the Pinwindow size not larger than viewport.
        # --------------------------------
        # Resize PinWindow
        # --------------------------------
        window = self.window()
        if isinstance(window, PinWindow):
            window.resize_for_view(new_size)
            # Same relative cursor position
            # inside the resized PinView
            new_local = QPoint(
                round(self.viewport().width() * fx),
                round(self.viewport().height() * fy),
            )
            current_global = self.viewport().mapToGlobal(new_local)
            # Keep same content area under mouse
            window.move(window.pos() + global_mouse - current_global)
            self.show_status_message(f"Zoom: {round(new_zoom * 100)}%")
            # print(
            #     "window      :",
            #     window.size(),
            #     "\nview        :",
            #     self.size(),
            #     "\nviewport    :",
            #     self.viewport().size(),
            #     "\ntransformed :",
            #     self.transform().mapRect(self.sceneRect()).size(),
            # )
        event.accept()

    def rotate_left(self):
        self._rotation = (self._rotation - 90) % 360
        self._apply_pin_transform()

    def rotate_right(self):
        self._rotation = (self._rotation + 90) % 360
        self._apply_pin_transform()

    def flip_horizontal(self):
        self._flip_h = not self._flip_h
        self._apply_pin_transform()

    def flip_vertical(self):
        self._flip_v = not self._flip_v
        self._apply_pin_transform()

    def _update_view_transform(self):
        """
        Apply image view transform
        """
        transform = QTransform()
        transform.rotate(self._rotation)
        transform.scale(
            -1 if self._flip_h else 1,
            -1 if self._flip_v else 1,
        )
        transform.scale(self._zoom, self._zoom)
        self.setTransform(transform)

    def _apply_pin_transform(self):
        """
        Apply Pin window transform.
        will call apply view transform.
        """
        from .pin_window import PinWindow  # Need to solve

        # --------------------------------
        # Preserve current window center
        # --------------------------------
        window = self.window()
        old_center = window.frameGeometry().center()
        # --------------------------------
        # Apply view transform
        # --------------------------------
        self._update_view_transform()
        # --------------------------------
        # Calculate physical displayed size
        # --------------------------------
        scene_size = self.sceneRect().size()
        width = scene_size.width()
        height = scene_size.height()
        # 90 / 270 degrees swaps W/H
        if self._rotation % 180 != 0:
            width, height = height, width
        new_size = QSize(
            round(width * self._zoom),
            round(height * self._zoom),
        )
        # --------------------------------
        # Resize PinWindow
        # --------------------------------
        if isinstance(window, PinWindow):
            window.resize_for_view(new_size)
            # Keep PinWindow center at same location
            new_frame = window.frameGeometry()
            window.move(
                old_center.x() - new_frame.width() // 2,
                old_center.y() - new_frame.height() // 2,
            )
            self.update_toolbar_position()

    def reset_transform(self):
        """
        Reset transform :rotation, flip, zoom.
        Including variables.
        """
        # --------------------------------
        # Transform : zoom flip rotate
        # --------------------------------
        self._zoom = 1.0
        self._rotation = 0
        self._flip_h = False
        self._flip_v = False
        self.resetTransform()

    def mousePressEvent(self, event):
        """
        Pinview receive the mouse event first.
        """
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        scene = self.scene()
        # ==================================================
        # SELECT
        # ==================================================
        if scene is not None and scene.tool_state.tool == Tool.SELECT:
            scene_pos = self.mapToScene(event.position().toPoint())

            # Annotation / resize handle gets priority
            if scene.has_annotation_interaction_at(scene_pos):
                return super().mousePressEvent(event)

            # Empty area -> drag PinWindow
            self._drag_window = True
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()

            event.accept()
            return

        # ==================================================
        # Drawing tools -> Scene
        # ==================================================
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # --------------------------------
        # Window dragging
        # --------------------------------
        if self._drag_window and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            # self.update_toolbar_position()
            event.accept()
            return

        # --------------------------------
        # Drawing
        # --------------------------------
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """ """
        # --------------------------------
        # Finish window dragging
        # --------------------------------
        if event.button() == Qt.MouseButton.LeftButton and self._drag_window:
            self._drag_window = False
            self.scene().clear_annotation_selection()
            event.accept()
            return

        # --------------------------------
        # Finish drawing
        # --------------------------------
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        # Copy
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self.copy_image)

        # Save
        save_action = menu.addAction("Save As...")
        save_action.triggered.connect(self.save_image)
        menu.addSeparator()

        # Always on top
        # top_action = menu.addAction("Always on Top")
        # top_action.setCheckable(True)
        # window = self.window()
        # top_action.setChecked(
        #     bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        # )
        # top_action.toggled.connect(self.alwaysOnTopChanged.emit)
        transform_menu = menu.addMenu("Processing")
        rotate_left = transform_menu.addAction("Rotate Left")
        rotate_right = transform_menu.addAction("Rotate Right")
        transform_menu.addSeparator()
        flip_horizontal = transform_menu.addAction("Flip Horizontal")
        flip_vertical = transform_menu.addAction("Flip Vertical")

        rotate_left.triggered.connect(self.rotate_left)
        rotate_right.triggered.connect(self.rotate_right)
        flip_horizontal.triggered.connect(self.flip_horizontal)
        flip_vertical.triggered.connect(self.flip_vertical)

        # Toolbar
        toolbar_action = menu.addAction("Toolbar")
        toolbar_action.setCheckable(True)
        toolbar_action.setChecked(self._toolbar_enabled)
        toolbar_action.toggled.connect(self.set_toolbar_enabled)

        # Shadow
        current_window = self.window()
        shadow_action = menu.addAction("Show Shadow")
        shadow_action.setCheckable(True)
        shadow_action.setChecked(current_window.get_shadow())
        shadow_action.toggled.connect(
            lambda checked: current_window.set_shadow(checked)
        )
        menu.addSeparator()

        # Close
        close_action = menu.addAction("Close")
        close_action.triggered.connect(self.close_self)

        # event.globalPos() is already
        # global desktop coordinates.
        menu.exec(event.globalPos())

        event.accept()

    def toggled_tool_bar(self, enabled: bool | None):
        if enabled:
            self.show_toolbar()
        else:
            self.hide_toolbar()

    def close_self(self):
        """
        Overide action.
        """
        self.window().close()

    def closeEvent(self, event):
        self.window().close()
        event.ignore()
        return
        # return super().closeEvent(event)
