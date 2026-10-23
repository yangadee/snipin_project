from PyQt6.QtCore import Qt, QPointF, QLineF, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QPainter,
    QPen,
    QPixmap,
    QUndoStack,
)
from PyQt6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
)

from ui.annotation.items import AnnotationHandles

from ui.models.tools import Tool
from ui.models.tool_state import ToolState
from ui.models.annotation import ANNOTATION_DATA, AnnotationData
from .commands import (
    AddAnnotationCommand,
    DeleteAnnotationCommand,
    MoveAnnotationCommand,
    ResizeAnnotationCommand,
)


def make_brush_cursor(diameter: int, color=QColor(0, 120, 215)) -> QCursor:
    diameter = max(2, int(diameter))
    # Extra pixels so the outline is not clipped.
    padding = 2
    size = diameter + padding * 2
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(color, 1))
    painter.drawEllipse(padding, padding, diameter - 1, diameter - 1)
    painter.end()
    # Actual drawing point = center of brush.
    center = size // 2
    return QCursor(pixmap, center, center)


class ImageScene(QGraphicsScene):
    tool_changed = pyqtSignal(object)  # emit to viewport

    def __init__(
        self,
        pixmap: QPixmap | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.bg_item: QGraphicsPixmapItem | None = None
        # self.bg_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        if pixmap is not None:
            self.set_pixmap(pixmap)

        # self.setSceneRect(QRectF(pixmap.rect()))

        # self.bg_item = self.addPixmap(pixmap)
        # self.bg_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        # self.bg_item.setZValue(0)

        self.tool = Tool.SELECT

        self.start_pos = QPointF()
        self.current_item = None
        self.tool_state = None
        self.tool_specs = None
        self.annotation_handles = AnnotationHandles(self)

        self.active_handle = None

        self.moving_annotation = False
        self.move_start_pos = QPointF()
        self.move_item_start_pos = QPointF()

        self.undo_stack = QUndoStack(self)

        self.current_item = None
        self.active_handle = None

        self.moving_annotation = False
        self.move_start_pos = QPointF()
        self.move_item_start_pos = QPointF()
        self.resize_old_geometry = None
        # existing...
        # for shift modifier.
        self._annotation_mouse_pos = None

    def set_pixmap(self, pixmap: QPixmap) -> None:
        if self.bg_item is None:
            self.bg_item = self.addPixmap(pixmap)
            self.bg_item.setZValue(0)
            self.bg_item.setTransformationMode(
                Qt.TransformationMode.SmoothTransformation
            )

        else:
            self.bg_item.setPixmap(pixmap)
        self.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.bg_item.setPos(0, 0)
        self.pixmap = pixmap

        # self.setSceneRect(QRectF(pixmap.rect()))         # Update scene size

    @staticmethod
    def _clone_item(item, offset=QPointF()):
        if isinstance(item, QGraphicsLineItem):
            line = item.mapToScene(item.line().p1()), item.mapToScene(item.line().p2())
            clone = QGraphicsLineItem(
                QLineF(
                    line[0] - offset,
                    line[1] - offset,
                )
            )
            clone.setPen(item.pen())
        elif isinstance(item, QGraphicsEllipseItem):
            scene_rect = item.mapRectToScene(item.rect())
            clone = QGraphicsEllipseItem(scene_rect.translated(-offset))
            clone.setPen(item.pen())
            clone.setBrush(item.brush())
        elif isinstance(item, QGraphicsRectItem):
            scene_rect = item.mapRectToScene(item.rect())
            clone = QGraphicsRectItem(scene_rect.translated(-offset))
            clone.setPen(item.pen())
            clone.setBrush(item.brush())
        else:
            return None
        clone.setZValue(item.zValue())
        clone.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        clone.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        return clone

    # ========================================================
    # Tool state
    # ========================================================
    # def set_tool(self, tool):
    #     self.tool = Tool(tool)

    def current_options(self):
        if not self.tool_state:
            return None
        return self.tool_state.options

    def current_handler(self):
        spec = self.tool_specs[self.tool_state.tool]
        if spec.handler is None:
            return None
        return spec.handler

    def set_tool_state(self, state: ToolState):
        self.tool_state = state
        self.tool = self.tool_state.tool
        self.clear_annotation_selection()
        self.tool_changed.emit(self.tool_state.tool)

    def set_tool_specs(self, tool_specs):
        self.tool_specs = tool_specs

    @property
    def selected_annotation(self):
        return self.annotation_handles.item

    def select_annotation(self, item):
        if item is None:
            self.clear_annotation_selection()
            return
        self.annotation_handles.attach(item)

    def clear_annotation_selection(self):
        # item = self.annotation_handles.item
        # if item is not None:
        #     item.setSelected(False)
        #     item.clearFocus()
        self.clearSelection()
        self.clearFocus()
        self.annotation_handles.detach()

    def has_annotation_selection(self) -> bool:
        item = self.annotation_handles.item
        return item is not None and item.scene() is self

    def delete_selected_annotation(self) -> bool:
        """
        not used.
        """
        item = self.annotation_handles.item
        if item is None or item.scene() is not self or not item.data(ANNOTATION_DATA):
            return False
        self.clear_annotation_selection()
        self.undo_stack.push(DeleteAnnotationCommand(self, item))
        return True

    def annotation_at(self, pos):
        if not self.views():
            return None
        item = self.itemAt(pos, self.views()[0].transform())
        if item is None:
            return None
        # Handle may be a child/helper belonging to annotation
        while item is not None:
            # if item.data(ANNOTATION_ITEM) and item.data(EDITABLE_ITEM):
            #     return item
            data = item.data(ANNOTATION_DATA)
            if data is not None and data.editable:
                return item
            item = item.parentItem()
        return None

    def has_annotation_interaction_at(self, pos: QPointF) -> bool:
        """
        Pinview calls to check annotation interaction
        """
        # Selected annotation resize handle
        if self.annotation_handles.handle_at(pos) is not None:
            return True
        # Selected annotation body
        item = self.annotation_handles.item
        if item is not None and item.scene() is self:
            local_pos = item.mapFromScene(pos)
            if item.contains(local_pos):
                return True
        # Any selectable annotation
        return self.annotation_at(pos) is not None

    # ========================================================
    # Create
    # ========================================================

    def _start_annotation(self, start_pos):
        spec = self.tool_specs[self.tool_state.tool]
        handler = spec.handler
        if handler is None:
            return None
        # Handler can optionally obtain scene context

        handler.prepare(self)
        item = handler.start(start_pos, spec.options)
        if item is None:
            return None
        # item.setData(ANNOTATION_ITEM, True)
        # item.setData(EDITABLE_ITEM, handler.is_editable(item))
        item.setData(
            ANNOTATION_DATA,
            AnnotationData(
                tool=self.tool_state.tool,
                editable=handler.is_editable(item),
            ),
        )
        item.setZValue(20)
        self.addItem(item)
        return item

    def _update_annotation(self, item, start_pos, current_pos, modifiers):
        """
        update_annotation with constrain
        """
        spec = self.tool_specs[self.tool_state.tool]
        handler = spec.handler
        if handler is None:
            return
        current_pos = handler.constrain(start_pos, current_pos, modifiers)
        handler.update(item, start_pos, current_pos)

    def _finish_annotation(self, item, end_pos):
        """
        ├── validate size
        ├── discard if too small
        └── prepare item for editing
        """

        spec = self.tool_specs[self.tool_state.tool]
        if spec.handler is None:
            return
        handler = spec.handler
        if handler is None:
            return False
        if not handler.is_valid(item, self.start_pos, end_pos):
            if item.scene() is self:
                self.removeItem(item)
            return False

        # ----------------------------------
        # Make completed annotation editable
        # ----------------------------------
        # item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

        handler.finish(item, end_pos)
        return True

    """
    Press priority:
    1. resize handle
    2. move currently selected annotation
    3. select annotation
    4. start drawing
    5. default Qt handling

    Move:
    1. resizing
    2. moving
    3. drawing
    4. default

    Release:
    1. finish resize
    2. finish move
    3. finish drawing
    4. default
    """

    # ========================================================
    # Mouse
    # ========================================================
    def _try_start_resize(self, pos: QPointF) -> bool:
        role = self.annotation_handles.handle_at(pos)
        if role is None:
            return False
        self.active_handle = role
        self.resize_old_geometry = self.annotation_handles.geometry()
        return True

    def _try_start_move(self, pos: QPointF) -> bool:
        item = self.annotation_handles.item
        if item is None or item.scene() is not self:
            return False
        local_pos = item.mapFromScene(pos)
        if not item.contains(local_pos):
            return False
        self.moving_annotation = True
        self.move_start_pos = QPointF(pos)
        self.move_item_start_pos = QPointF(item.pos())
        return True

    def _try_select_annotation(self, pos: QPointF) -> bool:
        item = self.annotation_at(pos)
        if item is None:
            return False
        self.select_annotation(item)
        # item.setFocus() # only for keyboard
        # Qt selection state
        item.setSelected(True)

        # Immediately allow drag
        self.moving_annotation = True
        self.move_start_pos = QPointF(pos)
        self.move_item_start_pos = QPointF(item.pos())
        return True

    def _try_start_drawing(self, pos: QPointF) -> bool:
        # New drawing means previous annotation
        # is no longer being edited.
        self.clear_annotation_selection()
        item = self._start_annotation(pos)
        if item is None:
            return False
        self.current_item = item
        return True

    def mousePressEvent(self, event):

        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        pos = event.scenePos()
        self.start_pos = pos
        self.active_handle = None
        self.moving_annotation = False
        # Ordered interaction priority
        # ==================================================
        # 1. Selected annotation resize handle
        # ==================================================
        if self._try_start_resize(pos):
            event.accept()
            return
        # ==================================================
        # 2. Currently selected annotation
        # ==================================================
        if self._try_start_move(pos):
            event.accept()
            return
        # ==================================================
        # 3. SELECT tool
        # ==================================================
        if self.tool == Tool.SELECT:
            if self._try_select_annotation(pos):
                event.accept()
                return
            self.clear_annotation_selection()
            event.accept()
            return
        # ==================================================
        # 4. Drawing
        # ==================================================
        if self._try_start_drawing(pos):
            event.accept()
            return
        super().mousePressEvent(event)

    def _mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self.start_pos = event.scenePos()
        # Reset transient interaction state
        self.active_handle = None
        self.moving_annotation = False
        # ==================================================
        # 1. Resize handle
        #    Available in ALL tool modes
        # ==================================================
        role = self.annotation_handles.handle_at(self.start_pos)
        if role is not None:
            self.active_handle = role
            # Save geometry for undo
            self.resize_old_geometry = self.annotation_handles.geometry()
            event.accept()
            return

        # ==================================================
        # 2. Currently selected annotation
        #    Can move in ALL tool modes
        # ==================================================
        selected_item = self.annotation_handles.item
        if selected_item is not None and selected_item.scene() is self:
            local_pos = selected_item.mapFromScene(self.start_pos)
            if selected_item.contains(local_pos):
                self.moving_annotation = True
                # Save initial mouse/item positions
                self.move_start_pos = QPointF(self.start_pos)
                self.move_item_start_pos = QPointF(selected_item.pos())
                event.accept()
                return
        # ==================================================
        # 3. SELECT tool
        #    Select another annotation
        # ==================================================
        if self.tool == Tool.SELECT:
            item = self.annotation_at(self.start_pos)
            if item is not None:
                self.select_annotation(item)
                # Immediately allow dragging newly selected item
                self.moving_annotation = True
                self.move_start_pos = QPointF(self.start_pos)
                self.move_item_start_pos = QPointF(item.pos())
                event.accept()
                return
            # Clicked empty space
            self.clear_annotation_selection()
            event.accept()
            return

        # ==================================================
        # 4. DRAW
        # Starting a new annotation -> remove old handles
        # ==================================================
        self.clear_annotation_selection()
        self.current_item = self._start_annotation(self.start_pos)
        if self.current_item is not None:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        current_pos = event.scenePos()

        # ==================================================
        # 1. Resize selected annotation
        # ==================================================
        if self.active_handle is not None:
            self.annotation_handles.resize(self.active_handle, current_pos)
            event.accept()
            return

        # ==================================================
        # 2. Move selected annotation
        # ==================================================
        if self.moving_annotation:
            item = self.annotation_handles.item
            if item is not None:
                delta = current_pos - self.move_start_pos
                item.setPos(self.move_item_start_pos + delta)
                self.annotation_handles.update_positions()
            event.accept()
            return

        # ==================================================
        # 3. Creating new annotation
        # ==================================================
        if self.current_item is not None:
            self._annotation_mouse_pos = event.scenePos()
            self._update_annotation(
                self.current_item,
                self.start_pos,
                current_pos,
                event.modifiers(),
            )

            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)
        current_pos = event.scenePos()
        # ==================================================
        # 1. Finish resize
        # ==================================================
        if self.active_handle is not None:
            self.active_handle = None
            item = self.annotation_handles.item
            if item is not None:
                new_geometry = self.annotation_handles.geometry()
                if self.resize_old_geometry != new_geometry:
                    self.undo_stack.push(
                        ResizeAnnotationCommand(
                            self.annotation_handles,
                            item,
                            self.resize_old_geometry,
                            new_geometry,
                        )
                    )
            self.annotation_handles.update_positions()
            event.accept()
            return

        # ==================================================
        # 2. Finish move
        # ==================================================
        if self.moving_annotation:
            self.moving_annotation = False
            item = self.annotation_handles.item
            if item is not None:
                old_pos = self.move_item_start_pos
                new_pos = item.pos()
                if old_pos != new_pos:
                    self.undo_stack.push(
                        MoveAnnotationCommand(
                            self.annotation_handles, item, old_pos, new_pos
                        )
                    )
            self.annotation_handles.update_positions()

            event.accept()
            return
        # ==================================================
        # 3. Finish new annotation
        # ==================================================
        if self.current_item is not None:
            item = self.current_item
            self.current_item = None
            handler = self.current_handler()
            if self._finish_annotation(item, current_pos):
                if handler is not None and handler.is_editable(item):
                    self.select_annotation(item)
                else:
                    self.clear_annotation_selection()
                self.undo_stack.push(AddAnnotationCommand(self, item))

            event.accept()
            return

        # ==================================================
        # 4. Normal scene handling
        # ==================================================
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        # ==================================================
        # Shift -> change item shape
        # ==================================================
        key = event.key()
        if (
            event.key() == Qt.Key.Key_Shift
            and self.current_item is not None
            and self._annotation_mouse_pos is not None
        ):
            self._update_annotation(
                self.current_item,
                self.start_pos,
                self._annotation_mouse_pos,
                event.modifiers(),
            )

            event.accept()
            return
        # ==================================================
        # ESC -> deselect annotation
        # ==================================================
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if self.annotation_handles.item is not None:
                self.clear_annotation_selection()
                event.accept()
                return
        # ==================================================
        # DELETE -> delete selected annotation
        # ==================================================
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            item = self.annotation_handles.item
            # If text or node are editing, just continue...
            if item is not None and hasattr(item, "is_editing"):
                if item.is_editing():
                    return super().keyPressEvent(event)
            if item is not None and item.scene() is self and item.data(ANNOTATION_DATA):
                # Remove handles FIRST because they reference item
                self.clear_annotation_selection()
                self.undo_stack.push(DeleteAnnotationCommand(self, item))
                event.accept()
                return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Shift
            and self.current_item is not None
            and self._annotation_mouse_pos is not None
        ):
            self._update_annotation(
                self.current_item,
                self.start_pos,
                self._annotation_mouse_pos,
                event.modifiers(),
            )
            event.accept()
            return
        super().keyReleaseEvent(event)

    def undo(self):
        self.clear_annotation_selection()
        self.undo_stack.undo()

    def redo(self):
        self.clear_annotation_selection()
        self.undo_stack.redo()


