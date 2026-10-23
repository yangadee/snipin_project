from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget,
    QGridLayout,
    QPushButton,
    QFrame,
    QLabel,
    QColorDialog,
)


class ColorPalette(QWidget):
    """Refactored micro color palette: layout/size set ONCE, style updates COLOR only."""

    color_selected = pyqtSignal(QColor)
    colorChanged = pyqtSignal(QColor)

    def __init__(self):
        super().__init__(None)
        self.color_buttons = []
        self.current_color = QColor("#FF0000")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # self.setStyleSheet("""
        # QWidget {
        # background-color: transparent;
        # border: none;
        # padding: 0px; margin: 0px;
        # }
        # QPushButton {
        # border: 0.5px solid rgba(255, 255, 255, 60);
        # border-radius: 0px;
        # padding: 0px; margin: 0px;
        # min-width: 0px; min-height: 0px;
        # }
        # QPushButton:hover { border: 1px solid white; }
        # """)
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
                border-radius: 3px;
                padding: 0px;
                margin: 0px;
                min-height: 24px;
            }
            QPushButton {
                border: .5px solid rgba(255, 255, 255, 60);
                border-radius: 0px;
                padding: 0px;
                margin: 0px;
                min-width: 0px; min-height: 0px;
            }
            QPushButton:hover {
                border: 1px solid #222222;
            }
        """)

        self.init_ui()

    def init_ui(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        # layout.setHorizontalSpacing(1)
        # layout.setVerticalSpacing(0)
        self.setLayout(layout)
        self.setFixedHeight(24)
        # 尺寸在這裡一輩子只設定一次
        button_size = 12
        big_height = (button_size * 2) + 1
        big_width = big_height

        # Big Current Color Button
        self.current_color_btn = QPushButton()
        self.current_color_btn.setMinimumSize(0, 0)
        self.current_color_btn.setFixedSize(big_width, big_height)  # 固定尺寸，永不改變
        self.current_color_btn.setToolTip(self.current_color.name().upper())
        self.current_color_btn.clicked.connect(self.pick_current_color)
        layout.addWidget(self.current_color_btn, 0, 0, 2, 1)

        # Color Grid Buttons
        colors = [
            "#FF0000",
            "#FF8000",
            "#FFFF00",
            "#00FF00",
            "#00FFFF",
            "#0080FF",
            "#8000FF",
            "#FF00FF",
            "#000000",
            "#444444",
            "#888888",
            "#CCCCCC",
            "#FFFFFF",
            "#880000",
            "#008800",
            "#000088",
        ]
        columns = 8

        for i, hex_color in enumerate(colors):
            btn = QPushButton()
            btn.setMinimumSize(0, 0)
            btn.setFixedSize(button_size, button_size)  # 固定尺寸，永不改變
            btn.setToolTip(hex_color)
            btn.clicked.connect(lambda checked=False, c=hex_color: self.pick_color(c))

            # 初始化按鈕外觀
            self.update_color_button_style(btn, hex_color, selected=False)

            row = i // columns
            col = (i % columns) + 1
            layout.addWidget(btn, row, col)
            self.color_buttons.append((btn, hex_color))

        # 初始化大按鈕顏色
        self.update_current_color_button()
        self.adjustSize()

    # def sizeHint(self):
    # return QSize(150, 24)

    def update_color_button_style(self, btn, hex_color, selected=False):
        border = "1px solid #FFFFFF" if selected else ".5px solid rgba(90,90,90,120)"
        btn.setStyleSheet(f"background-color: {hex_color}; border: {border};")

    def update_current_color_button(self):
        current_hex = self.current_color.name().upper()
        self.current_color_btn.setStyleSheet(
            f"background-color: {current_hex}; border: 1px solid #FFFFFF; border-radius: 1px;"
        )
        for btn, hex_color in self.color_buttons:
            self.update_color_button_style(
                btn, hex_color, selected=(hex_color.upper() == current_hex)
            )

    def pick_color(self, hex_color: str):
        color = QColor(hex_color)
        self.current_color = color
        self.update_current_color_button()
        self.color_selected.emit(color)
        self.colorChanged.emit(color)

    def pick_current_color(self):
        # color = QColorDialog.getColor(self.current_color, self, "Select Color")
        dialog = QColorDialog(self)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.setStyleSheet("""
            QColorDialog { background: #F3F3F3; }
            QLabel, QPushButton, QLineEdit, QSpinBox { color: black; }
            QLineEdit, QSpinBox, QPushButton { background: white; border: 1px solid #CCC; border-radius: 3px; padding: 2px; }
        """)

        if dialog.exec() == QColorDialog.DialogCode.Accepted:
            color = dialog.selectedColor()
            if color.isValid():
                self.current_color = color
                self.color_selected.emit(color)
                self.colorChanged.emit(color)
                self.update_current_color_button()

        return

    def set_current_color(self, color):  # call by external.
        qcolor = QColor(color)
        if qcolor.isValid():
            self.current_color = qcolor
            self.update_current_color_button()

    def setColor(self, color):
        return self.set_current_color(color)

    def color(self):
        return self.current_color


# Optional: Add custom color button at bottom later
# colors = [
# "#FF0000", "#FF8000", "#FFFF00", "#00FF00", "#00FFFF", "#0080FF", "#8000FF", "#FF00FF",
# "#FF4444", "#FFBB33", "#FFFF44", "#44FF44", "#44FFFF", "#4488FF", "#BB44FF", "#FF44BB",
# "#000000", "#444444", "#888888", "#CCCCCC", "#FFFFFF", "#880000", "#008800", "#000088"
# ]
