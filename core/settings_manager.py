from __future__ import annotations
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QSettings
import copy
from enum import Enum
from pathlib import Path
from typing import Any
from dataclasses import fields, is_dataclass


class SettingsManager:
    """
    Version 2.0
    Persistent application settings backed by QSettings/INI.

    DEFAULTS is the schema and source of default values.
    QSettings stores only persisted overrides.

    Runtime reads:
        settings.value(key, default)

    Runtime writes:
        settings.setValue(key, value)
    """

    DEFAULTS = {
        "general": {
            "language": "English",
            "run_on_startup": False,
            "hit_testing_enabled": True,
            "hint_panel_enabled": True,
            "cursor_magnifier_enabled": True,
            "win_mouse_capture_enabled": True,
            "capture_cursor_enabled": False,
            "max_stored_pins": 10,
            "log_level": "Info",
            "config_path": "snipin.ini",
        },
        "hotkeys": {
            "capture_area": "F1",
            "capture_fullscreen": "Ctrl+Shift+F",
            "restore_pin": "Shift+F3",
            "pin_clipboard": "F3",
            "reopen_app": "Shift+F6",
            "reload_plugins": "Shift+F5",
            "exit_app": "Ctrl+Q",
        },
        "plugins": {
            "enable": True,
        },
    }

    def __init__(self, config_path: str | Path = "snipin.ini"):
        self.config_path = str(config_path)
        self.settings = QSettings(self.config_path, QSettings.Format.IniFormat)

    @property
    def hit_testing_enabled(self) -> bool:
        return self.get("General/hit_testing_enabled", True, type_=bool)

    @property
    def hint_panel_enabled(self) -> bool:
        return self.get("General/hint_panel_enabled", True, type_=bool)

    @property
    def cursor_magnifier_enabled(self) -> bool:
        return self.get("General/cursor_magnifier_enabled", True, type_=bool)

    @property
    def capture_cursor_enabled(self) -> bool:
        return self.get("General/capture_cursor_enabled", False, type_=bool)

    @property
    def max_stored_pins(self) -> int:
        return self.get("General/max_stored_pins", 10, type_=int)

    # ========================================================
    # Generic API
    # ========================================================
    def get(self, key: str, default: Any = None, type_: Any = None):
        """
        Read a setting.
        If default is omitted, try to obtain it from DEFAULTS.
        """
        if default is None:
            default = self._default_for_key(key)

        # Explicit type requested
        if type_ is not None:
            return self.settings.value(key, default, type=type_)

        # Otherwise infer/convert from default
        value = self.settings.value(key, self._serialize_value(default))
        return self._convert_value(value, default)

    def set(self, key: str, value):
        """
        Save a single setting.
        """
        self.settings.setValue(key, self._serialize_value(value))

    def contains(self, key: str) -> bool:
        return self.settings.contains(key)

    def remove(self, key: str):
        self.settings.remove(key)

    def sync(self):
        """
        Explicitly flush changes to storage.

        Normally call this during application shutdown rather
        than after every small setting update.
        """
        self.settings.sync()

    # ========================================================
    # Section API
    # ========================================================

    def get_general(self) -> dict:
        return self._load_section("general")

    def get_hotkeys(self) -> dict:
        return self._load_section("hotkeys")

    def get_plugins_settings(self) -> dict:
        return self._load_section("plugins")

    def get_tool_settings(self) -> dict:
        return self._load_nested_section("tools")

    def data(self) -> dict:
        """
        Return the complete currently effective configuration.

        DEFAULTS provides missing values and QSettings overrides
        the values that were persisted by the user.
        """
        return {
            "general": self.get_general(),
            "hotkeys": self.get_hotkeys(),
            "plugins": self.get_plugins_settings(),
            "tools": self.get_tool_settings(),
        }

    # ========================================================
    # Section updates
    # ========================================================
    def update_general(self, values: dict):
        self._save_section("general", values)

    def update_hotkeys(self, values: dict):
        self._save_section("hotkeys", values)

    def update_plugins(self, values: dict):
        self._save_section("plugins", values)

    def update_tools(self, tools: dict):
        for tool_name, values in tools.items():
            if not isinstance(values, dict):
                continue
            self._save_section(f"tools/{tool_name}", values)

    def set_all(self, data: dict):
        """
        Persist supplied settings.

        Unknown sections are intentionally ignored here.
        """
        general = data.get("general")
        if isinstance(general, dict):
            self.update_general(general)
        hotkeys = data.get("hotkeys")
        if isinstance(hotkeys, dict):
            self.update_hotkeys(hotkeys)
        plugins = data.get("plugins")
        if isinstance(plugins, dict):
            self.update_plugins(plugins)
        tools = data.get("tools")
        if isinstance(tools, dict):
            self.update_tools(tools)

    # ========================================================
    # Tool dataclass support
    # ========================================================

    def load_tool_options(self, tool, options):
        """
        Load persisted fields directly into a ToolOptions dataclass.

        Existing dataclass values are used as defaults, which means
        the dataclass itself remains the runtime source of default
        tool behavior.
        """
        if not is_dataclass(options):
            return
        prefix = f"tools/{tool.name.lower()}"
        for field in fields(options):
            current = getattr(options, field.name)
            key = f"{prefix}/{field.name}"
            value = self.settings.value(key, self._serialize_value(current))
            value = self._convert_value(value, current)
            setattr(options, field.name, value)

    def save_tool_options(self, tool, options):
        """
        Persist the current values of a ToolOptions dataclass.
        """
        if not is_dataclass(options):
            return
        prefix = f"tools/{tool.name.lower()}"
        for field in fields(options):
            value = getattr(options, field.name)
            key = f"{prefix}/{field.name}"

            self.settings.setValue(key, self._serialize_value(value))

    # ========================================================
    # Reset support
    # ========================================================
    def reset_all(self):
        """
        Remove every persisted override.

        Effective values then come entirely from DEFAULTS.
        """
        self.settings.clear()

    def reset_section(self, section: str):
        self.settings.remove(section)

    def reset_tool(self, tool):
        self.settings.remove(f"tools/{tool.name.lower()}")

    # ========================================================
    # Internal section helpers
    # ========================================================

    def __load_section(self, section: str) -> dict:
        defaults = self.DEFAULTS.get(section, {})
        result = {}
        for key, default in defaults.items():
            full_key = f"{section}/{key}"
            value = self.settings.value(full_key, self._serialize_value(default))
            result[key] = self._convert_value(value, default)
        return result

    def _load_section(self, section: str) -> dict:
        defaults = self.DEFAULTS.get(section, {})
        result = {}
        self.settings.beginGroup(section)
        try:
            # Load ALL existing settings first
            for key in self.settings.childKeys():
                value = self.settings.value(key)
                if key in defaults:
                    value = self._convert_value(value, defaults[key])
                result[key] = value
            # Add defaults that don't exist in INI
            for key, default in defaults.items():
                if key not in result:
                    result[key] = default
        finally:
            self.settings.endGroup()
        return result

    def _load_nested_section(self, section: str) -> dict:
        defaults = self.DEFAULTS.get(section, {})
        result = {}
        for group_name, group_defaults in defaults.items():
            if not isinstance(group_defaults, dict):
                continue
            result[group_name] = {}
            for key, default in group_defaults.items():
                full_key = f"{section}/" f"{group_name}/" f"{key}"
                value = self.settings.value(full_key, self._serialize_value(default))
                result[group_name][key] = self._convert_value(value, default)
        return result

    def _save_section(self, section: str, values: dict):
        for key, value in values.items():
            full_key = f"{section}/{key}"
            self.settings.setValue(full_key, self._serialize_value(value))

    # ========================================================
    # Defaults
    # ========================================================

    def _default_for_key(self, key: str):
        """
        Resolve:
            general/log_level
        or:
            tools/pen/color
        from DEFAULTS.
        """
        parts = [part for part in key.split("/") if part]
        value = self.DEFAULTS
        for part in parts:
            if not isinstance(value, dict):
                return None
            if part not in value:
                return None
            value = value[part]
        return copy.deepcopy(value)

    # ========================================================
    # Serialization
    # ========================================================

    @staticmethod
    def _serialize_value(value):
        if isinstance(value, QColor):
            # If alpha matters, use HexArgb instead.
            return value.name(QColor.NameFormat.HexRgb).upper()

        if isinstance(value, Enum):
            return value.value

        return value

    @staticmethod
    def _convert_value(value, default):
        if default is None:
            return value

        if isinstance(default, QColor):
            return QColor(value)

        # must check Enum first
        if isinstance(default, Enum):
            try:
                return type(default)(value)
            except (TypeError, ValueError):
                return default

        if isinstance(default, bool):
            if isinstance(value, bool):
                return value

            if isinstance(value, str):
                return value.strip().lower() in {
                    "true",
                    "1",
                    "yes",
                    "on",
                }

            return bool(value)

        # bool is also int in Python, therefore bool
        # MUST be tested above int.
        if isinstance(default, int):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        if isinstance(default, float):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        if isinstance(default, str):
            return str(value)

        return value

    # ========================================================
    # QColor convenience
    # ========================================================

    @staticmethod
    def qcolor_to_hex(color):
        if isinstance(color, QColor):
            return color.name().upper()

        if isinstance(color, str):
            return QColor(color).name().upper()

        return "#FF0000"

    @staticmethod
    def hex_to_qcolor(value):
        return QColor(value)


