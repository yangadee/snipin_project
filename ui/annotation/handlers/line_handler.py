from ui.annotation.items import ArrowItem
from ui.annotation.styles import make_pen
from ui.models.tools import AnnotationHandler, LineType
from PyQt6.QtWidgets import QGraphicsLineItem
from PyQt6.QtCore import QLineF, QPointF, Qt


class LineHandler(AnnotationHandler):
    """
    For Line/arrow/Highlight pen
    """

    def start(self, pos, options):
        if getattr(options, "line_type", None) == LineType.ARROW:
            item = ArrowItem(QLineF(pos, pos))
        else:
            item = QGraphicsLineItem(QLineF(pos, pos))
        item.setPen(make_pen(options))
        return item

    def update(self, item, start_pos, current_pos):
        item.setLine(QLineF(start_pos, current_pos))

    def is_valid(self, item, start_pos, end_pos):
        return QLineF(start_pos, end_pos).length() >= 5.0

    def resize_to(self, role, scene_pos):
        item = self.item
        if isinstance(item, QGraphicsLineItem):
            local_pos = item.mapFromScene(scene_pos)
            line = item.line()
            if role == "start":
                line.setP1(local_pos)
            elif role == "end":
                line.setP2(local_pos)
            item.setLine(line)
            self.update_positions()
            return

    def constrain(self, start_pos, current_pos, modifiers):
        if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
            return current_pos

        dx = current_pos.x() - start_pos.x()
        dy = current_pos.y() - start_pos.y()

        if abs(dx) >= abs(dy):
            return QPointF(current_pos.x(), start_pos.y())

        return QPointF(start_pos.x(), current_pos.y())
