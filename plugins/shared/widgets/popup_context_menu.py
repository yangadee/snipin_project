from PyQt6.QtGui import (
    QCursor,
    QPainter,
    QColor,
    QPen,
    QDesktopServices,
)
from PyQt6.QtCore import Qt, QSize, QRectF, QUrl, QPoint
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QApplication,
)


class PopupContextMenu2(QWidget):
    def __init__(self, data_list=None, popup_pos=None, parent=None):
        super().__init__(parent)
        if data_list is None:
            data_list = []

        self.popup_pos = popup_pos
        self.data_list = data_list
        self.init_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        # Enable high-quality anti-aliasing for smooth rounded edges
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Define background color and thin border line color
        painter.setBrush(QColor("#ffffff"))  # White filling
        painter.setPen(QPen(QColor("#cccccc"), 1))  # 1px gray border

        # Get the actual rectangle bounding box (adjusted inside by 0.5px for crisp 1px border lines)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        # Draw a perfect rounded rectangle: 6.0 is the horizontal/vertical corner radius
        painter.drawRoundedRect(rect, 6.0, 6.0)

    def init_ui(self):
        # 1. Window Flags: Remove window frame and auto-close when clicking outside (Popup)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
            | Qt.WindowType.NoDropShadowWindowHint  # 強制關閉作業系統的視窗陰影
        )
        self.setFixedWidth(150)  # Fixed standard width similar to QMenu

        # 2. Premium QMenu-like style sheet (Optimized compact spacing and button sizes)
        self.setStyleSheet("""
            QWidget { 
                background-color: #ffffff; 
                border: 1px solid #cccccc; 
                border-radius: 4px; 
            }
            QListWidget { 
                border: none; 
                background: transparent; 
            }
            QListWidget::item { 
                padding: 2px 5px; /* Compact padding matching QMenu */
                color: #0066cc;    /* Blue link text color */
                font-family: sans-serif;
                font-size: 13px;
                border-bottom: 1px solid #fafafa;
                border-radius: 2px;
            }
            QListWidget::item:hover { 
                background-color: #f0f0f0; 
            }
            QListWidget::item:selected { 
                background-color: #0066cc; /* High-contrast selection background */
                color: #ffffff;            /* Selected text becomes white */
            }
            QListWidget::item:disabled {
                color: #aaaaaa;            /* Gray color for read-only texts */
                background-color: transparent;
            }
            QPushButton { 
                background-color: #f8f9fa; 
                color: #333333; 
                border: 1px solid #dddddd; 
                padding: 4px 5px;          /* Ultra tight button padding */
                border-radius: 4px; 
                font-size: 11px;           /* Small text for mini buttons */
                font-family: sans-serif;
            }
            QPushButton:hover { 
                background-color: #e9ecef; 
            }
        """)

        # Main Vertical Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            2, 2, 2, 2
        )  # Tightest margin for maximum compactness
        main_layout.setSpacing(4)

        # 3. Core Component: QListWidget with Extended Selection Mode
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Connect click signal for instant single-click opening action
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.setSpacing(0)  # Force layout spacing between items to 0px

        # Populate compact items from data list
        for item in self.data_list:
            display_text = item.get("text", "")
            target_url = item.get("url", "")

            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 20))

            if target_url == "":
                # Read-only plain text: Disable it so it cannot be selected or clicked
                list_item.setText(display_text)
                list_item.setFlags(list_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                # Active link item: Prepend icon and inject hidden URL data
                list_item.setText(f"🔗 {display_text}")
                list_item.setData(Qt.ItemDataRole.UserRole, target_url)

            self.list_widget.addItem(list_item)

        main_layout.addWidget(self.list_widget)

        # 4. Dual Small Buttons Layout (Horizontal Side-by-Side)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(2, 0, 2, 2)
        btn_layout.setSpacing(4)  # Tight spacing between two buttons

        # Button B: Open Selected (Triggers batch open for items highlighted via Ctrl+Click)
        self.btn_open_selected = QPushButton("Open", self)
        self.btn_open_selected.clicked.connect(self.process_open_selected)
        btn_layout.addWidget(self.btn_open_selected)

        # Button A: Open All (Triggers batch open for all non-empty URLs)
        self.btn_open_all = QPushButton("Open All", self)
        self.btn_open_all.clicked.connect(self.process_open_all)
        btn_layout.addWidget(self.btn_open_all)

        main_layout.addLayout(btn_layout)

        # 5. Dynamic Height Calculation (Formula synced with the compact padding settings)
        item_count = self.list_widget.count()
        # 28px per item, 45px for layout padding and horizontal buttons space
        calculated_height = (item_count * 20) + 38
        self.setFixedHeight(
            min(calculated_height, 400)
        )  # Cap the maximum window height at 350px

    def on_item_clicked(self, item: QListWidgetItem):
        """Handles immediate single click vs multi-selection check"""
        # Query the hardware keyboard state from OS
        modifiers = QApplication.queryKeyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # Case A: Ctrl is being held down -> Enter multi-select mode, do nothing here
            return
        # Case B: Standard click -> Open immediately and disappear instantly like a QMenu
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            print(f"[Instant Open] Opening: {url}")
            QDesktopServices.openUrl(QUrl(url))
            self.close()

    def process_open_all(self):
        """Loops through all items and opens every single valid URL"""
        opened_count = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            url = item.data(Qt.ItemDataRole.UserRole)
            if url:  # Skip disabled/empty plain text rows
                print(f"[Open All Batch] Opening: {url}")
                QDesktopServices.openUrl(QUrl(url))
                opened_count += 1
        if opened_count > 0:
            self.close()

    def process_open_selected(self):
        """Loops through and opens only the rows highlighted by the user (Ctrl+Click)"""
        selected_items = self.list_widget.selectedItems()
        for item in selected_items:
            url = item.data(Qt.ItemDataRole.UserRole)
            if url:
                print(f"[Open Selected Batch] Opening: {url}")
                QDesktopServices.openUrl(QUrl(url))
        if selected_items:
            self.close()

    def show(self):
        """Spawns the frameless window precisely at the mouse cursor position"""
        if not self.data_list:
            return
        if self.popup_pos:
            self.move(self.popup_pos)
        else:
            self.move(QCursor.pos())
        super.show()
