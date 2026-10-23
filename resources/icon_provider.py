from PyQt6.QtGui import QIcon
import resources.resources_rc


class IconProvider:
    """
    A minimal, high-speed QIcon cache specifically for Qt Resource paths.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._instance._cache = {}
        return cls._instance

    # def __init__(self):
    #     # Key: string (resource path ':/...') -> Value: QIcon object
    #     if not hasattr(self, "_cache"):
    #         self._cache = {}

    def icon(self, name: str) -> QIcon:
        """
        Retrieves the cached icon using the name and extension.
        Defaults extension to 'png' if not specified.
        """
        full_name = name if "." in name else f"{name}.png"

        if full_name in self._cache:
            return self._cache[full_name]

        generated_icon = QIcon(f":/icons/{full_name}")

        # cache full name: ex icon.png
        self._cache[full_name] = generated_icon

        return generated_icon

    def clear(self) -> None:
        """Clears all cached references to free up memory."""
        self._cache.clear()


# Global: Use single shared instance
icon_provider = IconProvider()
