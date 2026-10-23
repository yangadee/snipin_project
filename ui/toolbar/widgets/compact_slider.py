from PyQt6.QtWidgets import QSlider
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor


class CompactSlider(QSlider):
    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)

        self.setFixedHeight(24)
        self.setStyleSheet("""
            QSlider {
                background: transparent;
                margin: 0px 5px;
                padding-top: 12px;  /* Reserve the upper half for the value */
            }
            QSlider::horizontal {
                min-width: 40px;
                max-width: 70px;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #E0E0E0;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #0078D4;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078D4;
                width: 12px;
                height: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #005A9E;
            }
        """)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # In paintEvent, keep your original font:
        font = self.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#0078D4"))

        label_rect = QRectF(0, 0, self.width(), 12)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, str(self.value()))
        painter.end()
