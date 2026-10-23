from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable
from PyQt6.QtCore import QRect, QPoint, QRectF
from PyQt6.QtGui import QIcon, QImage
from enum import Enum, auto

from PyQt6.QtWidgets import QGraphicsView


class PluginCapability(str, Enum):
    IMAGE = "image"
    TEXT = "text"
    HOTKEY = "hotkey"
    BACKGROUND = "background"
    TRAY = "tray"


class PluginStatus(Enum):
    IDLE = auto()
    RUNNING = auto()
    FINISHED = auto()
    CANCELLED = auto()
    ERROR = auto()


@dataclass
class PluginRecord:
    plugin_id: str
    enabled: bool = True
    module: ModuleType | None = None
    instance: object | None = None
    hotkey_id: str | None = None
    capabilities: frozenset[PluginCapability] = field(default_factory=frozenset)

    @property
    def is_loaded(self) -> bool:
        return self.module is not None

    @property
    def is_available(self) -> bool:
        return self.enabled and self.is_loaded and self.instance is not None


@dataclass(slots=True, frozen=True)
class PluginInfo:
    plugin_id: str
    name: str
    icon: str  # get Qicon via icon_provider
    tooltip: str = ""
    enabled: bool = True
    hotkey: str = ""


@dataclass(slots=True)
class PluginContext:
    view: QGraphicsView | None = None
    image: QImage | None = None
    selection_rect: QRectF | None = None
    cursor_pos: QPoint | None = None

    source: str = ""

    copy_text: Callable[[str], None] | None = None
    copy_image: Callable[[QImage], None] | None = None
    show_message: Callable[[str], None] | None = None
    callback: Callable[[object], None] | None = None