# class GrabScene(ImageScene):
#     selectionFinished = pyqtSignal()
#     selectionGeometryChanged = pyqtSignal(QRectF)
#     cursorRequested = pyqtSignal(object)
#     cursorRestoreRequested = pyqtSignal()
#     selectionMouseMoved = pyqtSignal(QPointF, QPoint)

#     def __init__(
#         self,
#         pixmap: QPixmap | None = None,
#         parent=None,
#     ):
#         super().__init__(pixmap, parent)
#         self.tool = Tool.SELECT
#         self.selection = None

#         # dim
#         self.dim = DimItem(self.sceneRect())
#         self.addItem(self.dim)
#         self.dim.setZValue(15)  # Between pixmap and items

#         self._creating_selection = False
#         self._selection_start = QPointF()
#         # frozen system cursor
#         self._frozen_cursor_item: QGraphicsPixmapItem | None = None
#         self._frozen_cursor_visible = False

#     @property
#     def is_selecting(self) -> bool:
#         return self._creating_selection

#     def set_pixmap(self, pixmap: QPixmap) -> None:
#         super().set_pixmap(pixmap)
#         self.dim.setRect(self.sceneRect())

#     def _set_pixmap(self, pixmap):
#         if pixmap.isNull():
#             return
#         self.pixmap = pixmap
#         # Replace background image
#         self.bg_item.setPixmap(pixmap)
#         self.bg_item.setZValue(0)
#         # Background always starts at scene 0,0
#         self.bg_item.setPos(0, 0)
#         # Update scene size
#         self.setSceneRect(QRectF(pixmap.rect()))
#         # self.update()

