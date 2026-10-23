import importlib
from pathlib import Path
import pkgutil
from typing import Iterable, Iterator
from PyQt6.QtCore import QObject
from sdk.models import PluginCapability, PluginInfo, PluginRecord
import logging
from types import ModuleType
import sys
import gc


def iter_modules(
    path: Iterable[str] | None = None, prefix: str = ""
) -> Iterator[pkgutil.ModuleInfo]:
    """
    Compatible wrapper around pkgutil.iter_modules().

    Uses pkgutil normally. If pkgutil finds nothing for an existing
    filesystem path, falls back to filesystem scanning.

    Returns:
        pkgutil.ModuleInfo(module_finder, name, ispkg)
    """

    # # ---------------------------------------------------------
    # # Normal pkgutil behavior
    # # ---------------------------------------------------------
    # modules = list(pkgutil.iter_modules(path, prefix))

    # if modules:
    #     yield from modules
    #     return

    # ---------------------------------------------------------
    # Filesystem fallback is intended for package.__path__,
    # ---------------------------------------------------------
    if path is None:
        return

    # ---------------------------------------------------------
    # Nuitka/filesystem fallback
    # ---------------------------------------------------------
    found = set()
    extension_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    for package_path in path:
        directory = Path(package_path)
        if not directory.is_dir():
            continue
        # Equivalent finder for a normal filesystem path.
        finder = pkgutil.get_importer(str(directory))
        for entry in directory.iterdir():
            # -------------------------------------------------
            # Ignore things such as: __pycache__, __init__.py
            # -------------------------------------------------
            if entry.name == "__pycache__":
                continue
            # -------------------------------------------------
            # Package
            # -------------------------------------------------
            if entry.is_dir():
                if not (entry / "__init__.py").is_file():
                    continue

                short_name = entry.name
                ispkg = True
            # -------------------------------------------------
            # Python source
            # -------------------------------------------------
            elif entry.is_file() and entry.suffix == ".py":
                short_name = entry.stem
                if short_name == "__init__":
                    continue
                ispkg = False

            # -------------------------------------------------
            # Extension module
            # -------------------------------------------------
            elif entry.is_file():
                short_name = None
                for suffix in extension_suffixes:
                    if entry.name.endswith(suffix):
                        short_name = entry.name[: -len(suffix)]
                        break
                if not short_name:
                    continue
                ispkg = False
            else:
                continue

            # -------------------------------------------------
            # Avoid duplicates.
            # -------------------------------------------------
            full_name = prefix + short_name
            if full_name in found:
                continue
            found.add(full_name)
            yield pkgutil.ModuleInfo(
                finder,
                full_name,
                ispkg,
            )


