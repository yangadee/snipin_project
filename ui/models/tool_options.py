from dataclasses import dataclass, field
from PyQt6.QtGui import QColor
from .tools import EffectShape, EffectType, LineType, NodeShape, ShapeType


# ============================================================
# Options
# ============================================================
@dataclass
class PenOptions:
    color: QColor = field(default_factory=lambda: QColor("#ff3b30"))
    width: int = 3
    opacity: int = 100


@dataclass
class ShapeOptions:
    shape: ShapeType = ShapeType.RECT
    color: QColor = field(default_factory=lambda: QColor("#ff3b30"))
    width: int = 3
    fill: bool = False
    fill_color: QColor = field(default_factory=lambda: QColor("#ff3b30"))
    opacity: int = 100
    fill_opacity: int = 25


@dataclass
class TextOptions:
    color: QColor = field(default_factory=lambda: QColor("#ff3b30"))
    font_size: int = 18
    font_family: str = "Arial"


@dataclass
class NodeOptions:
    shape: NodeShape = NodeShape.CIRCLE
    color: QColor = field(default_factory=lambda: QColor("#ff3b30"))
    size: int = 32


@dataclass
class MosaicOptions:
    size: int = 16
    strength: int = 10


@dataclass
class LineOptions:
    color: QColor = field(default_factory=lambda: QColor("#ff3b30"))
    opacity: int = 100
    width: int = 3
    line_type: LineType = LineType.ARROW
    # opacity: int = 100


@dataclass
class EffectOptions:
    effect: EffectType = EffectType.MOSAIC
    shape: EffectShape = EffectShape.RECT

    strength: int = 5
    # Width of brush stroke
    brush_size: int = 30


@dataclass
class PluginOptions:
    # selected_plugin_id: str | None = None
    # resvered for future features
    pass


ToolOptions = PenOptions | ShapeOptions | TextOptions | MosaicOptions