#     def clear_selection(self):
#         """
#         Clear selection & All items for re-select.
#         Set dim full scene rect.
#         """
#         for item in self.items():
#             if item not in (self.bg_item, self.dim, self._frozen_cursor_item):
#                 self.removeItem(item)
#         self.selection = None
#         self.dim.set_selection_rect(QRectF())

#     def reset_selection(self):
#         """
#         Ready to start selection
#         """
#         self.clear_selection()
#         self.clear_annotation_selection()
#         self._creating_selection = False
#         self._selection_start = QPointF()

#     def mousePressEvent(self, event):
#         if event.button() != Qt.MouseButton.LeftButton:
#             return super().mousePressEvent(event)
#         pos = event.scenePos()
#         # --------------------------------------------------
#         # Existing selection always has priority
#         # --------------------------------------------------
#         if self.selection:
#             item = self.itemAt(pos, self.views()[0].transform())
#             # Selection itself OR one of its child handles
#             if item is self.selection or self.selection.isAncestorOf(item):
#                 return QGraphicsScene.mousePressEvent(self, event)
#         # --------------------------------------------------
#         # Annotation tool
#         # Let ImageScene handle PEN / LINE / SHAPE / etc.
#         # Annotation may only START inside the selection.
#         # --------------------------------------------------
#         if self.tool != Tool.SELECT:
#             if self.selection:
#                 selection_rect = self.selection.scene_selection_rect().normalized()
#             if not selection_rect.contains(pos):
#                 self.clear_annotation_selection()
#                 event.accept()
#                 return
#             return super().mousePressEvent(event)
#         # --------------------------------------------------
#         # Existing selection
#         # Don't create another selection
#         # --------------------------------------------------
#         if self.selection:
#             return super().mousePressEvent(event)
#         # --------------------------------------------------
#         # Create selection
#         # --------------------------------------------------
#         self._selection_start = pos
#         self.selection = SelectionRect(QRectF(pos, pos))
#         self.selection.setZValue(200)
#         self.addItem(self.selection)
#         self.selection.signals.geometryChanged.connect(self._selection_changed)
#         self.selection.signals.cursorRequested.connect(self.cursorRequested)
#         self.selection.signals.cursorRestoreRequested.connect(
#             self.cursorRestoreRequested
#         )

