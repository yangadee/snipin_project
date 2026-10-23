from . import EditableTextItem, CustomNode, ArrowItem, EffectItem
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsRectItem, QGraphicsEllipseItem
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt


class ResizeHandle(QGraphicsRectItem):
    SIZE = 8

    CURSORS = {
        # Corners
        "top_left": Qt.CursorShape.SizeFDiagCursor,
        "bottom_right": Qt.CursorShape.SizeFDiagCursor,
        "top_right": Qt.CursorShape.SizeBDiagCursor,
        "bottom_left": Qt.CursorShape.SizeBDiagCursor,
        # Horizontal
        "middle_left": Qt.CursorShape.SizeHorCursor,
        "middle_right": Qt.CursorShape.SizeHorCursor,
        # Vertical
        "top_center": Qt.CursorShape.SizeVerCursor,
        "bottom_center": Qt.CursorShape.SizeVerCursor,
        # Line endpoints
        "start": Qt.CursorShape.CrossCursor,
        "end": Qt.CursorShape.CrossCursor,
    }

    def __init__(self, role, manager):
        half = self.SIZE / 2

        super().__init__(QRectF(-half, -half, self.SIZE, self.SIZE))

        self.role = role
        self.manager = manager

        # White border
        pen = QPen(QColor("white"))
        pen.setWidth(2)
        pen.setCosmetic(True)
        self.setPen(pen)

        # Blue fill
        self.setBrush(QColor("#1683FF"))

        self.setZValue(1000)

        # --------------------------------
        # Resize cursor
        # --------------------------------
        self.setCursor(self.CURSORS.get(role, Qt.CursorShape.ArrowCursor))


