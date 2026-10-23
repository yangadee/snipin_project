from PyQt6.QtCore import QRectF, QPointF, QLineF
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsRectItem, QGraphicsEllipseItem


class AddAnnotationCommand(QUndoCommand):
    def __init__(self, scene, item):
        super().__init__("Add annotation")
        self.scene = scene
        self.item = item
        self._first_redo = True

    def undo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)

    def redo(self):
        # Item was already added while drawing
        if self._first_redo:
            self._first_redo = False
            return
        if self.item.scene() is None:
            self.scene.addItem(self.item)


class DeleteAnnotationCommand(QUndoCommand):
    def __init__(self, scene, item):
        super().__init__("Delete annotation")
        self.scene = scene
        self.item = item

    def redo(self):
        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)

    def undo(self):
        if self.item.scene() is None:
            self.scene.addItem(self.item)


class MoveAnnotationCommand(QUndoCommand):

    def __init__(self, annotation_handles, item, old_pos, new_pos):
        super().__init__("Move annotation")

        self.annotation_handles = annotation_handles
        self.item = item

        self.old_pos = QPointF(old_pos)
        self.new_pos = QPointF(new_pos)

    def undo(self):
        self.item.setPos(self.old_pos)

        if self.annotation_handles.item is self.item:
            self.annotation_handles.update_positions()

    def redo(self):
        self.item.setPos(self.new_pos)

        if self.annotation_handles.item is self.item:
            self.annotation_handles.update_positions()


class ResizeAnnotationCommand(QUndoCommand):

    def __init__(self, handles, item, old_geometry, new_geometry):
        super().__init__("Resize annotation")

        self.handles = handles
        self.item = item
        self.old_geometry = old_geometry
        self.new_geometry = new_geometry

        self._first_redo = True

    def _apply(self, geometry):
        if isinstance(self.item, QGraphicsLineItem):
            self.item.setLine(QLineF(geometry))

        elif isinstance(self.item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            self.item.setRect(QRectF(geometry))

        # elif isinstance(self.item, ArrowItem):
        #     start, end = geometry

        #     self.item.set_line(
        #         start,
        #         end,
        #     )

        if self.handles.item is self.item:
            self.handles.update_positions()

    def undo(self):
        self._apply(self.old_geometry)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return

        self._apply(self.new_geometry)