#         self._creating_selection = True
#         event.accept()

#     def _selection_changed(self, rect):
#         # self.update()
#         self.dim.set_selection_rect(rect)
#         self.selectionGeometryChanged.emit(rect)

#     def mouseMoveEvent(self, event):
#         if self.tool == Tool.SELECT and self._creating_selection and self.selection:
#             # old_rect = self.selection.sceneBoundingRect()
#             rect = QRectF(self._selection_start, event.scenePos()).normalized()

#             # self.selection.setRect(rect)
#             self.selection.set_selection_rect(rect)
#             # self.dim.set_selection_rect(rect)
#             # new_rect = self.selection.sceneBoundingRect()
#             # # Dity region: Include both old + new location
#             # dirty = old_rect.united(new_rect).adjusted(-2, -2, 2, 2)
#             # self.update(dirty)
#             self.selectionMouseMoved.emit(event.scenePos(), event.screenPos())

#             event.accept()
#             return

#         super().mouseMoveEvent(event)

#     def mouseReleaseEvent(self, event):
#         if self.tool == Tool.SELECT and self._creating_selection:
#             rect = QRectF(self._selection_start, event.scenePos()).normalized()
#             if rect.width() < 20 and rect.height() < 20:
#                 self.removeItem(self.selection)
#                 self.selection = None
#             else:
#                 self.selection.set_selection_rect(rect)
#                 self.selection.set_finished(True)  # show handles

