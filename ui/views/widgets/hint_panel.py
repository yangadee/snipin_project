from enum import Enum, auto
from PyQt6.QtCore import QRectF, Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
from PyQt6.QtWidgets import QWidget

# ===================================================
# SET WS_EX_TRANSPARENT
# ===================================================
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
LONG_PTR = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = LONG_PTR
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
user32.SetWindowLongPtrW.restype = LONG_PTR
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020


class HintMode(Enum):
    SNIP = auto()
    EDIT = auto()
    DRAW = auto()


class ShortcutHintPanel(QWidget):
    """
    A multi-line shortcut hint panel inspired by Snipaste.
    Independently responsible for calculating its own size, as well as
    aligning and rendering key caps.
    """

    def __init__(self, parent=None, shortcuts=None):
        super().__init__(parent)

        # Configure window flags: frameless, stays on top, and treated as a tool window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # Enable translucent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # ------------------------------------------
        # set Win32 WS_EX_TRANSPARENT
        # ------------------------------------------
        hwnd = int(self.winId())
        ex_style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_TRANSPARENT)
        # ------------------------------------------

        self.shortcuts = list(shortcuts or [])
        self.init_layout_size()

    def set_shortcuts(self, shortcuts):
        shortcuts = list(shortcuts)
        if shortcuts == self.shortcuts:
            return
        self.shortcuts = shortcuts

        # Recalculate width/height because the new mode can
        # contain different key combinations / descriptions.
        self.init_layout_size()

        # Repaint using the new shortcut list.
        self.update()

    # def _init_layout_size(self):
    #     # 設置現代科技感的字體
    #     self.panel_font = QFont("Segoe UI", 10, QFont.Weight.Medium)
    #     fm = QFontMetrics(self.panel_font)

    #     # 定義內邊距與行高
    #     self.padding_x, self.padding_y = 10, 15
    #     self.line_height = fm.lineSpacing() + 10  # 每行高度加上上下留白
    #     self.gap_between = 20  # 按鍵區與文字說明之間的間隙

    #     # 1. 計算左側「所有按鍵群組」的最大寬度，用來做右側文字的對齊線
    #     self.max_keys_zone_width = 0
    #     for keys, connector, _ in self.shortcuts:
    #         zone_w = 0
    #         for i, key in enumerate(keys):
    #             key_w = fm.boundingRect(key).width() + 12
    #             zone_w += max(key_w, 24)  # 限制單個按鍵最小寬度為 24px
    #             if i < len(keys) - 1 and connector:
    #                 zone_w += fm.boundingRect(connector).width() + 10
    #         if zone_w > self.max_keys_zone_width:
    #             self.max_keys_zone_width = zone_w

    #     # 2. 計算右側說明文字的最大寬度
    #     self.max_text_width = max(
    #         (fm.boundingRect(text).width() for _, _, text in self.shortcuts),
    #         default=0,
    #     )
    #     # 3. 組合出面板總尺寸，並套用到 Widget
    #     self.box_width = (
    #         self.padding_x * 2
    #         + self.max_keys_zone_width
    #         + self.gap_between
    #         + self.max_text_width
    #     )
    #     self.box_height = self.padding_y * 2 + len(self.shortcuts) * self.line_height
    #     self.setFixedSize(self.box_width, self.box_height)

    def init_layout_size(self):
        # Font
        self.panel_font = QFont("Segoe UI", 11, QFont.Weight.Medium)
        fm = QFontMetrics(self.panel_font)

        # --------------------------------------------------------
        # Spacing
        # --------------------------------------------------------
        # Outer panel padding
        self.padding_x = 14
        self.padding_y = 8

        # Key size
        self.key_padding_x = 8
        self.key_min_width = 26
        self.key_height_margin = 4

        self.connector_margin = 4  # Space around "+" or "/"
        self.gap_between = 24  # Space between key column and description

        self.line_height = max(fm.lineSpacing() + self.key_height_margin, 27)

        # --------------------------------------------------------
        # Left side: shortcut keys
        # --------------------------------------------------------
        # self.max_keys_zone_width = 0
        # for keys, connector, _ in self.shortcuts:
        #     zone_w = 0

        #     for i, key in enumerate(keys):
        #         key_w = fm.horizontalAdvance(key) + self.key_padding_x * 2
        #         zone_w += max(key_w, self.key_min_width)

        #         if i < len(keys) - 1 and connector:
        #             connector_w = fm.horizontalAdvance(connector)
        #             zone_w += connector_w + self.connector_margin * 2

        #     self.max_keys_zone_width = max(
        #         self.max_keys_zone_width,
        #         zone_w,
        #     )

        self.max_keys_zone_width = 0
        for keys, connector, _ in self.shortcuts:
            groups = self._normalize_key_groups(keys)
            zone_w = 0.0
            for group_index, group in enumerate(groups):
                zone_w += self._key_group_width(fm, group, connector)
                if group_index < len(groups) - 1:
                    zone_w += fm.horizontalAdvance("/") + self.connector_margin * 2
            self.max_keys_zone_width = max(self.max_keys_zone_width, zone_w)
        # --------------------------------------------------------
        # Right side: description
        # --------------------------------------------------------
        self.max_text_width = max(
            (fm.horizontalAdvance(text) for _, _, text in self.shortcuts), default=0
        )

        # --------------------------------------------------------
        # Final panel size
        # --------------------------------------------------------
        self.box_width = (
            self.padding_x * 2
            + self.max_keys_zone_width
            + self.gap_between
            + self.max_text_width
        )

        self.box_height = self.padding_y * 2 + len(self.shortcuts) * self.line_height
        self.setFixedSize(int(self.box_width), int(self.box_height))

    def _normalize_key_groups(self, keys):
        """
        Convert:
            ["Ctrl", "C"]
        into:
            [["Ctrl", "C"]]
        while preserving:
            [["Ctrl", "C"], ["S"]]
        """
        if not keys:
            return []
        if isinstance(keys[0], str):
            return [keys]
        return keys

    def _key_group_width(
        self,
        fm: QFontMetrics,
        keys: list[str],
        connector: str,
    ) -> float:
        width = 0.0
        for i, key in enumerate(keys):
            key_w = max(
                fm.horizontalAdvance(key) + self.key_padding_x * 2, self.key_min_width
            )
            width += key_w
            if i < len(keys) - 1 and connector:
                width += fm.horizontalAdvance(connector) + self.connector_margin * 2
        return width

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.panel_font)
        fm = QFontMetrics(self.panel_font)

        # ========================================================
        # Panel background
        # ========================================================
        border_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
        painter.setBrush(QColor(35, 35, 35, 190))
        painter.drawRoundedRect(border_rect, 8, 8)
        # ========================================================
        # Rows
        # ========================================================
        current_y = self.padding_y
        for keys, connector, text in self.shortcuts:
            center_y = current_y + self.line_height / 2
            # ----------------------------------------------------
            # Normalize:
            # ["Ctrl", "C"]
            # ->
            # [["Ctrl", "C"]]
            # while also supporting:
            # [["Ctrl", "C"], ["S"]]
            # ----------------------------------------------------
            groups = self._normalize_key_groups(keys)

            # ----------------------------------------------------
            # Calculate total shortcut width
            # ----------------------------------------------------
            current_zone_w = 0.0
            for group_index, group in enumerate(groups):
                current_zone_w += self._key_group_width(fm, group, connector)

                # Separator between alternatives:
                # [Ctrl]+[C] / [S]
                if group_index < len(groups) - 1:
                    current_zone_w += (
                        fm.horizontalAdvance("/") + self.connector_margin * 2
                    )
            # Right align shortcut area
            x = self.padding_x + self.max_keys_zone_width - current_zone_w
            # ====================================================
            # Draw shortcut groups
            # ====================================================
            for group_index, group in enumerate(groups):
                # ------------------------------------------------
                # Draw keys inside this group
                # ------------------------------------------------
                for i, key in enumerate(group):
                    key_w = max(
                        fm.horizontalAdvance(key) + self.key_padding_x * 2,
                        self.key_min_width,
                    )
                    key_h = fm.height() + self.key_height_margin
                    key_rect = QRectF(x, center_y - key_h / 2, key_w, key_h)
                    # Key background/border
                    painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
                    painter.setBrush(QColor(255, 255, 255, 18))
                    painter.drawRoundedRect(key_rect, 4, 4)
                    # Key text
                    painter.setPen(QColor(245, 245, 245))
                    painter.drawText(key_rect, Qt.AlignmentFlag.AlignCenter, key)
                    x += key_w
                    # --------------------------------------------
                    # Connector inside group:
                    # [Ctrl] + [C]
                    # --------------------------------------------
                    if i < len(group) - 1 and connector:
                        conn_w = (
                            fm.horizontalAdvance(connector) + self.connector_margin * 2
                        )
                        conn_rect = QRectF(
                            x, center_y - fm.height() / 2, conn_w, fm.height()
                        )
                        painter.setPen(QColor(150, 150, 150))
                        painter.drawText(
                            conn_rect, Qt.AlignmentFlag.AlignCenter, connector
                        )
                        x += conn_w
                # ------------------------------------------------
                # Alternative separator:
                #
                # [Ctrl]+[C] / [S]
                # ------------------------------------------------
                if group_index < len(groups) - 1:
                    separator = "/"
                    sep_w = fm.horizontalAdvance(separator) + self.connector_margin * 2
                    sep_rect = QRectF(x, center_y - fm.height() / 2, sep_w, fm.height())
                    painter.setPen(QColor(125, 125, 125))
                    painter.drawText(sep_rect, Qt.AlignmentFlag.AlignCenter, separator)
                    x += sep_w
            # ====================================================
            # Description
            # ====================================================
            text_x = self.padding_x + self.max_keys_zone_width + self.gap_between
            text_rect = QRectF(text_x, current_y, self.max_text_width, self.line_height)
            painter.setPen(QColor(220, 220, 220))
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )
            current_y += self.line_height

    # def paintEvent(self, event):
    #     painter = QPainter(self)
    #     painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    #     painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    #     painter.setFont(self.panel_font)
    #     fm = QFontMetrics(self.panel_font)

    #     # ========================================================
    #     # Panel background
    #     # ========================================================
    #     border_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

    #     painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
    #     painter.setBrush(QColor(35, 35, 35, 190))
    #     painter.drawRoundedRect(border_rect, 8, 8)

    #     # ========================================================
    #     # Rows
    #     # ========================================================
    #     current_y = self.padding_y

    #     for keys, connector, text in self.shortcuts:
    #         center_y = current_y + self.line_height / 2

    #         # ----------------------------------------------------
    #         # Calculate current shortcut width
    #         # ----------------------------------------------------
    #         current_zone_w = 0

    #         for i, key in enumerate(keys):
    #             key_w = max(
    #                 fm.horizontalAdvance(key) + self.key_padding_x * 2,
    #                 self.key_min_width,
    #             )
    #             current_zone_w += key_w

    #             if i < len(keys) - 1 and connector:
    #                 current_zone_w += (
    #                     fm.horizontalAdvance(connector) + self.connector_margin * 2
    #                 )

    #         # Right-align shortcut group inside left column
    #         x = self.padding_x + self.max_keys_zone_width - current_zone_w

    #         # ----------------------------------------------------
    #         # Draw keys
    #         # ----------------------------------------------------
    #         for i, key in enumerate(keys):
    #             key_w = max(
    #                 fm.horizontalAdvance(key) + self.key_padding_x * 2,
    #                 self.key_min_width,
    #             )
    #             key_h = fm.height() + self.key_height_margin
    #             key_rect = QRectF(x, center_y - key_h / 2, key_w, key_h)

    #             # Key background + subtle border
    #             painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
    #             painter.setBrush(QColor(255, 255, 255, 18))
    #             painter.drawRoundedRect(key_rect, 4, 4)

    #             # Key text
    #             painter.setPen(QColor(245, 245, 245))
    #             painter.drawText(key_rect, Qt.AlignmentFlag.AlignCenter, key)

    #             x += key_w

    #             # ------------------------------------------------
    #             # Connector: + / etc.
    #             # ------------------------------------------------
    #             if i < len(keys) - 1 and connector:
    #                 conn_w = fm.horizontalAdvance(connector) + self.connector_margin * 2
    #                 conn_rect = QRectF(
    #                     x, center_y - fm.height() / 2, conn_w, fm.height()
    #                 )
    #                 painter.setPen(QColor(150, 150, 150))
    #                 painter.drawText(conn_rect, Qt.AlignmentFlag.AlignCenter, connector)
    #                 x += conn_w

    #         # ----------------------------------------------------
    #         # Description
    #         # ----------------------------------------------------
    #         text_x = self.padding_x + self.max_keys_zone_width + self.gap_between
    #         text_rect = QRectF(text_x, current_y, self.max_text_width, self.line_height)
    #         painter.setPen(QColor(220, 220, 220))
    #         painter.drawText(
    #             text_rect,
    #             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    #             text,
    #         )
    #         current_y += self.line_height

    # def _paintEvent(self, event):
    #     painter = QPainter(self)
    #     painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    #     fm = QFontMetrics(self.panel_font)
    #     painter.setFont(self.panel_font)

    #     # 1. 繪製面板圓角背景（深灰色、高透明毛玻璃感）
    #     rect = self.rect()
    #     painter.setPen(Qt.PenStyle.NoPen)
    #     painter.setBrush(QColor(45, 45, 45, 150))
    #     painter.drawRoundedRect(rect, 4, 4)

    #     # 面板外圍微白裝飾邊框
    #     painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
    #     painter.drawRoundedRect(rect, 4, 4)

    #     # 2. 逐行繪製按鍵與說明文字
    #     current_y = self.padding_y

    #     for keys, connector, text in self.shortcuts:
    #         center_y = current_y + self.line_height // 2

    #         # --- 【左側：按鍵區繪製（右對齊）】 ---
    #         current_zone_w = 0
    #         for i, key in enumerate(keys):
    #             current_zone_w += max(fm.boundingRect(key).width() + 12, 24)
    #             if i < len(keys) - 1 and connector:
    #                 current_zone_w += fm.boundingRect(connector).width() + 10

    #         # 計算這組按鍵的 X 軸起始點
    #         start_key_x = self.padding_x + (self.max_keys_zone_width - current_zone_w)

    #         for i, key in enumerate(keys):
    #             key_rect_w = max(fm.boundingRect(key).width() + 12, 24)
    #             key_rect_h = fm.height() + 6
    #             key_rect = QRect(
    #                 start_key_x, center_y - key_rect_h // 2, key_rect_w, key_rect_h
    #             )

    #             # 繪製鍵盤實體外觀（高亮白邊、極淡白底）
    #             painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
    #             painter.setBrush(QColor(255, 255, 255, 12))
    #             painter.drawRoundedRect(key_rect, 3, 3)

    #             # 繪製按鍵內的字母
    #             painter.setPen(QColor(255, 255, 255))
    #             painter.drawText(key_rect, Qt.AlignmentFlag.AlignCenter, key)

    #             start_key_x += key_rect_w

    #             # 繪製按鍵之間的連接符（如 + 或 /）
    #             if i < len(keys) - 1 and connector:
    #                 conn_w = fm.boundingRect(connector).width() + 10
    #                 conn_rect = QRect(
    #                     start_key_x, center_y - fm.height() // 2, conn_w, fm.height()
    #                 )
    #                 painter.setPen(QColor(170, 170, 170))
    #                 painter.drawText(conn_rect, Qt.AlignmentFlag.AlignCenter, connector)
    #                 start_key_x += conn_w

    #         # --- 【右側：說明文字繪製（左對齊）】 ---
    #         text_x = self.padding_x + self.max_keys_zone_width + self.gap_between
    #         text_rect = QRect(
    #             text_x, center_y - fm.height() // 2, self.max_text_width, fm.height()
    #         )
    #         painter.setPen(QColor(225, 225, 225))
    #         painter.drawText(
    #             text_rect,
    #             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    #             text,
    #         )

    #         current_y += self.line_height
