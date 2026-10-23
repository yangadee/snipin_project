from sdk.models import PluginInfo, PluginStatus
from resources import icon_provider
from ui.models.tool_options import PluginOptions
from ui.toolbar.widgets import PluginButton

from .base import OptionsPage
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtCore import pyqtSignal


class PluginOptionsPage(OptionsPage):
    pluginSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = None
        # self._buttons = {}
        self._buttons: dict[str, PluginButton] = {}

    def set_options(self, options: PluginOptions):
        self.options = options

    # def _set_plugins(self, plugins: list[PluginInfo] | tuple[PluginInfo, ...]):
    #     self.clear_plugins()
    #     self.start()
    #     for info in plugins:
    #         button = QToolButton(self)
    #         icon = icon_provider.icon(info.icon)
    #         button.setIcon(icon)
    #         button.setToolTip(info.tooltip or info.name)
    #         button.clicked.connect(
    #             lambda checked=False, pid=info.plugin_id: self._select_plugin(pid)
    #         )
    #         self.layout.addWidget(button)
    #         self._buttons[info.plugin_id] = button
    #     self.finish()

    def set_plugins(
        self,
        plugins: list[PluginInfo] | tuple[PluginInfo, ...],
    ):
        self.clear_plugins()
        self.start()
        for info in plugins:
            button = PluginButton(
                plugin_id=info.plugin_id,
                icon=icon_provider.icon(info.icon),
                tooltip=info.tooltip or info.name,
                parent=self,
            )
            button.clicked.connect(
                lambda checked=False, pid=info.plugin_id: self._select_plugin(pid)
            )
            self.layout.addWidget(button)
            self._buttons[info.plugin_id] = button
        self.finish()

    def set_plugin_status(self, plugin_id: str, status: PluginStatus):
        button = self._buttons.get(plugin_id)
        if button is None:
            return
        button.set_status(status)

    def _select_plugin(self, plugin_id: str):
        # if self.options is not None:
        #     self.options.selected_plugin_id = plugin_id
        self.pluginSelected.emit(plugin_id)

    # def clear_plugins(self):
    #     for button in self._buttons.values():
    #         self.layout.removeWidget(button)
    #         button.deleteLater()
    #     self._buttons.clear()

    def clear_plugins(self) -> None:
        """
        Clear everything from page layout.
        """
        while self.layout.count():
            item = self.layout.takeAt(0)  # pop()
            if widget := item.widget():
                widget.deleteLater()
        self._buttons.clear()
