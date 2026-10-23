from dataclasses import dataclass
from typing import Callable
from PyQt6.QtGui import QCursor
from ui.models.tool_options import ToolOptions
from ui.models.tools import AnnotationHandler, EffectType, LineType, ShapeType, Tool

# ============================================================
# Data class
# ============================================================


@dataclass
class ToolState:
    tool: Tool
    shape_type: ShapeType | None = None
    line_type: LineType | None = None
    effect_type: EffectType | None = None
    options: ToolOptions | None = None


@dataclass
class ToolSpec:
    id: Tool
    name: str
    icon: str
    options: ToolOptions | None = None
    options_page: any = None
    handler: AnnotationHandler | None = None
    cursor_factory: (
        Callable[
            [ToolOptions | None],
            QCursor,
        ]
        | None
    ) = None