# class _SettingsManager:
#     """
#     version 1.0: JSON.
#     Load/save app settings and provide merged defaults.
#     """

#     DEFAULTS = {
#         "general": {
#             "log_level": "Info",
#             "run_on_startup": False,
#             "max_closed_pins": 10,
#         },
#         "hotkeys": {
#             "capture_area": "F1",
#             "capture_fullscreen": "Ctrl+Shift+F",
#             "restore_pin": "Shift+F3",
#             "pin_clipboard": "F3",
#             "reopen_app": "F6",
#             "reload_plugins": "F5",
#             "exit_app": "Ctrl+Q",
#         },
#         "plugins": {
#             "enable": True,
#         },
#         "tools": {
#             "select": {},
#             "pen": {
#                 "color": "#FF0000",
#                 "width": 3,
#                 "highlight": False,
#             },
#             "line": {
#                 "color": "#FF0000",
#                 "width": 3,
#                 "highlight": False,
#             },
#             "arrow": {
#                 "color": "#FF0000",
#                 "width": 3,
#             },
#             "rect": {
#                 "color": "#FF0000",
#                 "width": 3,
#                 "fill": False,
#                 "fill_capacity": 50,
#                 "highlight": False,
#                 "fill_color": "#FFFF00",
#             },
#             "ellipse": {
#                 "color": "#FF0000",
#                 "width": 3,
#                 "fill": False,
#                 "fill_capacity": 50,
#                 "highlight": False,
#                 "fill_color": "#FFFF00",
#             },
#             "text": {
#                 "color": "#FF0000",
#                 "font_size": 20,
#             },
#             "mosaic": {
#                 "brush_size": 28,
#                 "block_size": 3,
#                 "blur_mode": False,
#             },
#         },
#     }

