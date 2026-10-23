import os

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
import sys
from PyQt6.QtCore import QObject, Qt, QPointF, QRectF, QLineF, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QBrush,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)


class SelectionSignals(QObject):
    """
    SelectionRect inherits from QGraphicsRectItem, which is not aQObject.
    Therefore a pyqtSignal declared directly on it cannot work as a normal bound Qt signal
    """

    geometryChanged = pyqtSignal(QRectF)
    cursorRequested = pyqtSignal(object)
    cursorRestoreRequested = pyqtSignal()


# ============================================================
# Selection rectangle
# ============================================================
class SelectionRect(QGraphicsRectItem):
    HANDLE_SIZE = 10.0
    NONE = 0
    TOP_LEFT = 1
    TOP = 2
    TOP_RIGHT = 3
    RIGHT = 4
    BOTTOM_RIGHT = 5
    BOTTOM = 6
    BOTTOM_LEFT = 7
    LEFT = 8

    def __init__(self, rect=QRectF()):
        super().__init__(rect.normalized())
        self.setZValue(20)
        self.setPen(QPen(QColor("#00aaff"), 2))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        self.setAcceptHoverEvents(True)
        self._handle = self.NONE
        self._press_scene_pos = QPointF()
        self._press_scene_rect = QRectF()
        self.signals = SelectionSignals()

        # ---------------------------------
        # Size label
        # ---------------------------------
        self.LABEL_MARGIN = 5
        self.size_label = QGraphicsSimpleTextItem(self)
        self.size_label.setBrush(QBrush(Qt.GlobalColor.white))
        font = QFont()
        font.setPointSize(9)
        self.size_label.setFont(font)
        self.size_label.setZValue(100)
        self._update_size_label()

        # selection finished state
        self._finished = False

    def is_finished(self) -> bool:
        return self._finished

    @property
    def finished(self):
        return self._finished

    # --------------------------------------------------------
    # Geometry
    # --------------------------------------------------------
    def _handles(self):
        r = self.rect()
        s = self.HANDLE_SIZE
        h = s / 2
        return {
            self.TOP_LEFT: QRectF(r.left() - h, r.top() - h, s, s),
            self.TOP: QRectF(r.center().x() - h, r.top() - h, s, s),
            self.TOP_RIGHT: QRectF(r.right() - h, r.top() - h, s, s),
            self.RIGHT: QRectF(r.right() - h, r.center().y() - h, s, s),
            self.BOTTOM_RIGHT: QRectF(r.right() - h, r.bottom() - h, s, s),
            self.BOTTOM: QRectF(r.center().x() - h, r.bottom() - h, s, s),
            self.BOTTOM_LEFT: QRectF(r.left() - h, r.bottom() - h, s, s),
            self.LEFT: QRectF(r.left() - h, r.center().y() - h, s, s),
        }

    def _handle_at(self, pos):
        for handle, r in self._handles().items():
            if r.contains(pos):
                return handle
        return self.NONE

    def boundingRect(self):
        m = self.HANDLE_SIZE
        return self.rect().adjusted(-m, -m, +m, +m)

    # # IMPORTANT:
    # # Make handles outside rect actually clickable.
    # def shape(self):
    #     path = QPainterPath()
    #     # Whole selection is draggable
    #     path.addRect(self.rect())
    #     # Handles are also hit-testable
    #     for rect in self._handles().values():
    #         path.addRect(rect)
    #     return path
    def _shape(self):
        path = QPainterPath()
        m = 5  # Increase this number to make the clickable area even bigger
        bigger_rect = self.rect().adjusted(-m, -m, m, m)
        path.addRect(bigger_rect)
        return path

    def shape(self):
        """Override shape to restrict click detection strictly to the border line."""
        # Create a basic path containing the raw outline of the rectangle
        base_path = QPainterPath()
        base_path.addRect(self.rect())

        # Set up a stroker to turn the outline into a clickable ribbon
        stroker = QPainterPathStroker()
        margin = 10
        stroker.setWidth(margin)
        border_only_path = stroker.createStroke(base_path)
        return border_only_path

    # --------------------------------------------------------
    # Emit Move/resize
    # --------------------------------------------------------
    def _emit_geometry_changed(self):
        self.signals.geometryChanged.emit(self.scene_selection_rect())

    def itemChange(self, change, value):
        """
        Item position change callback.
        """
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
            and self.scene()
        ):
            self._emit_geometry_changed()
            self._update_size_label()
        return super().itemChange(change, value)

    # Resizing
    def set_selection_rect(self, rect):
        """
        Wrapper for setRect() to track the size change.
        """
        # self.prepareGeometryChange()
        self.setRect(rect)
        self._emit_geometry_changed()
        self._update_size_label()

    def set_finished(self, finished: bool):
        if self._finished == finished:
            return

        self._finished = finished
        self.update()

    def scene_selection_rect(self):
        """
        Actual selection, Map rect -> scene loco coordinate
        """
        return self.mapRectToScene(self.rect())

    def scene_outer_rect(self):
        """
        self.sceneBoundingRect() is already in QGraphicsScene coordinates
        selection + handles bounding rect.
        """
        return self.sceneBoundingRect()

    # --------------------------------------------------------
    # Painting
    # --------------------------------------------------------
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Border
        painter.setPen(self.pen())
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawRect(self.rect())
        if not self._finished:
            return

        # Handles
        radius = 2.5
        painter.setPen(QPen(QColor("#0088dd"), 1))
        painter.setBrush(QBrush(Qt.GlobalColor.white))
        for rect in self._handles().values():
            # painter.drawRect(rect)
            painter.drawRoundedRect(QRectF(rect), radius, radius)

    # # --------------------------------------------------------
    # # Cursor
    # # --------------------------------------------------------
    # def _hoverMoveEvent(self, event):
    #     handle = self._handle_at(event.pos())
    #     cursor = {
    #         self.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    #         self.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
    #         self.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    #         self.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
    #         self.TOP: Qt.CursorShape.SizeVerCursor,
    #         self.BOTTOM: Qt.CursorShape.SizeVerCursor,
    #         self.LEFT: Qt.CursorShape.SizeHorCursor,
    #         self.RIGHT: Qt.CursorShape.SizeHorCursor,
    #     }.get(handle, Qt.CursorShape.SizeAllCursor)
    #     self.setCursor(cursor)
    #     super().hoverMoveEvent(event)

    # def _hoverLeaveEvent(self, event):
    #     self.unsetCursor()
    #     super().hoverLeaveEvent(event)

    def hoverMoveEvent(self, event):
        if not self._finished:
            return super().hoverMoveEvent(event)
        handle = self._handle_at(event.pos())
        cursor = {
            self.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
            self.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
            self.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
            self.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
            self.TOP: Qt.CursorShape.SizeVerCursor,
            self.BOTTOM: Qt.CursorShape.SizeVerCursor,
            self.LEFT: Qt.CursorShape.SizeHorCursor,
            self.RIGHT: Qt.CursorShape.SizeHorCursor,
        }.get(handle, Qt.CursorShape.SizeAllCursor)

        # self.setCursor(cursor)
        self.signals.cursorRequested.emit(cursor)  # let viewport set.
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        # self.unsetCursor()
        if not self._finished:
            return super().hoverLeaveEvent(event)
        self.signals.cursorRestoreRequested.emit()  # let viewport unset.
        super().hoverLeaveEvent(event)

    # --------------------------------------------------------
    # Resize / move
    # --------------------------------------------------------
    def mousePressEvent(self, event):
        self._handle = self._handle_at(event.pos())
        if self._handle != self.NONE:
            self._press_scene_pos = event.scenePos()
            self._press_scene_rect = self.scene_selection_rect()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        Only trigger after items exist, not in item is creating
        """
        if self._handle == self.NONE:
            super().mouseMoveEvent(event)
            if self.scene():
                self.scene().update()
            return
        delta = event.scenePos() - self._press_scene_pos
        r = QRectF(self._press_scene_rect)
        # Left
        if self._handle in (self.TOP_LEFT, self.LEFT, self.BOTTOM_LEFT):
            r.setLeft(r.left() + delta.x())
        # Right
        if self._handle in (self.TOP_RIGHT, self.RIGHT, self.BOTTOM_RIGHT):
            r.setRight(r.right() + delta.x())
        # Top
        if self._handle in (self.TOP_LEFT, self.TOP, self.TOP_RIGHT):
            r.setTop(r.top() + delta.y())
        # Bottom
        if self._handle in (self.BOTTOM_LEFT, self.BOTTOM, self.BOTTOM_RIGHT):
            r.setBottom(r.bottom() + delta.y())
        r = r.normalized()
        if r.width() >= 10 and r.height() >= 10:
            # Convert scene rect back to local item geometry.
            # Reset pos so rect remains easy to manage.
            self.prepareGeometryChange()
            self.setPos(0, 0)
            # self.setRect(r)
            # self._update_size_label()
            self.set_selection_rect(r)

        event.accept()

    def mouseReleaseEvent(self, event):
        self._handle = self.NONE
        super().mouseReleaseEvent(event)
        if self.scene():
            self.scene().update()

    def wheelEvent(self, event):
        """Override wheel event to resize the bounding box via scrolling."""
        current_rect = self.rect()
        delta = event.delta()
        step = 5

        if delta > 0:
            new_rect = current_rect.adjusted(-step, -step, step, step)
        else:
            # Scroll Down: Deflate the rectangle inward on all sides
            # Add a safety check to prevent the rectangle from collapsing into negative width/height
            if current_rect.width() > step * 2 and current_rect.height() > step * 2:
                new_rect = current_rect.adjusted(step, step, -step, -step)
            else:
                new_rect = current_rect
        self.set_selection_rect(new_rect)
        event.accept()

    # ========================================================
    # Size label
    # ========================================================

    def _update_size_label(self):
        rect = self.rect()
        width = round(rect.width())
        height = round(rect.height())
        self.size_label.setText(f"{width} × {height}")
        label_rect = self.size_label.boundingRect()
        x = rect.left()
        y = rect.top() - label_rect.height() - self.LABEL_MARGIN
        # Not enough space above -> put inside
        if y < 0:
            y = rect.top() + self.LABEL_MARGIN

        self.size_label.setPos(x, y)
