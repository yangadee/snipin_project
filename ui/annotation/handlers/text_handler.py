from ui.annotation.items import EditableTextItem
from ui.models.tools import AnnotationHandler
from PyQt6.QtGui import QColor


class TextHandler(AnnotationHandler):

    def start(self, pos, options):
        color = QColor(options.color)
        # color.setAlphaF(options.opacity)

        item = EditableTextItem(
            placeholder="",
            font_size=options.font_size,
            color=color,
            font_family=options.font_family,
        )

        item.setPos(pos)
        return item

    def update(self, item, start_pos, current_pos):
        # Text is created by click, not drag.
        pass

    def finish(self, item, end_pos):
        item.enable_editing()
