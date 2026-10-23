from abc import ABC, abstractmethod
from PyQt6.QtGui import QIcon


class PluginBase(ABC):
    """
    Abstract Base Class that serves as a rigid contract for all application plugins.
    """

    # Names aligned PEP-8
    NAME = ""
    ICON = ""
    TYPE = ""
    VERSION = ""
    DESCRIPTION = ""
    DEFAULT_HOTKEY = ""

    def __init__(self):
        # This will hold the core API instance after initialization
        self.api = None

    def initialize(self, api) -> None:
        """
        Dependency injection method. Stores the core application API instance.
        """
        self.api = api

    @abstractmethod
    def run(self, *args, **kwargs):
        """
        The main execution entry point for the plugin. Must be overridden.
        """
        pass

    def cleanup(self):
        """
        Clean up before delete.
        """
        pass
