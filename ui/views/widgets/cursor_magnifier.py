from PyQt6.QtCore import Qt, QPoint, QRect, QSize
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget


class CursorMagnifier(QWidget):
    def __init__(self, parent=None, width=120, height=100):
        super().__init__(parent)

        # self.setWindowFlags(
        #     Qt.WindowType.SubWindow
        #     | Qt.WindowType.FramelessWindowHint
        #     | Qt.WindowType.NoDropShadowWindowHint
        #     | Qt.WindowType.WindowDoesNotAcceptFocus
        # )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(width, height)

        # Zoomer 75%，25% text
        self.img_h = int(self.height() * 0.7)
        self.img_w = self.width()

        self.target_pixel_size = 8
        self.grid_w = self.img_w // self.target_pixel_size
        self.grid_h = self.img_h // self.target_pixel_size

        if self.grid_w % 2 == 0:
            self.grid_w += 1
        if self.grid_h % 2 == 0:
            self.grid_h += 1

        self.bg_pixmap = QPixmap()
        self.current_mouse_pos = QPoint(0, 0)

    def update_data(self, mouse_pos, bg_pixmap):
        self.current_mouse_pos = mouse_pos
        self.bg_pixmap = bg_pixmap

        offset_x, offset_y = 20, 20
        margin = 5

        parent = self.parent()

        # mouse_pos: overlay local -> global
        global_mouse_pos = parent.mapToGlobal(mouse_pos)

        # Physical screen currently under cursor
        screen = QApplication.screenAt(global_mouse_pos)
        if screen is None:
            return

        # QScreen geometry is global
        screen_rect_global = screen.geometry()

        # Convert physical screen rect -> overlay local coordinates
        screen_top_left = parent.mapFromGlobal(screen_rect_global.topLeft())

        screen_rect = QRect(
            screen_top_left,
            screen_rect_global.size(),
        )

        # Default: right-bottom of cursor
        x = mouse_pos.x() + offset_x
        y = mouse_pos.y() + offset_y

        # ------------------------------------------------------
        # Horizontal boundary
        # ------------------------------------------------------
        if x + self.width() > screen_rect.right() + 1 - margin:
            x = mouse_pos.x() - self.width() - offset_x

        if x < screen_rect.left() + margin:
            x = screen_rect.left() + margin

        # ------------------------------------------------------
        # Vertical boundary
        # ------------------------------------------------------
        if y + self.height() > screen_rect.bottom() + 1 - margin:
            y = mouse_pos.y() - self.height() - offset_y

        if y < screen_rect.top() + margin:
            y = screen_rect.top() + margin

        self.move(x, y)
        self.update()

    def paintEvent(self, event):
        if self.bg_pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # [ 1 ~ 4 步驟與先前相同：擷取放大鏡、計算中心點、繪製十字線與藍色小鎖定框 ]
        half_grid_w = self.grid_w // 2
        half_grid_h = self.grid_h // 2
        capture_rect = QRect(
            self.current_mouse_pos.x() - half_grid_w,
            self.current_mouse_pos.y() - half_grid_h,
            self.grid_w,
            self.grid_h,
        )
        cropped = self.bg_pixmap.copy(capture_rect)
        img_rect = QRect(0, 0, self.img_w, self.img_h)
        painter.drawPixmap(
            img_rect,
            cropped.scaled(
                img_rect.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            ),
        )

        center_pixel_img = self.bg_pixmap.copy(
            QRect(self.current_mouse_pos, QSize(1, 1))
        ).toImage()
        pixel_color = (
            QColor(center_pixel_img.pixel(0, 0))
            if not center_pixel_img.isNull()
            else QColor(0, 0, 0)
        )

        real_pixel_w = self.img_w / self.grid_w
        real_pixel_h = self.img_h / self.grid_h
        center_x = int(0 + (half_grid_w * real_pixel_w) + (real_pixel_w / 2))
        center_y = int(0 + (half_grid_h * real_pixel_h) + (real_pixel_h / 2))

        shadow_pen = QPen(QColor(0, 0, 0, 180), 3)
        painter.setPen(shadow_pen)
        painter.drawLine(0, center_y, self.img_w, center_y)
        painter.drawLine(center_x, 0, center_x, self.img_h)

        core_pen = QPen(QColor(255, 255, 255, 245), 1)
        painter.setPen(core_pen)
        painter.drawLine(0, center_y, self.img_w, center_y)
        painter.drawLine(center_x, 0, center_x, self.img_h)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 170, 255), 1.5))
        painter.drawRect(
            QRect(
                int(center_x - real_pixel_w / 2),
                int(center_y - real_pixel_h / 2),
                int(real_pixel_w),
                int(real_pixel_h),
            )
        )

        # ========================================================
        # 5. Info area background
        # ========================================================
        info_rect = QRect(0, self.img_h, self.width(), self.height() - self.img_h)

        # Semi-transparent dark background
        painter.fillRect(info_rect, QColor(20, 20, 20, 210))

        # ========================================================
        # 6. Position + Color Swatch + RGB
        # ========================================================
        base_font_size = 9.0
        min_font_size = 6.0

        font = QFont("Consolas", int(base_font_size), QFont.Weight.Bold)
        font.setPointSizeF(base_font_size)
        painter.setFont(font)

        rgb_text = (
            f"({pixel_color.red()}," f"{pixel_color.green()}," f"{pixel_color.blue()})"
        )
        pos_text = f"{self.current_mouse_pos.x()}," f"{self.current_mouse_pos.y()}"

        # --------------------------------------------------------
        # Layout
        # --------------------------------------------------------
        margin_x = 6
        margin_y = 2
        swatch_size = 12
        swatch_gap = 5
        max_width = self.width() - margin_x * 2
        max_height = info_rect.height() - margin_y * 2

        # ========================================================
        # Auto-fit font
        # ========================================================
        while True:
            painter.setFont(font)

            # Important: get metrics from the painter AFTER setting the font
            fm = painter.fontMetrics()
            pos_width = fm.horizontalAdvance(pos_text)
            rgb_width = swatch_size + swatch_gap + fm.horizontalAdvance(rgb_text)
            required_height = fm.lineSpacing() * 2
            fits_width = pos_width <= max_width and rgb_width <= max_width
            fits_height = required_height <= max_height
            if fits_width and fits_height:
                break
            base_font_size -= 0.5
            if base_font_size <= min_font_size:
                base_font_size = min_font_size
                font.setPointSizeF(base_font_size)
                painter.setFont(font)
                fm = painter.fontMetrics()
                break
            font.setPointSizeF(base_font_size)

        # ========================================================
        # Helper: text with shadow
        # ========================================================
        def draw_text_with_shadow(p, x, y, text):
            p.setPen(QColor(0, 0, 0, 220))
            p.drawText(x + 1, y + 1, text)
            p.setPen(QColor(255, 255, 255))
            p.drawText(x, y, text)

        # ========================================================
        # Vertically center BOTH rows inside info_rect
        # ========================================================
        total_text_height = fm.lineSpacing() * 2
        content_top = info_rect.top() + (info_rect.height() - total_text_height) // 2
        first_y = content_top + fm.ascent()
        second_y = first_y + fm.lineSpacing()

        # ========================================================
        # First row: Position
        # ========================================================
        pos_width = fm.horizontalAdvance(pos_text)
        pos_x = (self.width() - pos_width) // 2
        draw_text_with_shadow(painter, pos_x, first_y, pos_text)

        # ========================================================
        # Second row: Swatch + RGB
        # ========================================================
        rgb_text_width = fm.horizontalAdvance(rgb_text)
        second_total_width = swatch_size + swatch_gap + rgb_text_width
        second_start_x = (self.width() - second_total_width) // 2

        # --------------------------------------------------------
        # Swatch
        # --------------------------------------------------------
        swatch_y = second_y - fm.ascent() + (fm.height() - swatch_size) // 2
        swatch_rect = QRect(
            second_start_x,
            swatch_y,
            swatch_size,
            swatch_size,
        )
        painter.setBrush(pixel_color)
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
        painter.drawRect(swatch_rect)

        # --------------------------------------------------------
        # RGB text
        # --------------------------------------------------------
        second_text_x = second_start_x + swatch_size + swatch_gap
        draw_text_with_shadow(painter, second_text_x, second_y, rgb_text)

        # ========================================================
        # Outer bounding border
        # ========================================================
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Dark outer border
        painter.setPen(QPen(QColor(0, 0, 0, 200), 3))
        painter.drawRoundedRect(self.rect(), 1, 1)
        # White inner border
        painter.setPen(QPen(QColor(255, 255, 255, 230), 1))
        painter.drawRoundedRect(self.rect(), 1, 1)
