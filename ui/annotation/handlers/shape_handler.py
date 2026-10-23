from ui.annotation.styles import make_pen, make_shape_brush
from ui.models.tools import AnnotationHandler, ShapeType
from PyQt6.QtGui import QPen
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
from PyQt6.QtCore import QPointF, QRectF, Qt


class ShapeHandler(AnnotationHandler):

    ITEM_TYPES = {
        ShapeType.RECT: QGraphicsRectItem,
        ShapeType.ELLIPSE: QGraphicsEllipseItem,
    }

    def start(self, pos, options):
        item_class = self.ITEM_TYPES.get(options.shape)

        if item_class is None:
            return None

        item = item_class(QRectF(pos, pos))
        if options.fill:
            item.setPen(QPen(Qt.PenStyle.NoPen))
            item.setBrush(make_shape_brush(options))
        else:
            item.setPen(make_pen(options))

        return item

    def update(self, item, start_pos, current_pos):
        item.setRect(QRectF(start_pos, current_pos).normalized())

    def update(self, item, start_pos, current_pos):
        rect = QRectF(start_pos, current_pos).normalized()
        item.setRect(rect)

    def is_valid(self, item, start_pos, end_pos):
        rect = item.rect()
        return rect.width() >= 5.0 and rect.height() >= 5.0

    def resize_to(self, role, scene_pos):
        item = self.item
        if isinstance(
            item,
            (QGraphicsRectItem, QGraphicsEllipseItem),
        ):
            rect = item.sceneBoundingRect()
            if role == "top_left":
                rect.setTopLeft(scene_pos)
            elif role == "top_right":
                rect.setTopRight(scene_pos)
            elif role == "bottom_left":
                rect.setBottomLeft(scene_pos)
            elif role == "bottom_right":
                rect.setBottomRight(scene_pos)
            rect = rect.normalized()
            local_rect = item.mapFromScene(rect).boundingRect()
            item.setRect(local_rect)
            self.update_positions()

    def constrain(self, start_pos, current_pos, modifiers):
        if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
            return current_pos
        dx = current_pos.x() - start_pos.x()
        dy = current_pos.y() - start_pos.y()
        # Keep the smaller drag dimension
        size = min(abs(dx), abs(dy))
        # size = (abs(dx) + abs(dy)) / 2
        # Preserve drag direction
        x = start_pos.x() + size if dx >= 0 else start_pos.x() - size
        y = start_pos.y() + size if dy >= 0 else start_pos.y() - size
        return QPointF(x, y)
