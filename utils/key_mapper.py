from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence


class KeyMapper:
    def __init__(self):
        # Master Mapping Array: (Primary Display String, Windows VK Code, Qt Key Enum, [List of String Aliases])
        self._master_table = [
            # Alphanumerics (A-Z)
            *[
                (
                    chr(code),
                    code,
                    getattr(Qt.Key, f"Key_{chr(code)}"),
                    [chr(code).lower()],
                )
                for code in range(0x41, 0x5B)
            ],
            # Numbers (0-9)
            *[
                (chr(code), code, getattr(Qt.Key, f"Key_{chr(code)}"), [])
                for code in range(0x30, 0x3A)
            ],
            # Function Keys (F1 - F24)
            *[
                (f"F{i}", 0x6F + i, getattr(Qt.Key, f"Key_F{i}"), [f"f{i}"])
                for i in range(1, 25)
            ],
            # Control / Navigation Keys
            ("Space", 0x20, Qt.Key.Key_Space, [" ", "space"]),
            ("Tab", 0x09, Qt.Key.Key_Tab, ["tab"]),
            ("Backspace", 0x08, Qt.Key.Key_Backspace, ["backspace", "back"]),
            ("Enter", 0x0D, Qt.Key.Key_Return, ["enter", "return", "\n", "\r"]),
            ("Escape", 0x1B, Qt.Key.Key_Escape, ["escape", "esc"]),
            ("Delete", 0x2E, Qt.Key.Key_Delete, ["delete", "del"]),
            ("Insert", 0x2D, Qt.Key.Key_Insert, ["insert", "ins"]),
            ("Home", 0x24, Qt.Key.Key_Home, ["home"]),
            ("End", 0x23, Qt.Key.Key_End, ["end"]),
            ("PageUp", 0x21, Qt.Key.Key_PageUp, ["pageup", "pgup"]),
            ("PageDown", 0x22, Qt.Key.Key_PageDown, ["pagedown", "pgdn"]),
            ("Left", 0x25, Qt.Key.Key_Left, ["left"]),
            ("Up", 0x26, Qt.Key.Key_Up, ["up"]),
            ("Right", 0x27, Qt.Key.Key_Right, ["right"]),
            ("Down", 0x28, Qt.Key.Key_Down, ["down"]),
            # Modifiers
            ("Shift", 0x10, Qt.Key.Key_Shift, ["shift"]),
            ("Ctrl", 0x11, Qt.Key.Key_Control, ["ctrl", "control"]),
            ("Alt", 0x12, Qt.Key.Key_Alt, ["alt"]),
            ("CapsLock", 0x14, Qt.Key.Key_CapsLock, ["capslock", "caps"]),
            ("Win", 0x5B, Qt.Key.Key_Meta, ["win", "windows", "meta"]),
            # Standard Punctuation Symbols
            (",", 0xBC, Qt.Key.Key_Comma, ["comma", "<"]),
            (".", 0xBE, Qt.Key.Key_Period, ["period", ">"]),
            ("/", 0xBF, Qt.Key.Key_Slash, ["slash", "?"]),
            (";", 0xBA, Qt.Key.Key_Semicolon, ["semicolon", ":"]),
            ("'", 0xDE, Qt.Key.Key_Apostrophe, ["apostrophe", "quote", '"']),
            ("[", 0xDB, Qt.Key.Key_BracketLeft, ["bracketleft", "{"]),
            ("]", 0xDD, Qt.Key.Key_BracketRight, ["bracketright", "}"]),
            ("\\", 0xDC, Qt.Key.Key_Backslash, ["backslash", "|"]),
            ("-", 0xBD, Qt.Key.Key_Minus, ["minus", "_"]),
            ("=", 0xBB, Qt.Key.Key_Equal, ["equal", "plus", "+"]),
            ("`", 0xC0, Qt.Key.Key_QuoteLeft, ["quoteleft", "backtick", "~"]),
            # Shifted symbols (added)
            ("~", 0xC0, Qt.Key.Key_QuoteLeft, ["tilde"]),
            ("!", 0x31, Qt.Key.Key_Exclam, ["exclamation", "exclam"]),
            ("@", 0x32, Qt.Key.Key_At, ["at"]),
            ("#", 0x33, Qt.Key.Key_NumberSign, ["numbersign", "hash", "pound"]),
            ("$", 0x34, Qt.Key.Key_Dollar, ["dollar"]),
            ("%", 0x35, Qt.Key.Key_Percent, ["percent"]),
            ("^", 0x36, Qt.Key.Key_AsciiCircum, ["caret", "circumflex"]),
            ("&", 0x37, Qt.Key.Key_Ampersand, ["ampersand", "and"]),
            ("*", 0x38, Qt.Key.Key_Asterisk, ["asterisk", "star"]),
            ("(", 0x39, Qt.Key.Key_ParenLeft, ["parenleft", "leftparen"]),
            (")", 0x30, Qt.Key.Key_ParenRight, ["parenright", "rightparen"]),
            ("_", 0xBD, Qt.Key.Key_Minus, ["underscore", "minus"]),
            ("+", 0xBB, Qt.Key.Key_Equal, ["plus", "equal"]),
            ("{", 0xDB, Qt.Key.Key_BracketLeft, ["leftbrace", "braceleft"]),
            ("}", 0xDD, Qt.Key.Key_BracketRight, ["rightbrace", "braceright"]),
            (":", 0xBA, Qt.Key.Key_Semicolon, ["colon"]),
            ('"', 0xDE, Qt.Key.Key_Apostrophe, ["quotedbl", "doublequote"]),
            ("<", 0xBC, Qt.Key.Key_Comma, ["less", "lessthan"]),
            (">", 0xBE, Qt.Key.Key_Period, ["greater", "greaterthan"]),
            ("?", 0xBF, Qt.Key.Key_Slash, ["question"]),
            ("|", 0xDC, Qt.Key.Key_Backslash, ["bar", "verticalbar"]),
        ]
        # Generate multi-directional conversion dictionaries
        self._str_to_vk = {}
        self._str_to_qt = {}
        self._vk_to_str = {}
        self._vk_to_qt = {}
        self._qt_to_vk = {}
        for primary_str, vk, qt_key, aliases in self._master_table:
            all_strings = [primary_str] + aliases
            for s in all_strings:
                self._str_to_vk[s] = vk
                self._str_to_vk[s.lower()] = vk
                self._str_to_vk[s.upper()] = vk
                self._str_to_qt[s] = qt_key
            if vk not in self._vk_to_str:
                self._vk_to_str[vk] = primary_str
            self._vk_to_qt[vk] = qt_key
            self._qt_to_vk[qt_key] = vk

        self._MOD_MAP = {
            "ctrl": 0x0002,
            "control": 0x0002,
            "shift": 0x0004,
            "alt": 0x0001,
            "win": 0x0008,
        }
        self._MOD_MAP = {
            "alt": 0x0001,
            "menu": 0x0001,  # Alt is also called Menu key
            "control": 0x0002,
            "ctrl": 0x0002,
            "lctrl": 0x0002,
            "rctrl": 0x0002,
            "shift": 0x0004,
            "lshift": 0x0004,
            "rshift": 0x0004,
            "win": 0x0008,
            "windows": 0x0008,
            "lwin": 0x0008,
            "rwin": 0x0008,
        }

    # MOD
    def is_mod(self, key_str: str) -> bool:
        """Check if the string is a recognized modifier."""
        if not key_str:
            return False
        return key_str.strip().lower() in self._MOD_MAP

    def mod_to_vk(self, key_str: str) -> int:
        """Convert modifier name to Windows modifier flag (MOD_xxx)."""
        if not key_str:
            return 0
        return self._MOD_MAP.get(key_str.strip().lower(), 0)

    def mods_to_flags(self, mods: list[str] | str) -> int:
        """Convert list of modifiers like ['ctrl', 'shift'] into combined flag."""
        if isinstance(mods, str):
            mods = [mods]
        flags = 0
        for m in mods:
            flags |= self.mod_to_vk(m)
        return flags

    # Keys
    def str_to_vk(self, key_str: str) -> int:
        """Converts strings like ',', 'F1', 'f12', or 'Enter' safely into Windows VK codes."""
        return self._str_to_vk.get(key_str.strip(), 0)

    def vk_to_str(self, vk: int) -> str:
        """Converts Windows Virtual Key code back into its clean string format."""
        return self._vk_to_str.get(vk, "Unknown")

    def str_to_qt_key(self, key_str: str) -> int:
        """Converts strings directly to a Qt.Key.Key integer constant."""
        return self._str_to_qt.get(key_str.strip(), Qt.Key.Key_unknown)

    def vk_to_qt_key(self, vk: int) -> int:
        """Converts Windows VK code to a Qt.Key integer constant."""
        return self._vk_to_qt.get(vk, Qt.Key.Key_unknown)