#             self.selectionFinished.emit()
#             self._creating_selection = False
#             self.update()
#             event.accept()
#             return
#         super().mouseReleaseEvent(event)

#     # ========================================================
#     # Dim area
#     # ========================================================
#     def _drawForeground(self, painter, rect):
#         super().drawForeground(painter, rect)
#         path = QPainterPath()
#         path.addRect(self.sceneRect())
#         if self.selection:
#             hole = QPainterPath()
#             hole.addRect(self.selection.scene_outer_rect())  # <- use scene_outer_rect
#             path = path.subtracted(hole)
#         painter.fillPath(path, QColor(0, 0, 0, 110))

#     # ========================================================
#     # Create PinScene in Scene, not Pin
#     # ========================================================
#     def create_pin_scene(self) -> PinScene:
#         if not self.selection:
#             return None
#         rect = self.selection.scene_selection_rect().normalized()
#         pixmap = self.pixmap.copy(rect.toAlignedRect())
#         scene = PinScene(pixmap)
#         self.copy_annotations_to(scene, rect)
#         return scene

#     def _copy_annotations_to(self, target_scene, source_rect):
#         # ----------------------------------------------------
#         # 2. Clone annotations
#         # ----------------------------------------------------
#         for item in self.items(Qt.SortOrder.AscendingOrder):
#             # don't duplicate screenshot / selection rect
#             if item in (self.pixmap, self.selection):
#                 continue
#             # only items touching selection
#             if not item.sceneBoundingRect().intersects(source_rect):
#                 continue
#             new_item = self.clone_item(item)
#             if new_item is None:
#                 continue
#             new_item.setPos(new_item.pos() - source_rect.topLeft())
#             target_scene.addItem(new_item)
#         return target_scene

