from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QPixmap, QCursor
from PyQt6.QtWidgets import QApplication


def get_screen_under_cursor():
    """
    Returns:
        QScreen in current cursor
    """
    screen = QApplication.screenAt(QCursor.pos())
    if screen is None:
        screen = QApplication.primaryScreen()
    return screen


def capture_fullscreen_under_cursor():
    """
    Capture the entire screen currently containing the mouse cursor
    and calculate the top-left position to center the pixmap on that screen.

    Returns:
        tuple: (QPixmap, QPoint) or (QPixmap(), None) if failed.
    """
    # ====================================================
    # 1. GET SCREEN UNDER CURSOR
    # ====================================================
    screen = get_screen_under_cursor()
    if screen is None:
        return QPixmap(), None

    # ====================================================
    # 2. CAPTURE SCREEN IMAGE
    # ====================================================
    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        return QPixmap(), None

    # ====================================================
    # 3. CALCULATE CENTER POSITION ON SAME SCREEN
    # ====================================================
    screen_rect = screen.availableGeometry()
    pixmap_size = pixmap.deviceIndependentSize().toSize()

    # Center the pixmap relative to the specific screen's bounds
    pos = QPoint(
        screen_rect.x() + (screen_rect.width() - pixmap_size.width()) // 2,
        screen_rect.y() + (screen_rect.height() - pixmap_size.height()) // 2,
    )

    return pixmap, pos
