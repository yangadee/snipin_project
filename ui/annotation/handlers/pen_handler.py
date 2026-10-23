from ui.annotation.styles import make_pen
from ui.models.tools import AnnotationHandler
from PyQt6.QtWidgets import QGraphicsPathItem
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPixmap
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt


class PenHandler(AnnotationHandler):
    def start(self, pos, options):
        path = QPainterPath(pos)
        # Make first click visible
        path.lineTo(pos + QPointF(0.01, 0.01))
        item = QGraphicsPathItem(path)
        item.setPen(make_pen(options))
        return item

    def update(self, item, start_pos, current_pos):
        path = item.path()
        path.lineTo(current_pos)
        item.setPath(path)
