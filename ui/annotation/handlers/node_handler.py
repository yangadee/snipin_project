from ui.annotation.items import CustomNode
from ui.annotation.styles import make_pen, make_shape_brush
from ui.models.tools import AnnotationHandler


class NodeHandler(AnnotationHandler):

    def __init__(self):
        self._next_number = 1

    def start(self, pos, options):
        item = CustomNode(
            text=str(self._next_number),
            shape_type=options.shape,
            color=options.color,
            size=options.size,
        )
        # Node center = clicked position
        item.setPos(pos)
        self._next_number += 1
        return item

    def update(self, item, start_pos, current_pos):
        # Click-created item.
        pass

    def finish(self, item, end_pos):
        pass

    def reset_next_number(self):
        self._next_number = 1