#     def __init__(self, config_path="snipin.ini"):
#         self.config_path = config_path
#         self._data = self.load()
#         self.settings = QSettings(config_path, QSettings.Format.IniFormat)

#     # ====================================================
#     # PUBLIC API
#     # ====================================================
#     def data(self):
#         return copy.deepcopy(self._data)

#     def get_hotkeys(self):
#         return copy.deepcopy(self._data["hotkeys"])

#     def get_tool_settings(self):
#         return copy.deepcopy(self._data["tools"])

#     def get_general(self):
#         return copy.deepcopy(self._data["general"])

#     def get_plugins_settings(self):
#         return copy.deepcopy(self._data["plugins"])

#     def set_all(self, new_data):
#         merged = self._merge_defaults(copy.deepcopy(new_data))
#         self._data = merged
#         self.save()

#     def update_hotkeys(self, hotkeys_dict):
#         self._data["hotkeys"] = copy.deepcopy(hotkeys_dict)
#         self._data = self._merge_defaults(self._data)
#         self.save()

#     def update_tools(self, tools_dict):
#         self._data["tools"] = copy.deepcopy(tools_dict)
#         self._data = self._merge_defaults(self._data)
#         self.save()

#     def update_general(self, general_dict):
#         self._data["general"] = copy.deepcopy(general_dict)
#         self._data = self._merge_defaults(self._data)
#         self.save()

