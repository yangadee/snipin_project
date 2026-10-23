from PyQt6.QtCore import QPoint, QPointF, QRectF, QSize, Qt

from PyQt6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPixmap,
)

from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem

from ui.models.tools import EffectShape, EffectType
from ui.models.tool_options import EffectOptions


class EffectItem(QGraphicsPixmapItem):

    def __init__(
        self,
        source_pixmap: QPixmap,
        options: EffectOptions,
        parent=None,
    ):
        super().__init__(parent)

        self.source_pixmap = QPixmap(source_pixmap)

        self.effect_type = options.effect
        self.shape_type = options.shape
        self.strength = max(2, int(options.strength))

        self.brush_size = max(2.0, float(options.brush_size))

        self._rect = QRectF()
        self._path = QPainterPath()

        # --------------------------------
        # Process source ONCE
        # --------------------------------
        self._processed_image = self._create_processed_image()

        self.setZValue(20)

        # Transparent pixmap means MaskShape can
        # become unnecessarily expensive.
        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    # =========================================================
    # Drawing interface
    # =========================================================

    def start_(self, pos: QPointF):
        if self.shape_type == EffectShape.RECT:
            self.set_rect(QRectF(pos, pos))
        else:
            self.start_path(pos)

    def update_geometry_(self, start_pos: QPointF, current_pos: QPointF):
        if self.shape_type == EffectShape.RECT:
            self.set_rect(QRectF(start_pos, current_pos).normalized())
        else:
            self.add_path_point(current_pos)

    def start(self, pos):
        if self.shape_type == EffectShape.RECT:
            self._rect = QRectF(pos, pos)
        else:
            self._path = QPainterPath(pos)
            self._path.lineTo(pos + QPointF(0.01, 0.01))

        self._update_masked_pixmap()

    def update_geometry(self, start_pos, current_pos):
        if self.shape_type == EffectShape.RECT:
            self._rect = QRectF(start_pos, current_pos).normalized()
        else:
            self._path.lineTo(current_pos)

        self._update_masked_pixmap()

    # =========================================================
    # Rectangle geometry
    # =========================================================

    def set_rect(self, rect: QRectF):
        self._rect = rect.normalized()
        if self._rect.isEmpty():
            return
        self._update_effect()

    def rect(self) -> QRectF:
        """
        Returns local effect rectangle.
        """

        if self._rect.isEmpty():
            return QRectF()

        return QRectF(0.0, 0.0, self._rect.width(), self._rect.height())

    # =========================================================
    # Brush geometry
    # =========================================================

    def start_path(self, pos: QPointF):
        self._path = QPainterPath(pos)

        # Make single click technically non-empty.
        self._path.lineTo(pos + QPointF(0.01, 0.01))

        self._update_effect()

    def add_path_point(self, pos: QPointF):
        self._path.lineTo(pos)
        self._update_effect()

    def path(self) -> QPainterPath:
        return QPainterPath(self._path)

    # =========================================================
    # Effect mask
    # =========================================================

    def effect_shape(self) -> QPainterPath:
        if self.shape_type == EffectShape.RECT:
            path = QPainterPath()
            path.addRect(self._rect)
            return path

        # Freehand brush path -> filled stroke shape.
        stroker = QPainterPathStroker()
        stroker.setWidth(self.brush_size)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return stroker.createStroke(self._path)

    # =========================================================
    # Effect processing
    # =========================================================

    def _update_effect(self):
        shape = self.effect_shape()

        if shape.isEmpty():
            self.setPixmap(QPixmap())
            return

        # ---------------------------------------------
        # Scene/source bounding region to process
        # ---------------------------------------------
        effect_rect = shape.boundingRect().intersected(
            QRectF(self.source_pixmap.rect())
        )

        if effect_rect.isEmpty():
            self.setPixmap(QPixmap())
            return

        source_rect = effect_rect.toAlignedRect()

        # Capture only affected source region
        source = self.source_pixmap.copy(source_rect)

        if source.isNull():
            self.setPixmap(QPixmap())
            return

        # ---------------------------------------------
        # Apply selected algorithm
        # ---------------------------------------------
        if self.effect_type == EffectType.MOSAIC:
            processed = self._make_mosaic(source, self.strength)

        elif self.effect_type == EffectType.BLUR:
            print("self.effect_type == EffectType.BLUR:")
            processed = self._make_blur(source, self.strength)

        else:
            return

        # ---------------------------------------------
        # Mask processed image
        # ---------------------------------------------
        result = self._apply_mask(processed, shape, source_rect)

        # Graphics item itself is local at 0,0.
        self.setPixmap(QPixmap.fromImage(result))

        # Position item's local origin at effect area TL.
        self.setPos(QPointF(source_rect.topLeft()))

    @staticmethod
    def _make_mosaic(image: QImage, block_size: int) -> QImage:
        if image.isNull():
            return QImage()
        block_size = max(2, int(block_size))
        small_size = QSize(
            max(1, image.width() // block_size),
            max(1, image.height() // block_size),
        )

        small = image.scaled(
            small_size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

        return small.scaled(
            image.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

    @staticmethod
    def _make_blur(image: QImage, strength: int) -> QImage:
        if image.isNull():
            return QImage()
        strength = max(2, int(strength))
        small_size = QSize(
            max(1, image.width() // strength),
            max(1, image.height() // strength),
        )
        small = image.scaled(
            small_size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return small.scaled(
            image.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    @staticmethod
    def _apply_mask(processed: QImage, shape: QPainterPath, source_rect) -> QImage:
        result = QImage(
            processed.size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )
        # shape is currently in scene/source coordinates.
        # Result image begins at local 0,0.
        local_shape = QPainterPath(shape)
        local_shape.translate(-source_rect.left(), -source_rect.top())
        painter.setClipPath(local_shape)
        painter.drawImage(0, 0, processed)
        painter.end()
        return result

    def _create_processed_image(self) -> QImage:
        if self.effect_type == EffectType.MOSAIC:
            return self._make_mosaic(
                self.source_pixmap.toImage(),
                self.strength,
            )
        if self.effect_type == EffectType.BLUR:
            return self._make_blur(
                self.source_pixmap.toImage(),
                self.strength,
            )
        return self.source_pixmap.toImage()

    def _rebuild_processed_image(self):
        source = self.source_pixmap.toImage()
        if source.isNull():
            self._processed_image = QImage()
            return
        if self.effect_type == EffectType.MOSAIC:
            self._processed_image = self._make_mosaic(source, self.strength)

        elif self.effect_type == EffectType.BLUR:
            self._processed_image = self._make_blur(source, self.strength)
        else:
            self._processed_image = source

    def set_strength(self, value):
        value = max(2, int(value))
        if value == self.strength:
            return
        self.strength = value
        # Effect itself changed, so rebuild cache.
        self._rebuild_processed_image()
        # Apply existing geometry/path again.
        self._update_masked_pixmap()

    def set_effect_type(self, effect_type):
        if effect_type == self.effect_type:
            return

        self.effect_type = effect_type

        self._rebuild_processed_image()
        self._update_masked_pixmap()

    def set_brush_size(self, value):
        value = max(2.0, float(value))
        if value == self.brush_size:
            return
        self.brush_size = value
        # Only mask changes
        self._update_masked_pixmap()

    def set_source_pixmap(self, pixmap):
        if pixmap.isNull():
            return
        self.source_pixmap = QPixmap(pixmap)
        self._rebuild_processed_image()
        self._update_masked_pixmap()

    def _update_masked_pixmap(self):
        shape = self.effect_shape()
        if shape.isEmpty():
            self.setPixmap(QPixmap())
            return
        source_bounds = QRectF(self.source_pixmap.rect())
        effect_rect = shape.boundingRect().intersected(source_bounds)
        if effect_rect.isEmpty():
            self.setPixmap(QPixmap())
            return
        source_rect = effect_rect.toAlignedRect()
        # --------------------------------
        # Crop from PREPROCESSED image
        # --------------------------------
        processed = self._processed_image.copy(source_rect)
        if processed.isNull():
            return

        # --------------------------------
        # Transparent output
        # --------------------------------
        result = QImage(
            processed.size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # --------------------------------
        # Convert scene mask -> local crop
        # --------------------------------
        local_shape = QPainterPath(shape)
        local_shape.translate(-source_rect.left(), -source_rect.top())
        painter.setClipPath(local_shape)
        painter.drawImage(QPoint(0, 0), processed)
        painter.end()

        # --------------------------------
        # Display
        # --------------------------------
        self.setPixmap(QPixmap.fromImage(result))
        self.setPos(QPointF(source_rect.topLeft()))
