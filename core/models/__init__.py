"""
store the shared dataclass
"""

from .hotkey import HotkeySpec
from .overlay import OverlayConfig

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AppContext:
    """
    Long-lived application services available to application components.

    The context owns nothing.
    AppController owns the actual manager/service objects.
    """

    plugins: any
    hotkeys: any
    settings: any
