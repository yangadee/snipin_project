# ui/annotation/style.py

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPen


def make_pen(options) -> QPen:
    color = QColor(options.color)
    color.setAlphaF(options.opacity / 100.0)

    return QPen(
        color,
        options.width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )


def make_shape_brush(options) -> QBrush:
    if not options.fill:
        return QBrush(Qt.BrushStyle.NoBrush)

    color = QColor(options.fill_color)
    color.setAlphaF(options.fill_opacity / 100.0)

    return QBrush(color)
