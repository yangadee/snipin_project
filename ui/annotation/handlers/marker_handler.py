from ui.annotation.styles import make_pen, make_shape_brush
from ui.models.tools import AnnotationHandler
from PyQt6.QtGui import QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsLineItem
from PyQt6.QtCore import QLineF


class MarkerHandler(AnnotationHandler):
    def start(self, pos, options):
        item = QGraphicsLineItem(QLineF(pos, pos))
        item.setPen(make_pen(options))
        return item

    def update(self, item, start_pos, current_pos):
        item.setLine(QLineF(start_pos, current_pos))

    def is_valid(self, item, start_pos, end_pos):
        return QLineF(start_pos, end_pos).length() >= 5.0

    def resize_to(self, role, scene_pos):
        item = self.item  # type: ignore
        if isinstance(item, QGraphicsLineItem):
            local_pos = item.mapFromScene(scene_pos)
            line = item.line()
            if role == "start":
                line.setP1(local_pos)
            elif role == "end":
                line.setP2(local_pos)
            item.setLine(line)
            self.update_positions()  # type: ignore