class PluginManager:
    def __init__(self, api, parent=None):
        self.api = api
        # self._plugins = {}
        self.loaded_plugin_modules: dict[str, ModuleType] = {}
        self._plugins: dict[str, PluginRecord] = {}
        # Track whether a plugin is currently enabled or disabled
        self.plugin_states = {}

    @property
    def plugins(self) -> dict[str, PluginRecord]:
        return self._plugins

    def plugin_infos(self) -> tuple[PluginInfo, ...]:
        infos = []
        for record in self._plugins.values():
            if not record.is_loaded:
                continue
            plugin = record.instance
            if plugin is None:
                continue
            infos.append(
                PluginInfo(
                    plugin_id=record.plugin_id,
                    name=getattr(plugin, "NAME", record.plugin_id),
                    icon=getattr(plugin, "ICON", ""),
                    tooltip=getattr(plugin, "DESCRIPTION", ""),
                    enabled=record.enabled,
                )
            )
        return tuple(infos)

    # def get_plugin(self, plugin_id: str):
    #     return self._plugins.get(plugin_id)

    def get_plugin_info(self, plugin_id: str) -> PluginInfo | None:
        record = self._plugins.get(plugin_id)
        if record is None:
            return None
        instance = record.instance
        module = record.module

        if instance is None and module is None:
            return None

        # Prefer instance metadata, then module metadata,
        # finally fall back to plugin_id.
        source = instance or module

        return PluginInfo(
            plugin_id=record.plugin_id,
            name=getattr(source, "NAME", record.plugin_id),
            icon=getattr(source, "ICON", ""),
            tooltip=getattr(source, "DESCRIPTION", ""),
            hotkey=getattr(source, "DEFAULT_HOTKEY", ""),
            enabled=record.enabled,
        )

    def plugin_infos_for(self, capability: PluginCapability) -> tuple[PluginInfo, ...]:
        infos = []
        for record in self._plugins.values():
            if not record.enabled:
                continue
            if capability not in record.capabilities:
                continue
            info = self.get_plugin_info(record.plugin_id)
            if info is not None:
                infos.append(info)
        return tuple(infos)

    def records_for(self, capability: PluginCapability):
        return tuple(
            record
            for record in self._plugins.values()
            if (
                record.enabled
                and record.is_loaded
                and capability in record.capabilities
            )
        )

    def get_plugin(self, plugin_id: str, capability: PluginCapability | None = None):
        record = self._plugins.get(plugin_id)
        if record is None:
            return None
        if not record.is_available:
            return None
        if capability is not None and capability not in record.capabilities:
            return None
        return record.instance

    def _parse_capabilities(self, values) -> frozenset:
        """
        Convert from string Set() to PluginCapability
        """
        result = set()
        for value in values:
            try:
                result.add(PluginCapability(value))
            except (ValueError, TypeError):
                logging.warning("Unknown plugin capability: %r", value)
        return frozenset(result)

    def unload_all(self):
        """
        Safe Unload all loaded plugins. Ignor all error
        """
        for plugin_id, _ in list(self._plugins.items()):
            try:
                self.unload_plugin(plugin_id)
            except Exception:
                pass

    def unload_plugin(self, plugin_id: str) -> bool:
        """Unregister and unload one plugin."""
        record = self._plugins.get(plugin_id)

        if record is None:
            logging.debug("Plugin '%s' is not registered.", plugin_id)
            return False

        try:
            plugin_instance = record.instance
            module_name = record.module.__name__

            # Unregister the plugin hotkey first.
            if record.hotkey_id is not None:
                self.api.unregister_hotkey_id(
                    hotkey_id=record.hotkey_id,
                )

            # Run plugin-specific cleanup.
            cleanup = getattr(plugin_instance, "cleanup", None)
            if callable(cleanup):
                cleanup()

            # Schedule QObject deletion through the Qt event loop.
            delete_later = getattr(plugin_instance, "deleteLater", None)
            if callable(delete_later):
                delete_later()

            # Remove the plugin record only after cleanup succeeds.
            self._plugins.pop(plugin_id, None)

            # Remove the plugin module and its submodules.
            for loaded_module_name in list(sys.modules):
                if loaded_module_name == module_name or loaded_module_name.startswith(
                    module_name + "."
                ):
                    sys.modules.pop(loaded_module_name, None)

            importlib.invalidate_caches()
            gc.collect()

            logging.debug(
                "Unloaded plugin '%s' from module '%s'.", plugin_id, module_name
            )
            return True

        except Exception:
            logging.exception("Failed to unload plugin '%s'.", plugin_id)
            return False

    def inspect_and_register_module(
        self,
        module: ModuleType,
        target_attr: str = "create_plugin",
    ) -> list[PluginRecord]:
        """
        Discover a plugin in a module and register its PluginRecord.
        Support mutiple plugins in a module
        """
        plugin = None
        plugins = []
        # Tier 1: Try explicit factory function
        factory = getattr(module, target_attr, None)
        if callable(factory):
            result = factory()
            if result is not None:
                # Factory can return one plugin or multiple plugins
                if isinstance(result, (list, tuple, set)):
                    plugins.extend(result)
                else:
                    plugins.append(result)

        # Tier 2: Fallback duck-typing class scan
        if not plugins:
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(module, attr_name)

                if not isinstance(attr, type):
                    continue

                # Avoid detecting classes imported from another module
                if attr.__module__ != module.__name__:
                    continue
                if all(
                    callable(getattr(attr, method, None))
                    for method in ("initialize", "run")
                ):
                    plugins.append(attr)

        if not plugins:
            logging.warning("No valid plugin found in module '%s'.", module.__name__)
            return []

        # ==========================================================
        # Register all plugins
        # ==========================================================
        records = []
        for plugin in plugins:
            try:
                # Class or instance
                plugin_instance = plugin() if isinstance(plugin, type) else plugin

                plugin_class = plugin_instance.__class__
                module_name = plugin_class.__module__
                plugin_name = plugin_class.__name__
                plugin_id = f"{module_name}.{plugin_name}"
                # --------------------------------------------------
                # Initialize
                # --------------------------------------------------
                initialize = getattr(plugin_instance, "initialize", None)
                if callable(initialize):
                    initialize(self.api)
                # --------------------------------------------------
                # Duplicate
                # --------------------------------------------------
                if plugin_id in self._plugins:
                    logging.warning(
                        "Plugin '%s' is already registered. Overwriting.", plugin_id
                    )

                # --------------------------------------------------
                # Hotkey
                # --------------------------------------------------
                hotkey_seq = getattr(plugin_instance, "DEFAULT_HOTKEY", "")

                if hotkey_seq:
                    self.api.register_hotkey(
                        hotkey_id=plugin_id,
                        hotkey_seq=hotkey_seq,
                        owner=module,
                        callback=plugin_instance.run,
                    )

                hotkey_id = plugin_id if hotkey_seq else None

                # --------------------------------------------------
                # Record
                # --------------------------------------------------
                capabilities = getattr(plugin_instance, "CAPABILITIES", ())
                record = PluginRecord(
                    plugin_id=plugin_id,
                    capabilities=self._parse_capabilities(capabilities),
                    module=module,
                    instance=plugin_instance,
                    hotkey_id=hotkey_id,
                )
                self._plugins[plugin_id] = record
                records.append(record)

                logging.debug("[Plugin] Registered plugin: %s", plugin_id)

            except Exception:
                logging.exception(
                    "[Plugin]Failed to register plugin '%s' from module '%s'.",
                    plugin,
                    module.__name__,
                )
        return records

    def load_dynamic_plugins(self, package_name: str = "plugins") -> None:
        """
        Dynamically scan and import submodules inside a package
        using pkgutil.iter_modules and importlib.import_module.
        """
        try:
            parent_package = importlib.import_module(package_name)
        except ImportError as e:
            logging.exception(
                "[Import Error] Failed to import parent package '%s'.",
                package_name,
            )
            return

        # modules = list(
        #     iter_modules(parent_package.__path__, parent_package.__name__ + ".")
        # )
        # print("found:", modules)

        try:
            for module_info in pkgutil.iter_modules(
                parent_package.__path__, parent_package.__name__ + "."
            ):
                # ---------------------------------------
                # Ignore plugin start with _
                # ---------------------------------------
                short_name = module_info.name.split(".")[-1]
                if short_name.startswith("_"):
                    continue
                # ---------------------------------------
                # Start Load
                # ---------------------------------------
                try:
                    module = importlib.import_module(module_info.name)
                    # e.g module_info.name : plugins.clipboard_findit
                    # Keep track of loaded modules
                    self.loaded_plugin_modules[module_info.name] = module
                    self.inspect_and_register_module(module)

                except Exception as e:
                    logging.exception(
                        "[ERROR] Failed to load module %s", module_info.name
                    )
        finally:
            return

    def execute_plugin(self, plugin_id, *args, **kwargs):
        """Execute a specific enabled plugin."""
        record = self._plugins.get(plugin_id)
        if record is None or not record.enabled:
            return None

        if record.instance is None:
            logging.warning("Plugin '%s' is enabled but not loaded.", plugin_id)
            return None

        run = getattr(record.instance, "run", None)
        if not callable(run):
            logging.error("Plugin '%s' has no callable run method.", plugin_id)
            return None

        return run(*args, **kwargs)

    def shutdown(self):
        self.unload_all()

    # ================================================
    # Grave yard
    # ================================================
    # def _register_plugin(self, plugin):
    #     """
    #     Registers a new plugin. Automatically prevents duplicate registration.
    #     """
    #     if isinstance(plugin, type):
    #         plugin_instance = plugin()
    #         module = plugin.__module__  # Ocr_Findit
    #         cls_name = plugin.__name__  # plugins.ocr_findit
    #     else:
    #         plugin_instance = plugin
    #         module = plugin.__class__.__module__
    #         cls_name = plugin.__class__.__name__

    #     if hasattr(plugin_instance, "initialize"):
    #         plugin_instance.initialize(self.api)

    #     if hasattr(plugin_instance, "NAME"):
    #         plugin_id = plugin_instance.NAME
    #         logging.info(f"[Registered] plugin: {plugin_instance.NAME}")
    #         if getattr(plugin_instance, "DEFAULT_HOTKEY", ""):
    #             hotkey_seq = plugin_instance.DEFAULT_HOTKEY
    #             self.api.register_hotkey(
    #                 hotkey_id=cls_name,
    #                 hotkey_seq=hotkey_seq,
    #                 owner=module,
    #                 callback=plugin_instance.run,
    #             )
    #     else:
    #         logging.error(f"Failed to get plugin_id {plugin_instance.NAME}")

    #     if plugin_id in self._plugins:
    #         logging.warning(
    #             f"Warning: Plugin '{plugin_id}' is already registered. Overwriting."
    #         )

    #     self._plugins[plugin_id] = plugin_instance
    #     self.plugin_states[plugin_id] = True  # Enabled by default

    # def _inspect_and_register_module(self, module, target_attr="create_plugin") -> None:
    #     """Scan a module for subclasses of BasePlugin and register them."""
    #     # Tier 1: Try explicit factory function
    #     factory = getattr(module, target_attr, None)
    #     if factory and callable(factory):
    #         func = getattr(module, target_attr)
    #         if callable(func):
    #             plugin_cls = func()  # <- fuction call
    #             self.register_plugin(plugin_cls)
    #             return

    #     # Tier 2: Fallback Duck-Typing trait scan for classes
    #     for attr in (getattr(module, x) for x in dir(module) if not x.startswith("_")):
    #         if isinstance(attr, type):  # and attr.__name__ != "PluginBase":
    #             # Check if class has both callable 'initialize' and 'run' methods
    #             if all(callable(getattr(attr, m, None)) for m in ("initialize", "run")):
    #                 plugin_cls = attr
    #                 self.register_plugin(plugin_cls)
    #                 return

    # def _unload_plugin(self, plugin_id: str) -> bool:
    #     """
    #     Unregister one plugin and remove its module from sys.modules.

    #     Example:
    #         self.unload_plugin("clipboard_findit")
    #     """
    #     plugin = self._plugins.get(plugin_id)

    #     if plugin is None:
    #         logging.info(
    #             "Plugin '%s' is not registered.",
    #             plugin_id,
    #         )
    #         return False

    #     try:
    #         # Support either a stored plugin class or plugin instance
    #         if isinstance(plugin, type):
    #             module_name = plugin.__module__
    #             cls_name = plugin.__name__
    #         else:  # instance
    #             module_name = plugin.__class__.__module__
    #             cls_name = plugin.__class__.__name__

    #             # cleanup() normally belongs to the plugin instance
    #             cleanup = getattr(plugin, "cleanup", None)

    #             if callable(cleanup):
    #                 cleanup()

    #             if getattr(plugin, "DEFAULT_HOTKEY", ""):
    #                 self.api.unregister_hotkey_id(
    #                     hotkey_id=cls_name,
    #                 )

    #             # Schedule QObject deletion safely through the Qt event loop.
    #             delete_later = getattr(plugin, "deleteLater", None)
    #             if callable(delete_later):
    #                 delete_later()

    #         # Remove plugin reference from manager
    #         self._plugins.pop(plugin_id, None)
    #         self.plugin_states.pop(plugin_id, None)

    #         # Remove the module and its submodules from import cache
    #         for loaded_module_name in list(sys.modules):
    #             if loaded_module_name == module_name or loaded_module_name.startswith(
    #                 module_name + "."
    #             ):
    #                 sys.modules.pop(loaded_module_name, None)

    #         importlib.invalidate_caches()
    #         gc.collect()

    #         logging.info(
    #             "Unloaded plugin '%s' from module '%s'.", plugin_id, module_name
    #         )
    #         return True

    #     except Exception:
    #         logging.exception("Failed to unload plugin '%s'.", plugin_id)
    #         return False
