from PyQt6.QtCore import QPoint, QRect, Qt, QRectF, QPointF, QLineF, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainterPath,
    QPen,
    QBrush,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsPathItem,
)

from ui.annotation.items import (
    SelectionRect,
    EditableTextItem,
    EffectItem,
    CustomNode,
    ArrowItem,
)

from ui.models.tools import Tool
from ui.models.annotation import ANNOTATION_DATA, AnnotationData
from .pin_scene import PinScene
from .image_scene import ImageScene


class DimItem(QGraphicsItem):
    """
    Drawing for corner rect() with Qgrphicsitem for best performance.
    """

    def __init__(self, scene_rect: QRectF):
        super().__init__()
        self._scene_rect = QRectF(scene_rect)
        self._selection_rect = QRectF()
        self.setZValue(10)

    def setRect(self, rect):
        """
        Change scene rect.
        """
        self._scene_rect = QRectF(rect)

    def boundingRect(self):
        return self._scene_rect

    def set_selection_rect(self, rect: QRectF):
        old_rect = self._selection_rect
        self._selection_rect = QRectF(rect)
        dirty = old_rect.united(self._selection_rect).adjusted(-2, -2, 2, 2)
        self.update(dirty)

    def clear_selection(self):
        old_rect = self._selection_rect
        self._selection_rect = QRectF()
        self.update(old_rect.adjusted(-2, -2, 2, 2))

    def paint(self, painter, option, widget=None):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 110))
        # No selection -> dim everything
        if self._selection_rect.isEmpty():
            painter.drawRect(self._scene_rect)
            return
        r = self._selection_rect
        s = self._scene_rect
        # Top
        painter.drawRect(QRectF(s.left(), s.top(), s.width(), r.top() - s.top()))
        # Bottom
        painter.drawRect(
            QRectF(s.left(), r.bottom(), s.width(), s.bottom() - r.bottom())
        )
        # Left
        painter.drawRect(QRectF(s.left(), r.top(), r.left() - s.left(), r.height()))
        # Right
        painter.drawRect(QRectF(r.right(), r.top(), s.right() - r.right(), r.height()))

    # def ___set_selection_rect(self, rect: QRectF):
    #     rect = rect.normalized()
    #     if rect == self._selection_rect:
    #         return
    #     old = QRectF(self._selection_rect)
    #     self._selection_rect = rect
    #     if old.isEmpty() or rect.isEmpty():
    #         self.update()
    #         return
    #     pad = 2.0
    #     # Region covering old + new selection.
    #     bounds = old.united(rect)
    #     # Top changed area
    #     top = QRectF(
    #         bounds.left(),
    #         min(old.top(), rect.top()),
    #         bounds.width(),
    #         abs(old.top() - rect.top()) + pad,
    #     )
    #     # Bottom changed area
    #     bottom_y = min(old.bottom(), rect.bottom())
    #     bottom = QRectF(
    #         bounds.left(),
    #         bottom_y - pad,
    #         bounds.width(),
    #         abs(old.bottom() - rect.bottom()) + pad * 2,
    #     )
    #     # Left changed area
    #     left = QRectF(
    #         min(old.left(), rect.left()),
    #         bounds.top(),
    #         abs(old.left() - rect.left()) + pad,
    #         bounds.height(),
    #     )
    #     # Right changed area
    #     right_x = min(old.right(), rect.right())
    #     right = QRectF(
    #         right_x - pad,
    #         bounds.top(),
    #         abs(old.right() - rect.right()) + pad * 2,
    #         bounds.height(),
    #     )
    #     self.update(top)
    #     self.update(bottom)
    #     self.update(left)
    #     self.update(right)


