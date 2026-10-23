from ui.annotation.items import EffectItem
from ui.models.tools import AnnotationHandler, EffectShape
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QRectF


class EffectHandler(AnnotationHandler):

    def __init__(self):
        self.source_pixmap = None

    def prepare(self, scene):
        self.source_pixmap = scene.bg_item.pixmap()

    def set_source_pixmap(self, pixmap: QPixmap):
        self.source_pixmap = pixmap

    def start(self, pos, options):
        if self.source_pixmap is None or self.source_pixmap.isNull():
            return None
        item = EffectItem(source_pixmap=self.source_pixmap, options=options)
        item.start(pos)
        return item

    def update(self, item, start_pos, current_pos):
        item.update_geometry(start_pos, current_pos)

    def is_valid(self, item, start_pos, end_pos):
        if item.shape_type == EffectShape.BRUSH:
            return item.path().length() >= 2.0

        rect = QRectF(start_pos, end_pos).normalized()

        return rect.width() >= 5.0 and rect.height() >= 5.0

    def is_editable(self, item):
        return False

    # def finish(self, item, end_pos):
    #     item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
    #     item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
