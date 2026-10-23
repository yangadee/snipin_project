from ui.models.tools import Tool

from .image_scene import ImageScene
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QObject


class PinScene(ImageScene):
    def __init__(
        self,
        pixmap: QPixmap | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(pixmap, parent)
        # No drawing by default.
        self.tool = Tool.SELECT
