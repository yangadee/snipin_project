from dataclasses import dataclass


@dataclass
class HotkeySpec:
    hotkey_id: str
    hotkey_seq: str
    registration_id: int | None
    owner: str
    enabled: bool = True