#     def copy_annotations_to(self, target_scene, source_rect: QRectF):
#         source_rect = source_rect.normalized()
#         for item in self.items(Qt.SortOrder.AscendingOrder):
#             # Only annotations.
#             # Automatically excludes:
#             #   bg_item
#             #   dim
#             #   selection
#             #   resize handles
#             #   size labels
#             if not item.data(ANNOTATION_DATA):
#                 continue
#             if not item.sceneBoundingRect().intersects(source_rect):
#                 continue
#             new_item = self.clone_item(item)
#             if new_item is None:
#                 continue
#             self._copy_item_properties(item, new_item)
#             new_item.setPos(item.scenePos() - source_rect.topLeft())
#             target_scene.addItem(new_item)
#         return target_scene

#     def _copy_item_properties(self, source, target):
#         target.setZValue(source.zValue())
#         target.setRotation(source.rotation())
#         target.setScale(source.scale())
#         target.setVisible(source.isVisible())
#         target.setTransformOriginPoint(source.transformOriginPoint())
#         target.setOpacity(source.opacity())
#         # target.setData(ANNOTATION_ITEM, True)
#         # target.setData(EDITABLE_ITEM, True)

#     def clone_item(self, item):

#         # ----------------------------------
#         # Arrow
#         # MUST come before QGraphicsLineItem
#         # ----------------------------------
#         if isinstance(item, ArrowItem):
#             clone = ArrowItem(QLineF(item.line()))
#             clone.setPen(QPen(item.pen()))
#             return clone

#         # ----------------------------------
#         # Line / Marker
#         # ----------------------------------
#         if isinstance(item, QGraphicsLineItem):
#             clone = QGraphicsLineItem(QLineF(item.line()))
#             clone.setPen(QPen(item.pen()))
#             return clone

#         # ----------------------------------
#         # Rectangle
#         # ----------------------------------
#         if isinstance(item, QGraphicsRectItem):
#             clone = QGraphicsRectItem(QRectF(item.rect()))
#             clone.setPen(QPen(item.pen()))
#             clone.setBrush(QBrush(item.brush()))
#             return clone

#         # ----------------------------------
#         # Ellipse
#         # ----------------------------------
#         if isinstance(item, QGraphicsEllipseItem):
#             clone = QGraphicsEllipseItem(QRectF(item.rect()))
#             clone.setPen(QPen(item.pen()))
#             clone.setBrush(QBrush(item.brush()))
#             return clone

#         # ----------------------------------
#         # Freehand path
#         # ----------------------------------
#         if isinstance(item, QGraphicsPathItem):
#             clone = QGraphicsPathItem(QPainterPath(item.path()))
#             clone.setPen(QPen(item.pen()))
#             clone.setBrush(QBrush(item.brush()))
#             return clone

