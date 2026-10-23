from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QTextCursor
from PyQt6.QtWidgets import QGraphicsTextItem

# ============================================================
# EDITABLE TEXT ITEM
# ============================================================


class EditableTextItem(QGraphicsTextItem):
    """A movable and editable text item for QGraphicsScene with placeholder support."""

    def __init__(
        self,
        placeholder: str = "Type here...",
        font_size: int = 20,
        color: QColor | tuple | str = QColor(0, 0, 0),
        font_family: str = "Arial",
    ):
        super().__init__(placeholder)

        self.placeholder = placeholder
        self.is_empty = True

        self.text_color = QColor(color)
        self.font_size = font_size
        self.font_family = font_family

        # Initial appearance (placeholder style)
        self.setDefaultTextColor(QColor(120, 120, 120))
        self.setFont(QFont(self.font_family, self.font_size))
        # self.setFont(QFont(self.font_family))

        # Make the item interactive
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsFocusable, True)

        # Start with no text interaction (editing enabled on double-click)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    # =============================================================
    # EDITING CONTROL
    # =============================================================

    def enable_editing(self) -> None:
        """Enable text editing and place cursor at the end."""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def disable_editing(self) -> None:
        """Disable text editing and remove focus."""
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.clearFocus()

    def is_editing(self) -> bool:
        return bool(
            self.textInteractionFlags() & Qt.TextInteractionFlag.TextEditorInteraction
        )

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if (
                self.textInteractionFlags()
                & Qt.TextInteractionFlag.TextEditorInteraction
            ):
                self.disable_editing()
                event.accept()
                return
        super().keyPressEvent(event)

    # =============================================================
    # STYLING
    # =============================================================

    def apply_style(
        self,
        font_size: int | None = None,
        color: QColor | tuple | str | None = None,
        font_family: str | None = None,
    ) -> None:
        """Update font and color settings."""
        if font_size is not None:
            self.font_size = font_size
        if color is not None:
            self.text_color = QColor(color)
        if font_family is not None:
            self.font_family = font_family

        self.setFont(QFont(self.font_family, self.font_size))

        if not self.is_empty:
            self.setDefaultTextColor(self.text_color)

    # =============================================================
    # EVENT HANDLERS
    # =============================================================
    def mouseDoubleClickEvent(self, event):
        """Enable editing when user double-clicks the text."""
        self.enable_editing()
        super().mouseDoubleClickEvent(event)

    def focusInEvent(self, event):
        """Remove placeholder when user starts editing."""
        if self.is_empty:
            self.setPlainText("")
            self.setDefaultTextColor(self.text_color)
            self.is_empty = False

        super().focusInEvent(event)

    def focusOutEvent(self, event):
        """Remove item if empty, otherwise disable editing."""
        if self.toPlainText().strip() == "":
            if self.scene():
                self.scene().removeItem(self)
        else:
            self.disable_editing()
        super().focusOutEvent(event)

    def wheelEvent_(self, event):
        # 1. Check if Ctrl is pressed AND the text item currently has focus
        is_ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if is_ctrl and self.hasFocus():
            # 2. Get current font from the item
            current_font = self.font()
            current_size = current_font.pointSize()

            # 3. Determine wheel direction (delta > 0 means scrolling up)
            # Standard mouse wheel step is 120
            step = 1 if event.angleDelta().y() > 0 else -1

            # 4. Calculate new size with safety constraints (e.g., min 6pt, max 72pt)
            new_size = max(6, min(72, current_size + step))

            # 5. Apply the new font size
            current_font.setPointSize(new_size)
            self.setFont(current_font)

            # 6. Crucial: Accept the event to prevent the View/Scene from zooming simultaneously
            event.accept()
            return

        # If conditions aren't met, pass the event to the default handler (e.g., scrolling text)
        super().wheelEvent(event)
