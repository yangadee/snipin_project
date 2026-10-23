from __future__ import annotations


import math
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)
from ui.models.tools import NodeShape


class NodeTextEditor(QGraphicsTextItem):
    def __init__(self, node):
        super().__init__(node)
        self.node = node
        self.setDefaultTextColor(node._contrast_text_color(node._color))
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.node.finish_text_editing()


class CustomNode(QGraphicsItem):
    """
    Numbered annotation node.

    The item's local origin (0, 0) is always its center.

    Example:
        node = CustomNode(
            text="1",
            shape_type=NodeShape.CIRCLE,
            color=QColor("#ff3b30"),
            size=32.0,
        )

        node.setPos(scene_pos)
        scene.addItem(node)
    """

    MIN_SIZE = 16.0
    MAX_SIZE = 200.0
    BORDER_WIDTH = 2.0

    def __init__(
        self,
        text: str = "1",
        shape_type: NodeShape = NodeShape.CIRCLE,
        color: QColor | str = QColor("#ff3b30"),
        size: float = 32.0,
        opacity: float = 1.0,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self._text = str(text)
        self._shape_type = shape_type
        self._color = QColor(color)
        self._size = max(self.MIN_SIZE, min(self.MAX_SIZE, float(size)))
        self._opacity = max(0.0, min(1.0, float(opacity)))
        # Selection is normal Qt selection
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # Movement is handled by your ImageScene
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        # Temporary text editor
        self._text_editor = None

    # =========================================================
    # Text
    # =========================================================

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, text: str):
        text = str(text)
        if self._text == text:
            return
        self._text = text
        self.update()

    # =========================================================
    # Size
    # =========================================================

    def size(self) -> float:
        return self._size

    def set_size(self, size: float):
        size = max(self.MIN_SIZE, min(self.MAX_SIZE, float(size)))
        if self._size == size:
            return
        # boundingRect() will change
        self.prepareGeometryChange()
        self._size = size
        self.update()

    # =========================================================
    # Shape
    # =========================================================

    @property
    def shape_type(self) -> NodeShape:
        return self._shape_type

    def set_shape_type(self, shape_type: NodeShape):
        if self._shape_type == shape_type:
            return

        # Shape changes but its outer bounding rectangle
        # remains the same. prepareGeometryChange() is not
        # necessary here.
        self._shape_type = shape_type

        self.update()

    # =========================================================
    # Color
    # =========================================================

    @property
    def color(self) -> QColor:
        return QColor(self._color)

    def set_color(self, color: QColor | str):
        color = QColor(color)

        if self._color == color:
            return

        self._color = color
        self.update()

    # =========================================================
    # Opacity
    # =========================================================

    @property
    def opacity_value(self) -> float:
        return self._opacity

    def set_opacity_value(self, opacity: float):
        opacity = max(0.0, min(1.0, float(opacity)))

        if self._opacity == opacity:
            return

        self._opacity = opacity
        self.update()

    # =========================================================
    # Geometry
    # =========================================================

    def boundingRect(self) -> QRectF:
        """
        Local geometry centered around (0, 0).
        """

        half = self._size / 2.0

        # Extra border space so antialiasing / outline
        # does not get clipped.
        extra = self.BORDER_WIDTH / 2.0

        return QRectF(
            -half - extra,
            -half - extra,
            self._size + extra * 2.0,
            self._size + extra * 2.0,
        )

    def _hexagon_polygon(self, rect: QRectF) -> QPolygonF:
        center = rect.center()
        rx = rect.width() / 2
        ry = rect.height() / 2
        points = []
        for i in range(6):
            angle = math.radians(60 * i)
            points.append(
                QPointF(
                    center.x() + rx * math.cos(angle),
                    center.y() + ry * math.sin(angle),
                )
            )
        return QPolygonF(points)

    def _node_rect(self) -> QRectF:
        """
        Exact node geometry without border expansion.
        """

        half = self._size / 2.0

        return QRectF(
            -half,
            -half,
            self._size,
            self._size,
        )

    def node_rect(self) -> QRectF:
        return self._node_rect()

    def shape(self) -> QPainterPath:
        """
        Accurate hit-test shape.
        """

        path = QPainterPath()
        rect = self._node_rect()

        if self._shape_type == NodeShape.CIRCLE:
            path.addEllipse(rect)
        elif self._shape_type == NodeShape.HEXAGON:
            path.addPolygon(self._hexagon_polygon(rect))
            path.closeSubpath()
        else:
            path.addRect(rect)

        return path

    # =========================================================
    # Paint
    # =========================================================

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self._node_rect()
        # --------------------------------
        # Node color + opacity
        # --------------------------------
        fill_color = QColor(self._color)
        fill_color.setAlphaF(self._opacity)
        # White outline
        border_pen = QPen(QColor("#ffffff"))
        border_pen.setWidthF(self.BORDER_WIDTH)
        border_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(border_pen)
        painter.setBrush(fill_color)

        # --------------------------------
        # Shape
        # --------------------------------
        if self._shape_type == NodeShape.CIRCLE:
            painter.drawEllipse(rect)
        elif self._shape_type == NodeShape.HEXAGON:
            painter.drawPolygon(self._hexagon_polygon(rect))
        else:
            painter.drawRoundedRect(rect, self._size * 0.15, self._size * 0.15)

        # --------------------------------
        # Text
        # --------------------------------

        if self._text_editor is None:
            font = QFont()
            font.setPointSizeF(max(7.0, self._size * 0.40))
            font.setBold(True)
            painter.setFont(font)
            text_color = self._contrast_text_color(fill_color)
            painter.setPen(text_color)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        # --------------------------------
        # Optional Qt selected indicator
        #
        # Your AnnotationHandles already show
        # selection, so normally don't draw another
        # selection rectangle here.
        # --------------------------------

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_text_editing()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def start_text_editing(self):
        if self._text_editor is not None:
            return
        editor = NodeTextEditor(self)
        self._text_editor = editor
        editor.setPlainText(self._text)
        # Match painted font
        font = QFont()
        font.setPointSizeF(max(7.0, self._size * 0.40))
        font.setBold(True)
        editor.setFont(font)
        editor.setDefaultTextColor(self._contrast_text_color(self._color))

        # Center editor
        editor.adjustSize()
        rect = editor.boundingRect()
        editor.setPos(-rect.width() / 2.0, -rect.height() / 2.0)
        # Give text editor focus
        editor.setFocus(Qt.FocusReason.MouseFocusReason)

        # Select all existing text.
        # Typing immediately replaces it.
        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        editor.setTextCursor(cursor)
        self.update()

    def finish_text_editing(self):
        editor = self._text_editor
        if editor is None:
            return
        text = editor.toPlainText().strip()
        if text:
            self._text = text
        self._text_editor = None
        if editor.scene() is not None:
            editor.scene().removeItem(editor)
        self.update()

    def is_editing(self) -> bool:
        return self._text_editor is not None

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _contrast_text_color(color: QColor) -> QColor:
        """
        Pick black/white text based on approximate luminance.
        """

        luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()

        if luminance > 160:
            return QColor("#000000")

        return QColor("#ffffff")