#     # ====================================================
#     # LOAD / SAVE
#     # ====================================================

#     def load(self):
#         """
#         load settings either from DEFAULTS or .ini file,
#         and compare it. DEFAULTS is master.
#         """
#         if not os.path.isfile(self.config_path):
#             return copy.deepcopy(self.DEFAULTS)
#         try:
#             with open(self.config_path, "r", encoding="utf-8") as f:
#                 raw = json.load(f)
#             return self._merge_defaults(raw)

#         except Exception as e:
#             print("Settings load failed:", e)
#             logging.error("Settings load failed")
#             return copy.deepcopy(self.DEFAULTS)

#     def save(self):
#         try:
#             serializable = copy.deepcopy(self._data)
#             with open(self.config_path, "w", encoding="utf-8") as f:
#                 json.dump(serializable, f, indent=4, ensure_ascii=False)
#         except Exception as e:
#             print("Settings save failed:", e)
#             logging.error("Settings save failed")

#     def load_tool_options(self, tool: Tool, options):
#         if not is_dataclass(options):
#             return
#         prefix = f"tools/{tool.name.lower()}"
#         for field in fields(options):
#             current = getattr(options, field.name)
#             key = f"{prefix}/{field.name}"
#             value = self.settings.value(key, current)
#             value = self._convert_value(value, current)
#             setattr(options, field.name, value)

#     def save_tool_options(self, tool: Tool, options):
#         if not is_dataclass(options):
#             return
#         prefix = f"tools/{tool.name.lower()}"
#         for field in fields(options):
#             value = getattr(options, field.name)
#             key = f"{prefix}/{field.name}"
#             self.settings.setValue(key, self._serialize_value(value))

#     def _serialize_value(self, value):
#         if isinstance(value, QColor):
#             return value.name(QColor.NameFormat.HexArgb)

#         if isinstance(value, Enum):
#             return value.value

#         return value

#     def _convert_value(self, value, default):
#         if isinstance(default, QColor):
#             return QColor(value)

#         if isinstance(default, bool):
#             if isinstance(value, str):
#                 return value.lower() in (
#                     "true",
#                     "1",
#                     "yes",
#                 )

#             return bool(value)

#         if isinstance(default, int):
#             return int(value)

#         if isinstance(default, float):
#             return float(value)

#         if isinstance(default, Enum):
#             return type(default)(value)

#         return value

#     # ====================================================
#     # HELPERS
#     # ====================================================
#     def _merge_defaults(self, data):
#         """
#         Read compare the .ini settings with DEFAULTS,
#         copy value from .ini file if not in DEFAULTS.
#         DEFAULTS is master
#         """
#         result = copy.deepcopy(self.DEFAULTS)
#         for section, section_value in data.items():
#             if section not in result:
#                 result[section] = section_value
#                 continue

#             if isinstance(result[section], dict) and isinstance(section_value, dict):
#                 for key, value in section_value.items():
#                     if (
#                         key in result[section]
#                         and isinstance(result[section][key], dict)
#                         and isinstance(value, dict)
#                     ):
#                         result[section][key].update(value)
#                     else:
#                         result[section][key] = value
#             else:
#                 result[section] = section_value

#         return result

#     @staticmethod
#     def qcolor_to_hex(color):
#         if isinstance(color, QColor):
#             return color.name().upper()
#         if isinstance(color, str):
#             return QColor(color).name().upper()
#         return "#FF0000"

#     @staticmethod
#     def hex_to_qcolor(value):
#         return QColor(value)