class AnnotationHandles:
    def __init__(self, scene):
        self.scene = scene
        self.item = None
        self.handles = {}

    def attach(self, item):
        self.detach()
        self.item = item
        # --------------------------------
        # Selected annotation = movable
        # --------------------------------
        self.item.setCursor(Qt.CursorShape.SizeAllCursor)
        if isinstance(item, (QGraphicsLineItem, ArrowItem)):
            roles = ("start", "end")

        elif isinstance(item, EditableTextItem):
            roles = (
                "top_left",
                "top_right",
                "bottom_left",
                "bottom_right",
            )
            item.document().contentsChanged.connect(self.update_positions)
        elif isinstance(item, CustomNode):
            roles = (
                "top_left",
                "top_right",
                "bottom_left",
                "bottom_right",
            )
        elif isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            roles = (
                "top_left",
                "top_center",
                "top_right",
                "middle_left",
                "middle_right",
                "bottom_left",
                "bottom_center",
                "bottom_right",
            )
        else:
            roles = ()

        for role in roles:
            handle = ResizeHandle(role, self)
            self.scene.addItem(handle)
            self.handles[role] = handle
        self.update_positions()

    def detach(self):
        if self.item is not None:
            self.item.unsetCursor()
        for handle in self.handles.values():
            if handle.scene() is self.scene:
                self.scene.removeItem(handle)
        self.handles.clear()
        self.item = None

    def update_positions(self):
        if self.item is None:
            return

        # ----------------------------------
        # Arrow
        # ----------------------------------
        # if isinstance(self.item, ArrowItem):
        #     self.handles["start"].setPos(self.item.mapToScene(self.item.start))
        #     self.handles["end"].setPos(self.item.mapToScene(self.item.end))
        #     return

        # ----------------------------------
        # Line
        # ----------------------------------
        if isinstance(self.item, (QGraphicsLineItem)):
            line = self.item.line()
            self.handles["start"].setPos(self.item.mapToScene(line.p1()))
            self.handles["end"].setPos(self.item.mapToScene(line.p2()))
            return

        if isinstance(self.item, CustomNode):
            rect = self.item.boundingRect()

            points = {
                "top_left": rect.topLeft(),
                "top_right": rect.topRight(),
                "bottom_left": rect.bottomLeft(),
                "bottom_right": rect.bottomRight(),
            }

            for role, pos in points.items():
                self.handles[role].setPos(self.item.mapToScene(pos))

            return

        # ----------------------------------
        # Text
        # ----------------------------------
        if isinstance(self.item, EditableTextItem):
            rect = self.item.boundingRect()

            points = {
                "top_left": rect.topLeft(),
                "top_right": rect.topRight(),
                "bottom_left": rect.bottomLeft(),
                "bottom_right": rect.bottomRight(),
            }

            for role, pos in points.items():
                self.handles[role].setPos(self.item.mapToScene(pos))

            return

        # ----------------------------------
        # Rect / Ellipse
        # Use actual geometry, NOT sceneBoundingRect()
        # ----------------------------------
        if isinstance(self.item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            rect = self.item.rect()
            points = {
                "top_left": rect.topLeft(),
                "top_center": QPointF(rect.center().x(), rect.top()),
                "top_right": rect.topRight(),
                "middle_left": QPointF(rect.left(), rect.center().y()),
                "middle_right": QPointF(rect.right(), rect.center().y()),
                "bottom_left": rect.bottomLeft(),
                "bottom_center": QPointF(rect.center().x(), rect.bottom()),
                "bottom_right": rect.bottomRight(),
            }
            for role, pos in points.items():
                self.handles[role].setPos(self.item.mapToScene(pos))

    def handle_at(self, scene_pos):
        for handle_type, handle in self.handles.items():
            if not handle.isVisible():
                continue
            local_pos = handle.mapFromScene(scene_pos)
            if handle.contains(local_pos):
                return handle_type
        return None

    def resize(self, role, scene_pos):
        if self.item is None:
            return
        item = self.item
        if item is None:
            return
        # ----------------------------------
        # Arrow
        # ----------------------------------
        # if isinstance(item, ArrowItem):
        #     local_pos = item.mapFromScene(scene_pos)
        #     if role == "start":
        #         item.set_start(local_pos)
        #     elif role == "end":
        #         item.set_end(local_pos)

        #     self.update_positions()
        #     return
        # ----------------------------------
        # Text
        # ----------------------------------
        if isinstance(item, EditableTextItem):
            self._resize_text(item, role, scene_pos)
            self.update_positions()
            return
        if isinstance(item, CustomNode):
            local_pos = item.mapFromScene(scene_pos)

            # Origin of CustomNode is its center.
            # Keep aspect ratio 1:1.
            half_size = max(
                abs(local_pos.x()),
                abs(local_pos.y()),
            )

            item.set_size(half_size * 2.0)

            self.update_positions()
            return
        # ----------------------------------
        # Line
        # ----------------------------------
        if isinstance(self.item, (QGraphicsLineItem)):
            line = self.item.line()
            local_pos = self.item.mapFromScene(scene_pos)
            if role == "start":
                line.setP1(local_pos)
            elif role == "end":
                line.setP2(local_pos)
            self.item.setLine(line)
            self.update_positions()
            return

        # ----------------------------------
        # Rect / Ellipse
        # ----------------------------------
        if isinstance(
            self.item,
            (QGraphicsRectItem, QGraphicsEllipseItem),
        ):
            rect = self.item.rect()

            # scene -> item coordinate
            pos = self.item.mapFromScene(scene_pos)

            if role == "top_left":
                rect.setTopLeft(pos)

            elif role == "top_center":
                rect.setTop(pos.y())

            elif role == "top_right":
                rect.setTopRight(pos)

            elif role == "middle_left":
                rect.setLeft(pos.x())

            elif role == "middle_right":
                rect.setRight(pos.x())

            elif role == "bottom_left":
                rect.setBottomLeft(pos)

            elif role == "bottom_center":
                rect.setBottom(pos.y())

            elif role == "bottom_right":
                rect.setBottomRight(pos)
            self.item.setRect(rect.normalized())
            self.update_positions()

    def _resize_text(
        self,
        item: EditableTextItem,
        role: str,
        scene_pos: QPointF,
    ):
        rect = item.boundingRect()
        # Scene -> item-local coordinates
        pos = item.mapFromScene(scene_pos)
        # Anchor opposite corner
        if role == "bottom_right":
            anchor = rect.topLeft()
        elif role == "bottom_left":
            anchor = rect.topRight()
        elif role == "top_right":
            anchor = rect.bottomLeft()
        elif role == "top_left":
            anchor = rect.bottomRight()
        else:
            return

        current_distance = QLineF(anchor, rect.center()).length()
        new_distance = QLineF(anchor, pos).length()
        if current_distance <= 0:
            return
        # Use diagonal ratio
        scale = new_distance / (current_distance * 2.0)
        font = item.font()
        current_size = font.pointSizeF()
        if current_size <= 0:
            current_size = 16.0
        new_size = max(6.0, min(200.0, current_size * scale))

        font.setPointSizeF(new_size)
        item.setFont(font)

    def geometry(self):
        item = self.item
        if item is None:
            return None
        if isinstance(item, QGraphicsLineItem):
            return QLineF(item.line())

        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            return QRectF(item.rect())
        if isinstance(item, ArrowItem):
            return (QPointF(item.start), QPointF(item.end))
        return None

    def set_geometry(self, geometry):
        item = self.item
        if item is None:
            return
        if isinstance(item, QGraphicsLineItem):
            item.setLine(QLineF(geometry))
        elif isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            item.setRect(QRectF(geometry))
        elif isinstance(item, ArrowItem):
            start, end = geometry

            item.set_line(start, end)
        self.update_positions()