class GrabScene(ImageScene):
    selectionFinished = pyqtSignal()
    selectionCanceled = pyqtSignal()
    selectionGeometryChanged = pyqtSignal(QRectF)
    cursorRequested = pyqtSignal(object)
    cursorRestoreRequested = pyqtSignal()
    selectionMouseMoved = pyqtSignal(QPointF, QPoint)
    SELECTION_MIN_SIZE = 20

    def __init__(
        self,
        pixmap: QPixmap | None = None,
        parent=None,
    ):
        super().__init__(pixmap, parent)
        self.tool = Tool.SELECT
        self.selection = None

        # dim
        self.dim = DimItem(self.sceneRect())
        self.addItem(self.dim)
        self.dim.setZValue(15)  # Between pixmap and items

        self._creating_selection = False
        self._selection_start = QPointF()
        # frozen system cursor
        self._frozen_cursor_item: QGraphicsPixmapItem | None = None
        self._frozen_cursor_visible = False

    @property
    def is_selecting(self) -> bool:
        return self._creating_selection

    def set_pixmap(self, pixmap: QPixmap) -> None:
        super().set_pixmap(pixmap)
        self.dim.setRect(self.sceneRect())

    def _set_pixmap(self, pixmap):
        if pixmap.isNull():
            return
        self.pixmap = pixmap
        # Replace background image
        self.bg_item.setPixmap(pixmap)
        self.bg_item.setZValue(0)
        # Background always starts at scene 0,0
        self.bg_item.setPos(0, 0)
        # Update scene size
        self.setSceneRect(QRectF(pixmap.rect()))

    def clear_annotations(self) -> None:
        """
        Remove all annotation items while preserving scene/UI items
        such as:
            - bg_item
            - dim
            - selection
            - frozen cursor
        """
        # Clear handles/references before removing their target item.
        self.clear_annotation_selection()
        # Cancel current annotation interaction.
        self.current_item = None
        self.active_handle = None
        self.moving_annotation = False

        for item in list(self.items()):
            data = item.data(ANNOTATION_DATA)
            if data is None:
                continue
            self.removeItem(item)
        #  permanently discard annotations
        self.undo_stack.clear()

    def clear_snip_selection(self):
        if self.selection is not None:
            self.removeItem(self.selection)
            self.selection = None
        self.dim.clear_selection()

    def reset_for_new_snip(self):
        """
        Reset the scene to the initial state, ready for a new snip.
        """
        self.clear_snip_selection()
        self.clear_annotations()
        self._creating_selection = False
        self._selection_start = QPointF()

    # def __clear_selection(self):
    #     """
    #     Clear selection & All items for re-select.
    #     Set dim full scene rect.
    #     """
    #     for item in self.items():
    #         if item not in (self.bg_item, self.dim, self._frozen_cursor_item):
    #             self.removeItem(item)
    #     self.selection = None
    #     self.dim.set_selection_rect(QRectF())

    # def __reset_selection(self):
    #     """
    #     Ready to start selection
    #     """
    #     self.clear_selection()
    #     self.clear_annotation_selection()
    #     self._creating_selection = False
    #     self._selection_start = QPointF()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        pos = event.scenePos()
        # --------------------------------------------------
        # Existing selection always has priority
        # --------------------------------------------------
        if self.selection:
            item = self.itemAt(pos, self.views()[0].transform())
            # Selection itself OR one of its child handles
            if item is self.selection or self.selection.isAncestorOf(item):
                return QGraphicsScene.mousePressEvent(self, event)
        # --------------------------------------------------
        # Annotation tool
        # Let ImageScene handle PEN / LINE / SHAPE / etc.
        # Annotation may only START inside the selection.
        # --------------------------------------------------
        if self.tool != Tool.SELECT:
            if self.selection:
                selection_rect = self.selection.scene_selection_rect().normalized()
            if not selection_rect.contains(pos):
                self.clear_annotation_selection()
                event.accept()
                return
            return super().mousePressEvent(event)
        # --------------------------------------------------
        # Existing selection
        # Don't create another selection
        # --------------------------------------------------
        if self.selection:
            return super().mousePressEvent(event)
        # --------------------------------------------------
        # Create selection
        # --------------------------------------------------
        self._selection_start = pos
        self._create_selection_rect(QRectF(pos, pos))
        # self.selection = SelectionRect(QRectF(pos, pos))
        # self.selection.setZValue(200)
        # self.addItem(self.selection)
        # self.selection.signals.geometryChanged.connect(self._selection_changed)
        # self.selection.signals.cursorRequested.connect(self.cursorRequested)
        # self.selection.signals.cursorRestoreRequested.connect(
        #     self.cursorRestoreRequested
        # )

        self._creating_selection = True
        event.accept()

    def _selection_changed(self, rect):
        # self.update()
        self.dim.set_selection_rect(rect)
        self.selectionGeometryChanged.emit(rect)

    def mouseMoveEvent(self, event):
        if self.tool == Tool.SELECT and self._creating_selection and self.selection:
            # old_rect = self.selection.sceneBoundingRect()
            rect = QRectF(self._selection_start, event.scenePos()).normalized()

            # self.selection.setRect(rect)
            self.selection.set_selection_rect(rect)
            # self.dim.set_selection_rect(rect)
            # new_rect = self.selection.sceneBoundingRect()
            # # Dity region: Include both old + new location
            # dirty = old_rect.united(new_rect).adjusted(-2, -2, 2, 2)
            # self.update(dirty)
            self.selectionMouseMoved.emit(event.scenePos(), event.screenPos())

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.tool == Tool.SELECT and self._creating_selection:
            rect = QRectF(self._selection_start, event.scenePos()).normalized()
            if (
                rect.width() < self.SELECTION_MIN_SIZE
                or rect.height() < self.SELECTION_MIN_SIZE
            ):
                self.removeItem(self.selection)
                self.selection = None
                self.clear_snip_selection()
                self.selectionCanceled.emit()
            else:
                self.selection.set_selection_rect(rect)
                self.selection.set_finished(True)  # show handles
                self.selectionFinished.emit()
            self._creating_selection = False
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ========================================================
    # Dim area
    # ========================================================
    def _drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        path = QPainterPath()
        path.addRect(self.sceneRect())
        if self.selection:
            hole = QPainterPath()
            hole.addRect(self.selection.scene_outer_rect())  # <- use scene_outer_rect
            path = path.subtracted(hole)
        painter.fillPath(path, QColor(0, 0, 0, 110))

    # ========================================================
    # Create PinScene in Scene, not Pin
    # ========================================================
    def create_pin_scene(self) -> PinScene:
        if not self.selection:
            return None
        rect = self.selection.scene_selection_rect().normalized()
        pixmap = self.pixmap.copy(rect.toAlignedRect())
        scene = PinScene(pixmap)
        self.copy_annotations_to(scene, rect)
        return scene

    def _copy_annotations_to(self, target_scene, source_rect):
        # ----------------------------------------------------
        # 2. Clone annotations
        # ----------------------------------------------------
        for item in self.items(Qt.SortOrder.AscendingOrder):
            # don't duplicate screenshot / selection rect
            if item in (self.pixmap, self.selection):
                continue
            # only items touching selection
            if not item.sceneBoundingRect().intersects(source_rect):
                continue
            new_item = self.clone_item(item)
            if new_item is None:
                continue
            new_item.setPos(new_item.pos() - source_rect.topLeft())
            target_scene.addItem(new_item)
        return target_scene

    def copy_annotations_to(self, target_scene, source_rect: QRectF):
        source_rect = source_rect.normalized()
        for item in self.items(Qt.SortOrder.AscendingOrder):
            # Only annotations.
            # Automatically excludes:
            #   bg_item
            #   dim
            #   selection
            #   resize handles
            #   size labels
            if not item.data(ANNOTATION_DATA):
                continue
            if not item.sceneBoundingRect().intersects(source_rect):
                continue
            new_item = self.clone_item(item)
            if new_item is None:
                continue
            self._copy_item_properties(item, new_item)
            new_item.setPos(item.scenePos() - source_rect.topLeft())
            target_scene.addItem(new_item)
        return target_scene

    def _copy_item_properties(self, source, target):
        target.setZValue(source.zValue())
        target.setRotation(source.rotation())
        target.setScale(source.scale())
        target.setVisible(source.isVisible())
        target.setTransformOriginPoint(source.transformOriginPoint())
        target.setOpacity(source.opacity())
        # target.setData(ANNOTATION_ITEM, True)
        # target.setData(EDITABLE_ITEM, True)

    def clone_item(self, item):
        # ----------------------------------
        # Arrow
        # MUST come before QGraphicsLineItem
        # ----------------------------------
        if isinstance(item, ArrowItem):
            clone = ArrowItem(QLineF(item.line()))
            clone.setPen(QPen(item.pen()))
            return clone

        # ----------------------------------
        # Line / Marker
        # ----------------------------------
        if isinstance(item, QGraphicsLineItem):
            clone = QGraphicsLineItem(QLineF(item.line()))
            clone.setPen(QPen(item.pen()))
            return clone

        # ----------------------------------
        # Rectangle
        # ----------------------------------
        if isinstance(item, QGraphicsRectItem):
            clone = QGraphicsRectItem(QRectF(item.rect()))
            clone.setPen(QPen(item.pen()))
            clone.setBrush(QBrush(item.brush()))
            return clone

        # ----------------------------------
        # Ellipse
        # ----------------------------------
        if isinstance(item, QGraphicsEllipseItem):
            clone = QGraphicsEllipseItem(QRectF(item.rect()))
            clone.setPen(QPen(item.pen()))
            clone.setBrush(QBrush(item.brush()))
            return clone

        # ----------------------------------
        # Freehand path
        # ----------------------------------
        if isinstance(item, QGraphicsPathItem):
            clone = QGraphicsPathItem(QPainterPath(item.path()))
            clone.setPen(QPen(item.pen()))
            clone.setBrush(QBrush(item.brush()))
            return clone

        # ----------------------------------
        # Text
        # ----------------------------------
        if isinstance(item, EditableTextItem):
            clone = EditableTextItem(
                placeholder=item.toPlainText(),
                font_size=item.font().pointSize(),
                color=item.defaultTextColor(),
                font_family=item.font().family(),
            )
            clone.setPlainText(item.toPlainText())

            clone.setFont(QFont(item.font()))
            clone.setDefaultTextColor(QColor(item.defaultTextColor()))
            if hasattr(clone, "disable_editing"):
                clone.disable_editing()
            return clone

        # ----------------------------------
        # Node
        # ----------------------------------
        if isinstance(item, CustomNode):
            return CustomNode(
                text=item.text,
                shape_type=item.shape_type,
                color=item.color,
                size=item.size(),
                opacity=item.opacity_value,
            )

        # ----------------------------------
        # Mosaic / Blur
        # Frozen raster clone
        # ----------------------------------
        if isinstance(item, EffectItem):
            clone = QGraphicsPixmapItem(QPixmap(item.pixmap()))
            clone.setShapeMode(item.shapeMode())
            clone.setTransformationMode(item.transformationMode())
            return clone

        # ----------------------------------
        # QGraphicsPixmapItem
        # Includes frozen system cursor
        # ----------------------------------
        if isinstance(item, QGraphicsPixmapItem):
            # print("clone pixmap item")
            clone = QGraphicsPixmapItem(QPixmap(item.pixmap()))
            clone.setOffset(item.offset())
            clone.setZValue(item.zValue())
            clone.setShapeMode(item.shapeMode())
            clone.setTransformationMode(item.transformationMode())
            return clone

        return None

    def _create_selection_rect(self, rect: QRectF):
        if self.selection is not None:
            return
        self.selection = SelectionRect(rect)
        self.selection.setZValue(200)
        self.addItem(self.selection)
        self.selection.signals.geometryChanged.connect(self._selection_changed)
        self.selection.signals.cursorRequested.connect(self.cursorRequested)
        self.selection.signals.cursorRestoreRequested.connect(
            self.cursorRestoreRequested
        )

    def set_selection_rect(self, rect: QRectF, finished: bool = True):
        """
        Set the selection_area rect by grabscene.
        """
        # print("set_selection_rect self.selection", self.selection)
        rect = rect.normalized().intersected(self.sceneRect())
        if rect.isEmpty():
            return
        if self.selection is None:
            self._create_selection_rect(rect)
            # self.selection = SelectionRect(rect)
            # self.selection.setZValue(200)
            # self.addItem(self.selection)
            # self.selection.signals.geometryChanged.connect(self._selection_changed)
            # self.selection.signals.cursorRequested.connect(self.cursorRequested)
            # self.selection.signals.cursorRestoreRequested.connect(
            #     self.cursorRestoreRequested
            # )

            # Initial geometry wasn't emitted
            self._selection_changed(self.selection.scene_selection_rect())
        else:
            self.selection.set_selection_rect(rect)
        # Must apply to BOTH new and existing selection
        self.selection.set_finished(finished)
        # print("After set_selection_rect", self.selection)

    # =================================================
    # Frozen system cursor
    # =================================================
    def set_frozen_cursor(self, cursor, virtual_rect: QRect) -> None:
        if cursor is None:
            self.remove_frozen_cursor()
            return
        cursor_pixmap, cursor_pos, hotspot = cursor
        if self._frozen_cursor_item is None:
            self._frozen_cursor_item = QGraphicsPixmapItem()
            self._frozen_cursor_item.setZValue(1)
            self._frozen_cursor_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._frozen_cursor_item.setAcceptHoverEvents(False)
            self._frozen_cursor_item.setData(
                ANNOTATION_DATA, AnnotationData(tool=None, editable=False)
            )
            self._frozen_cursor_item.setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False
            )
            self._frozen_cursor_item.setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False
            )
        self._frozen_cursor_item.setPixmap(cursor_pixmap)
        pos = cursor_pos - hotspot - virtual_rect.topLeft()
        self._frozen_cursor_item.setPos(QPointF(pos))
        # Add only if currently detached from a scene.
        if self._frozen_cursor_item.scene() is None:
            self.addItem(self._frozen_cursor_item)
            self._frozen_cursor_item.setVisible(self._frozen_cursor_visible)

    def set_frozen_cursor_visible(self, visible: bool) -> None:
        self._frozen_cursor_visible = visible
        if self._frozen_cursor_item is not None:
            self._frozen_cursor_item.setVisible(visible)

    def remove_frozen_cursor(self) -> None:
        if self._frozen_cursor_item is None:
            return
        self.removeItem(self._frozen_cursor_item)
        self._frozen_cursor_item = None