#         # ----------------------------------
#         # Text
#         # ----------------------------------
#         if isinstance(item, EditableTextItem):
#             clone = EditableTextItem(
#                 placeholder=item.toPlainText(),
#                 font_size=item.font().pointSize(),
#                 color=item.defaultTextColor(),
#                 font_family=item.font().family(),
#             )
#             clone.setPlainText(item.toPlainText())

#             clone.setFont(QFont(item.font()))
#             clone.setDefaultTextColor(QColor(item.defaultTextColor()))
#             if hasattr(clone, "disable_editing"):
#                 clone.disable_editing()
#             return clone

#         # ----------------------------------
#         # Node
#         # ----------------------------------
#         if isinstance(item, CustomNode):
#             return CustomNode(
#                 text=item.text,
#                 shape_type=item.shape_type,
#                 color=item.color,
#                 size=item.size(),
#                 opacity=item.opacity_value,
#             )

#         # ----------------------------------
#         # Mosaic / Blur
#         # Frozen raster clone
#         # ----------------------------------
#         if isinstance(item, EffectItem):
#             clone = QGraphicsPixmapItem(QPixmap(item.pixmap()))
#             clone.setShapeMode(item.shapeMode())
#             clone.setTransformationMode(item.transformationMode())
#             return clone

#         # ----------------------------------
#         # QGraphicsPixmapItem
#         # Includes frozen system cursor
#         # ----------------------------------
#         if isinstance(item, QGraphicsPixmapItem):
#             print("clone pixmap item")
#             clone = QGraphicsPixmapItem(QPixmap(item.pixmap()))
#             clone.setOffset(item.offset())
#             clone.setZValue(item.zValue())
#             clone.setShapeMode(item.shapeMode())
#             clone.setTransformationMode(item.transformationMode())
#             return clone

#         return None

#     def set_selection_rect(self, rect: QRectF, finished: bool = True):
#         """
#         Set the selection_area rect by grabscene.
#         """
#         rect = rect.normalized().intersected(self.sceneRect())
#         if rect.isEmpty():
#             return
#         if self.selection is None:
#             self.selection = SelectionRect(rect)
#             self.selection.setZValue(200)
#             self.addItem(self.selection)
#             self.selection.signals.geometryChanged.connect(self._selection_changed)
#             # Initial geometry wasn't emitted
#             self._selection_changed(self.selection.scene_selection_rect())
#         else:
#             self.selection.set_selection_rect(rect)
#         # Must apply to BOTH new and existing selection
#         self.selection.set_finished(finished)

#     # =================================================
#     # Frozen system cursor
#     # =================================================
#     def set_frozen_cursor(self, cursor, virtual_rect: QRect) -> None:
#         if cursor is None:
#             self.remove_frozen_cursor()
#             return
#         cursor_pixmap, cursor_pos, hotspot = cursor
#         if self._frozen_cursor_item is None:
#             self._frozen_cursor_item = QGraphicsPixmapItem()
#             self._frozen_cursor_item.setZValue(1)
#             self._frozen_cursor_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
#             self._frozen_cursor_item.setAcceptHoverEvents(False)
#             self._frozen_cursor_item.setData(
#                 ANNOTATION_DATA, AnnotationData(tool=None, editable=False)
#             )
#             self._frozen_cursor_item.setFlag(
#                 QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False
#             )
#             self._frozen_cursor_item.setFlag(
#                 QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False
#             )
#         self._frozen_cursor_item.setPixmap(cursor_pixmap)
#         pos = cursor_pos - hotspot - virtual_rect.topLeft()
#         self._frozen_cursor_item.setPos(QPointF(pos))
#         # Add only if currently detached from a scene.
#         if self._frozen_cursor_item.scene() is None:
#             self.addItem(self._frozen_cursor_item)
#             self._frozen_cursor_item.setVisible(self._frozen_cursor_visible)

#     def set_frozen_cursor_visible(self, visible: bool) -> None:
#         self._frozen_cursor_visible = visible
#         if self._frozen_cursor_item is not None:
#             self._frozen_cursor_item.setVisible(visible)

#     def remove_frozen_cursor(self) -> None:
#         if self._frozen_cursor_item is None:
#             return
#         self.removeItem(self._frozen_cursor_item)
#         self._frozen_cursor_item = None
