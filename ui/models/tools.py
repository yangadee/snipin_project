from dataclasses import dataclass, field
from enum import IntEnum, Enum, auto

# ============================================================
# Tool definitions
# ============================================================

"""
ToolSpec
    static-ish registration/configuration

ToolState
    current runtime state

ToolSelection
    current main + sub-tool
"""


class AnnotationHandler:
    def start(self, pos, options):
        raise NotImplementedError

    def prepare(self, scene):
        pass

    def update(self, item, start_pos, current_pos):
        raise NotImplementedError

    def is_valid(self, item, start_pos, end_pos):
        return True

    def is_editable(self, item):
        return True

    def finish(self, item, end_pos):
        pass

    def constrain(self, start_pos, current_pos, modifiers):
        return current_pos


class Tool(IntEnum):
    NONE = auto()
    SELECT = auto()
    PEN = auto()
    MARKER = auto()
    LINE = auto()
    SHAPE = auto()
    TEXT = auto()
    NODE = auto()
    EFFECT = auto()
    PLUGIN = auto()
    USER_BASE = 100


class ToolAction(Enum):
    COPY = auto()
    SAVE = auto()
    CLOSE = auto()
    PIN = auto()
    REDO = auto()
    UNDO = auto()


class EffectType(str, Enum):
    MOSAIC = "mosaic"
    BLUR = "blur"


class EffectShape(str, Enum):
    RECT = "rect"
    BRUSH = "brush"


class LineType(str, Enum):
    LINE = "line"
    ARROW = "arrow"


class ShapeType(str, Enum):
    RECT = "rect"
    ELLIPSE = "ellipse"
    CIRCLE = "circle"
    HEXAGON = "hexagon"


class NodeShape(str, Enum):
    CIRCLE = "circle"
    RECT = "rect"
    HEXAGON = "hexagon"
