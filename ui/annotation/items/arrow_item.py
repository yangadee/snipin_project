import math

from PyQt6.QtCore import QPointF, QRectF, QLineF, Qt
from PyQt6.QtGui import (
    QBrush,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPolygonF,
)
from PyQt6.QtWidgets import QGraphicsLineItem


class ArrowItem(QGraphicsLineItem):
    """
    QGraphicsLineItem with a filled arrow head.

    Compatible with normal line handling:
        item.line()
        item.setLine(...)
        item.pen()
        item.setPen(...)

    Therefore it can share:
        - LineHandler-style update
        - start/end resize handles
        - move logic
        - undo/redo geometry
        - wheel pen-width adjustment
    """

    MIN_ARROW_SIZE = 15.0
    ARROW_SCALE = 4.0

    # Invisible selectable area around the shaft
    HIT_WIDTH = 12.0

    # Arrow-head half angle:
    # 30 degrees on either side
    ARROW_ANGLE = math.pi / 6

    def __init__(
        self,
        line: QLineF | None = None,
        parent=None,
    ):
        super().__init__(
            line if line is not None else QLineF(),
            parent,
        )

    # =========================================================
    # Arrow geometry
    # =========================================================

    def arrow_size(self) -> float:
        """
        Arrow-head size follows line width.

        Examples:
            width 1 -> 15
            width 3 -> 15
            width 5 -> 20
            width 8 -> 32
        """

        return max(
            self.MIN_ARROW_SIZE,
            self.pen().widthF() * self.ARROW_SCALE,
        )

    def arrow_points(
        self,
    ) -> tuple[QPointF, QPointF, QPointF] | None:
        """
        Return:
            tip, left, right

        All points are in item-local coordinates.
        """

        line = self.line()

        if line.length() < 0.01:
            return None

        start = line.p1()
        tip = line.p2()

        angle = math.atan2(
            tip.y() - start.y(),
            tip.x() - start.x(),
        )

        size = self.arrow_size()

        left = QPointF(
            tip.x() - size * math.cos(angle - self.ARROW_ANGLE),
            tip.y() - size * math.sin(angle - self.ARROW_ANGLE),
        )

        right = QPointF(
            tip.x() - size * math.cos(angle + self.ARROW_ANGLE),
            tip.y() - size * math.sin(angle + self.ARROW_ANGLE),
        )

        return tip, left, right

    # =========================================================
    # Bounding rectangle
    # =========================================================

    def boundingRect(self) -> QRectF:
        """
        Must include:
            - shaft
            - line width
            - arrow head
            - hit-test margin
        """

        line = self.line()

        if line.length() < 0.01:
            return super().boundingRect()

        points = self.arrow_points()

        if points is None:
            return super().boundingRect()

        tip, left, right = points

        path = QPainterPath()

        # Shaft
        path.moveTo(line.p1())
        path.lineTo(line.p2())

        # Arrow head
        polygon = QPolygonF(
            [
                tip,
                left,
                right,
            ]
        )

        path.addPolygon(polygon)

        margin = (
            max(
                self.pen().widthF(),
                self.HIT_WIDTH,
            )
            / 2.0
            + 2.0
        )

        return path.boundingRect().adjusted(
            -margin,
            -margin,
            margin,
            margin,
        )

    # =========================================================
    # Hit-test shape
    # =========================================================

    def shape(self) -> QPainterPath:
        """
        Use a wider invisible shaft for easier mouse selection.

        Visible line may be 2-3 px, but hit target can remain
        about 12 px.
        """

        line = self.line()

        if line.length() < 0.01:
            return QPainterPath()

        points = self.arrow_points()

        if points is None:
            return QPainterPath()

        tip, left, right = points

        # --------------------------------
        # Shaft hit area
        # --------------------------------
        shaft = QPainterPath()

        shaft.moveTo(line.p1())

        shaft.lineTo(line.p2())

        stroker = QPainterPathStroker()

        stroker.setWidth(
            max(
                self.HIT_WIDTH,
                self.pen().widthF() + 6.0,
            )
        )

        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)

        shaft_shape = stroker.createStroke(shaft)

        # --------------------------------
        # Arrow head hit area
        # --------------------------------
        head_shape = QPainterPath()

        head_shape.addPolygon(
            QPolygonF(
                [
                    tip,
                    left,
                    right,
                ]
            )
        )

        head_shape.closeSubpath()

        return shaft_shape.united(head_shape)

    # =========================================================
    # Painting
    # =========================================================

    def paint(
        self,
        painter: QPainter,
        option,
        widget=None,
    ):
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        line = self.line()

        if line.length() < 2.0:
            return

        start = line.p1()
        end = line.p2()

        arrow_size = self.arrow_size()

        # =====================================================
        # Shaft
        #
        # Stop the shaft slightly before the tip so it does not
        # visibly extend through the filled arrow head.
        # =====================================================

        shorten = arrow_size * 0.75

        if line.length() > shorten:
            shaft_end = line.pointAt(1.0 - shorten / line.length())
        else:
            shaft_end = end

        painter.setPen(self.pen())

        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawLine(
            start,
            shaft_end,
        )

        # =====================================================
        # Arrow head
        # =====================================================

        points = self.arrow_points()

        if points is None:
            return

        tip, left, right = points

        color = self.pen().color()

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QBrush(color))

        painter.drawPolygon(
            QPolygonF(
                [
                    tip,
                    left,
                    right,
                ]
            )
        )
