from dataclasses import dataclass


@dataclass
class OverlayConfig:
    enable_hint_panel: bool = True
    show_cursor_magnifier: bool = True
    enable_hit_testing: bool = True
