import logging

from PyQt6.QtCore import QPoint, Qt, QRectF
from PyQt6.QtGui import (
    QCursor,
    QImage,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)


from core.models import AppContext
from sdk.models import PluginCapability, PluginContext, PluginStatus
from ui.toolbar.toolbar import FloatingToolbar
from ui.models.tools import Tool, ToolAction
from ui.annotation.items import EditableTextItem, CustomNode


class ImageView(QGraphicsView):
    """ """

    context_name = "image"

    def __init__(
        self,
        scene: QGraphicsScene | None = None,
        context: AppContext | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        if scene:
            self.setScene(scene)
        else:
            self.setScene(None)

        self.context = context
        # scene.tool_changed.connect(self._on_tool_changed)
        # self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating, True
        )  # prevent flicker
        self.setContentsMargins(0, 0, 0, 0)

        self._toolbar = FloatingToolbar(self)
        self._connect_toolbar()
        self._setup_undo_shortcuts()

    def _setup_undo_shortcuts(self):
        self._undo_shortcut = QShortcut(
            QKeySequence(QKeySequence.StandardKey.Undo), self
        )
        self._undo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._undo_shortcut.setAutoRepeat(False)
        self._undo_shortcut.activated.connect(self._undo)
        self._redo_shortcut = QShortcut(
            QKeySequence(QKeySequence.StandardKey.Redo), self
        )
        self._redo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._redo_shortcut.setAutoRepeat(False)
        self._redo_shortcut.activated.connect(self._redo)

    def _undo(self):
        scene = self.scene()
        if scene is not None:
            scene.clear_annotation_selection()
            scene.undo_stack.undo()

    def _redo(self):
        scene = self.scene()
        if scene is not None:
            scene.clear_annotation_selection()
            scene.undo_stack.redo()

    def _on_tool_changed(self, tool):
        self.viewport().unsetCursor()
        cursor = self._cursor_for_tool(tool)
        self.viewport().setCursor(cursor)

    @property
    def toolbar(self):
        return self._toolbar

    def set_pixmap(self, pixmap: QPixmap) -> None:
        """
        scene.set_pixmap() warpper.
        """
        self.scene().set_pixmap(pixmap)

    def _connect_toolbar(self):
        # Tool state -> View
        self._toolbar.toolStateChanged.connect(self.set_tool_state)
        self._toolbar.toolStateChanged.connect(self.update_tool_cursor)
        # Toolbar actions -> View
        self._toolbar.actionRequested.connect(self._on_toolbar_action)
        self._toolbar.resized.connect(self.update_toolbar_position)
        self.set_toolbar_plugins()
        if self.context is not None:
            self._toolbar.set_settings(self.context.settings)
        self._synchronize_toolbar_scene()

    def attach_scene(self, scene):
        self.setScene(scene)
        self._synchronize_toolbar_scene()

    def set_tool_state(self, state):
        scene = self.scene()
        if scene is not None:
            scene.set_tool_state(state)

    def _synchronize_toolbar_scene(self):
        scene = self.scene()
        if scene is not None:
            # Immediately synchronize Initial state
            if self._toolbar.tool_state is not None:
                scene.set_tool_state(self._toolbar.tool_state)
            scene.set_tool_specs(self._toolbar.tool_specs)

    def set_toolbar_plugins(self):
        if self.context is None:
            return
        infos = self.context.plugins.plugin_infos_for(PluginCapability.IMAGE)
        self._toolbar.set_plugins(infos)
        self._toolbar.pluginSelected.connect(self.execute_image_plugin)

    # Plugin
    def create_plugin_context(self, plugin_id: str | None = None) -> PluginContext:
        def callback(status):
            self.on_plugin_status_changed(plugin_id, status)

        scene = self.scene()
        selection_rect = None
        if getattr(scene, "selection", None):
            rect = scene.selection.scene_selection_rect()
            if not rect.isEmpty():
                selection_rect = QRectF(rect)
        return PluginContext(
            view=self,
            source=self.context_name,
            selection_rect=selection_rect,
            cursor_pos=QCursor.pos(),
            copy_image=self.render_image,
            callback=callback,
        )

    def execute_image_plugin(self, plugin_id: str):
        record = self.context.plugins.get_plugin(plugin_id)
        if record is None:
            return
        plugin_context = self.create_plugin_context(plugin_id=plugin_id)

        # def callback(status):
        #     self.on_plugin_status_changed(plugin_id, status)

        try:
            self.context.plugins.execute_plugin(plugin_id, plugin_context)
        except Exception:
            logging.exception("Plugin execution failed: %s", plugin_id)

    def on_plugin_status_changed(self, plugin_id: str, status: PluginStatus):
        # update toolbar/plugin button
        self.toolbar.set_plugin_status(plugin_id, status)

    def _on_toolbar_action(self, action: ToolAction):
        handlers = {
            ToolAction.COPY: lambda: self.copy_image(close=True),
            ToolAction.SAVE: self.save_image,
            ToolAction.UNDO: self.scene().undo,
            ToolAction.REDO: self.scene().redo,
            ToolAction.CLOSE: self.close_self,
            ToolAction.PIN: self.pin_self,
        }
        handler = handlers.get(action)
        if handler:
            handler()

    def update_tool_cursor(self):
        spec = self._toolbar.tool_specs.get(self._toolbar.tool_state.tool)
        if spec is None or spec.cursor_factory is None:
            self._tool_cursor = None
            self.viewport().unsetCursor()
            return
        self._tool_cursor = spec.cursor_factory(spec.options)
        self.viewport().setCursor(self._tool_cursor)

    def scene_to_global(self, pos):
        viewport_pos = self.mapFromScene(pos)
        return self.viewport().mapToGlobal(viewport_pos)

    def global_to_scene(self, pos):
        viewport_pos = self.viewport().mapFromGlobal(pos)
        return self.mapToScene(viewport_pos)

    def showEvent(self, event):
        return super().showEvent(event)

    def hideEvent(self, event):
        if self._toolbar is not None:
            self._toolbar.hide()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.window().close()
        event.accept()
        return

    #     if self._toolbar is not None:
    #         self._toolbar.close()
    #     super().closeEvent(event)

    # =========================================================
    # Image export
    # =========================================================

    def export_rect(self):
        """
        Builtin default export scene_rect().
        Rect for render and export image.
        """
        return self.scene().sceneRect()

    def render_image(self, from_viewport: bool = True) -> QImage:
        if from_viewport:
            return self._render_viewport_image()
        return self._render_scene_image()

    def _render_viewport_image(self) -> QImage:
        scene = self.scene()
        if scene is None:
            return QImage()
        scene.clear_annotation_selection()
        viewport = self.viewport()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return QImage()
        # ----------------------------------
        # UI-only scene items
        # ----------------------------------
        hidden_items = []
        selection = getattr(scene, "selection", None)
        if selection is not None:
            hidden_items.append(selection)
        visibility = [(item, item.isVisible()) for item in hidden_items]
        # ----------------------------------
        # Render exactly viewport appearance
        # ----------------------------------
        image = QImage(viewport.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        try:
            for item, _ in visibility:
                item.hide()
            painter = QPainter(image)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                viewport.render(painter)
            finally:
                painter.end()
        finally:
            for item, was_visible in visibility:
                item.setVisible(was_visible)
        return image

    def _render_scene_image(self) -> QImage:
        scene = self.scene()
        if scene is None:
            return QImage()
        scene.clear_annotation_selection()
        source_rect = self.export_rect().normalized()
        if source_rect.isEmpty():
            return QImage()
        # =========================================================
        # 1. Render scene at native resolution
        # =========================================================
        source_size = source_rect.size().toSize()
        image = QImage(source_size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        # =========================================================
        # 2. Hide UI-only scene items
        # =========================================================
        hidden_items = []
        selection = getattr(scene, "selection", None)
        if selection is not None:
            hidden_items.append(selection)
        visibility = [(item, item.isVisible()) for item in hidden_items]
        try:
            for item, _ in visibility:
                item.hide()
            painter = QPainter(image)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                scene.render(painter, QRectF(image.rect()), source_rect)
            finally:
                painter.end()
        finally:
            for item, was_visible in visibility:
                item.setVisible(was_visible)

        # =========================================================
        # 3. Apply PinView orientation
        #
        # IMPORTANT:
        # Don't use self.transform() directly because that also
        # contains _zoom.
        # =========================================================
        # transform = QTransform()
        # transform.rotate(self._rotation)

        # transform.scale(
        #     -1.0 if self._flip_h else 1.0,
        #     -1.0 if self._flip_v else 1.0,
        # )
        # # =========================================================
        # # 4. Only transform if necessary
        # # =========================================================
        # if not transform.isIdentity():
        #     image = image.transformed(
        #         transform, Qt.TransformationMode.SmoothTransformation
        #     )
        return image

    def copy_image(self, close: bool = False):
        image = self.render_image()
        if image.isNull():
            return
        QApplication.clipboard().setImage(image)
        if close:
            self.close_self()

    def save_image(self):
        image = self.render_image()
        if image.isNull():
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            "",
            "PNG Image (*.png);;" "JPEG Image (*.jpg *.jpeg);;" "Bitmap Image (*.bmp)",
        )
        if not path:
            return
        image.save(path)
        self.close_self()

    def update_toolbar_position(self):
        """
        Reposition the toolbar if it currently exists and is visible.
        GrabView / PinView can override _adjust_toolbar_position().
        """
        if self._toolbar is None:
            return
        if not self._toolbar.isVisible():
            return
        self._adjust_toolbar_position()

    def _adjust_toolbar_position(self):
        """
        Calculate and move toolbar to best position.
        Take toolbar_anchor_rect() from GrabView / PinView.
        toolbar_anchor_rect() return anchor in viewport rect.
        """
        anchor_rect = self.toolbar_anchor_rect()
        if anchor_rect is None or anchor_rect.isEmpty():
            self._toolbar.hide()
            return

        margin = 8  # Left right
        spacing = 4  # up down
        # self._toolbar.adjustSize()
        toolbar_width = self._toolbar.width()
        toolbar_height = self._toolbar.height()

        # --------------------------------
        # Anchor rect: viewport rect()
        # --------------------------------
        bottom_right = anchor_rect.bottomRight()
        top_left = anchor_rect.topLeft()
        # --------------------------------
        # Default:
        # below anchor, right aligned
        # --------------------------------
        local_pos = QPoint(bottom_right.x() - toolbar_width, bottom_right.y() + spacing)
        global_pos = self.viewport().mapToGlobal(local_pos)

        # --------------------------------
        # Determine screen containing
        # the anchor center
        # --------------------------------
        center_viewport = anchor_rect.center()
        center_global = self.viewport().mapToGlobal(center_viewport)
        screen = QApplication.screenAt(center_global)

        if screen is None:
            self._toolbar.move(global_pos)
            # self._toolbar.show()
            return

        screen_rect = screen.geometry()
        x = global_pos.x()
        y = global_pos.y()

        # --------------------------------
        # Keep horizontally inside screen
        # --------------------------------
        x = max(
            screen_rect.left() + margin,
            min(x, screen_rect.right() - toolbar_width - margin + 1),
        )

        # --------------------------------
        # Not enough room below:
        # put toolbar ABOVE anchor
        # --------------------------------
        if y + toolbar_height > screen_rect.bottom() - margin + 1:
            top_global = self.viewport().mapToGlobal(QPoint(top_left.x(), top_left.y()))
            y = top_global.y() - toolbar_height - spacing

        # --------------------------------
        # Final vertical clamp
        # --------------------------------
        y = max(
            screen_rect.top() + margin,
            min(y, screen_rect.bottom() - toolbar_height - margin + 1),
        )
        self._toolbar.move(QPoint(x, y))
        # self._toolbar.raise_()

    def toolbar_anchor_rect(self):
        """
        Return toolbar anchor in SCENE coordinates.
        Override in subclasses.
        """
        return None

    def close_self(self):
        """Override when the view has special close behavior."""
        self.window().close()

    def pin_self(self):
        """Override when the view has special close behavior."""
        pass

    def show_toolbar(self):
        # adjust position before showing.
        self._adjust_toolbar_position()
        self._toolbar.show()
        # self._toolbar.raise_()

    def hide_toolbar(self):
        # return
        self._toolbar.hide()
        self._toolbar.set_tool(tool=Tool.SELECT)

    # =========================================================
    # Toolbar visibility
    # =========================================================

    def hideEvent(self, event):
        self._toolbar.hide()
        super().hideEvent(event)

    def wheelEvent(self, event):
        scene = self.scene()
        item = scene.annotation_handles.item
        if item is not None:
            # Check whether mouse is over selected annotation
            scene_pos = self.mapToScene(event.position().toPoint())
            local_pos = item.mapFromScene(scene_pos)
            if item.contains(local_pos):
                # Wheel direction
                delta = event.angleDelta().y()
                if delta == 0:
                    return super().wheelEvent(event)
                step = 1 if delta > 0 else -1
                # --------------------------------
                # Text -> font size
                # --------------------------------
                if isinstance(item, EditableTextItem):
                    font = item.font()
                    size = font.pointSizeF()
                    if size <= 0:
                        size = 12.0
                    font.setPointSizeF(max(6.0, min(200.0, size + step)))
                    item.setFont(font)
                elif isinstance(item, CustomNode):
                    item.set_size(max(8.0, min(200.0, item.size() + step)))
                # --------------------------------
                # Stroke annotation -> pen width
                # --------------------------------
                elif hasattr(item, "pen") and hasattr(item, "setPen"):
                    pen = item.pen()
                    pen.setWidthF(max(1.0, min(50.0, pen.widthF() + step)))
                    item.setPen(pen)
                scene.annotation_handles.update_positions()
                self._toolbar.sync_options_from_item(item)
                event.accept()
                return
        # --------------------------------
        # Nothing selected
        # -> subclass-specific behavior
        # --------------------------------
        self._wheel_without_selection(event)

    def _wheel_without_selection(self, event):
        """
        TO be overide.
        """
        super().wheelEvent(event)
