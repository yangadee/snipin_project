import sys
import re
from PyQt6.QtCore import QRect, QSize, QUrl, Qt, QPoint
from PyQt6.QtGui import (
    QCursor,
    QDesktopServices,
    QKeySequence,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QListWidgetItem,
)

from resources import icon_provider


class PopupMenu(QWidget):
    def __init__(self, data_list=None, ref_pos=None, parent=None):
        super().__init__(parent)
        if data_list is None:
            data_list = []
        self.data_list = data_list
        self.init_ui()

        # Calculate position after init_ui()
        # Align top-top to point
        if ref_pos and isinstance(ref_pos, QPoint):
            self.popup_pos = ref_pos

        # Align to top-right of reference rect
        elif isinstance(ref_pos, QRect):
            # Align top-right to reference position
            ref_right_x = ref_pos.x() + ref_pos.width()
            ref_top_y = ref_pos.y()
            popup_x = ref_right_x - self.width()
            popup_y = ref_top_y
            self.popup_pos = QPoint(popup_x, popup_y)
        else:
            self.popup_pos = QCursor.pos()

    def init_ui(self):
        # 1. Window Flags: Remove window frame and auto-close when clicking outside (Popup)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(160)
        # QColor("#beeaff")
        self.setStyleSheet("""
            QWidget#Container {
                background-color: #ffffff;
                border-radius: 5px;         /* 圓角大小 */
                border: none;
            }
            QListWidget {
                border: 1px solid #cccccc;
                background: transparent; /*background-color: #ffffff;*/
                font-size: 15px; /* Items text size */
                font-family: "Consolas", monospace;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 1px 1px; /* Compact padding matching QMenu */
                color: #0066cc;    /* Blue link text color */
                font-family: "Consolas", monospace;
                border-bottom: 1px solid #fafafa;
                border-radius: 4px
            }
            QListWidget::item:hover {
                background-color: #e1f5fe ; /*#f0f0f0*/
            }
            QListWidget::item:selected {
                background-color: #0080ff; /* High-contrast selection background */
                color: #ffffff;            /* Selected text becomes white */
            }
            QListWidget::item:disabled {
                color: #aaaaaa;            /* Gray color for read-only texts */
                background-color: transparent;
            }
            QPushButton {
                padding: 2px 2px;
                border: 1px solid #cccccc;
                background-color: #f5f5f5;
                border-radius: 5px;
                font-size: 12px; /* button text size */
            }
            QPushButton:hover {
                background-color: #e1f5fe;
            }
            QPushButton:pressed  {
                background-color: #0080ff; /* High-contrast selection background */
                color: #ffffff;            /* Selected text becomes white */
            }
        """)

        # 2. 最外層佈局：不留邊距（因為我們不要陰影，只要純圓角邊框）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 3. 核心容器：用來承載背景色、圓角與外框線
        container = QWidget(self)
        container.setObjectName("Container")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(1)

        # 4. Top：QListWidget
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(0)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.populate_data_to_list(self.data_list)
        container_layout.addWidget(self.list_widget)

        # 5. Buttons（Open & Cancel）
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)
        self.btn_open = QPushButton("Open")
        self.btn_open_all = QPushButton("Open All")
        btn_layout.addWidget(self.btn_open)
        btn_layout.addWidget(self.btn_open_all)
        container_layout.addLayout(btn_layout)

        main_layout.addWidget(container)

        # 7. Connect
        self.btn_open_all.clicked.connect(self.process_open_all)
        self.btn_open.clicked.connect(self.process_open_selected)

        # ----------------------------------
        # HOTKEYS
        # ----------------------------------
        # Ctrl+C hotkey
        self.shortcut_copy = QShortcut(QKeySequence("Ctrl+C"), self.list_widget)
        self.shortcut_copy.activated.connect(self.copy_selected_text)

        # Bind Ctrl+A to select all function
        self.shortcut_select_all = QShortcut(QKeySequence("Ctrl+A"), self.list_widget)
        self.shortcut_select_all.activated.connect(self.list_widget.selectAll)

        # Dynamic Height Calculation (Formula synced with the compact padding settings)
        item_count = self.list_widget.count()
        # 20px per item, 45px for layout padding and horizontal buttons space
        calculated_height = (item_count * 20) + 30
        # Cap the maximum window height at 400px
        self.setFixedHeight(min(calculated_height, 400))

    def on_item_double_clicked(self, item: QListWidgetItem):
        """Double click -> Open immediately and disappear instantly like a QMenu"""
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            # print(f"[Instant Open] Opening: {url}")
            QDesktopServices.openUrl(QUrl(url))
            self.close()

    def populate_data_to_list(self, data_list: list):
        """
        # Populate compact items from datalist
        """
        # for item in data_list:
        #     display_text = item.get("text", "")
        #     target_url = item.get("url", "")
        #     tooltip = item.get("tooltip", "")
        #     type = item.get("type", "🔗")

        #     list_item = QListWidgetItem()
        #     list_item.setSizeHint(QSize(0, 20))

        #     if target_url == "":
        #         # Read-only plain text: Disable it so it cannot be selected or clicked
        #         list_item.setText(f"⚠️ {display_text}")
        #         list_item.setFlags(list_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

        #     else:
        #         # Active link item: Prepend icon and inject hidden URL data
        #         list_item.setText(f"{type} {display_text}")  #
        #         list_item.setData(Qt.ItemDataRole.UserRole, target_url)
        #         list_item.setToolTip(tooltip)

        #     self.list_widget.addItem(list_item)
        for result in data_list:
            item = QListWidgetItem(
                icon_provider.icon(result.kind), f"{result.title} \t{result.subtitle}"
            )
            item.setSizeHint(QSize(0, 20))
            item.setToolTip(result.subtitle)
            item.setData(Qt.ItemDataRole.UserRole, result.link)
            # item.setToolTip(result.link)
            self.list_widget.addItem(item)
        return

    def process_open_all(self):
        """Loops through all items and opens every single valid URL"""
        opened_count = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            url = item.data(Qt.ItemDataRole.UserRole)
            if url:  # Skip disabled/empty plain text rows
                # print(f"[Open All Batch] Opening: {url}")
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
                # print(f"[Open Selected Batch] Opening: {url}")
                QDesktopServices.openUrl(QUrl(url))
        if selected_items:
            self.close()

    def copy_selected_text(self):
        """
        Filters out leading ⚠️ and 🔗 icons from selected items
        and copies the pure text to the clipboard.
        """
        # Get all currently selected items from the list widget
        selected_items = self.list_widget.selectedItems()

        if not selected_items:
            return

        pure_text_list = []
        for item in selected_items:
            text = item.text()

            # Remove leading ⚠️ or 🔗 icons and any trailing spaces
            text_cleaned = re.sub(r"^[⚠️🔗]\s*", "", text)

            # Strip remaining leading and trailing whitespaces
            text_cleaned = text_cleaned.strip()

            # Only add to list if the line is not empty after filtering
            if text_cleaned:
                pure_text_list.append(text_cleaned)

        # Join items with newlines and copy to the system clipboard
        full_text = "\n".join(pure_text_list)
        QApplication.clipboard().setText(full_text)

    def show(self):
        """Spawns the frameless window precisely at the desired position"""
        if not self.data_list:
            return
        if self.popup_pos:
            self.move(self.popup_pos)

        super().show()

    # todo manual DPI


if __name__ == "__main__":

    class MainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Main Window")
            self.setGeometry(100, 100, 300, 300)

            layout = QVBoxLayout(self)
            self.btn_show = QPushButton("點擊彈出圓角小視窗", self)
            self.btn_show.clicked.connect(self.show_popup)
            layout.addWidget(self.btn_show)

        def show_popup(self):
            # Testing data
            data_list = [
                {"text": "cws131a.dia", "url": "https://example.com"},
                {"text": "cws222.abc", "url": "https://example.com"},
                {"text": "cil015c.adj", "url": "https://example.com"},
                {"text": "cil172a.per", "url": "https://example.com"},
                {"text": "cme238a.adj", "url": "https://example.com"},
                {"text": "cal199a.adj", "url": "https://example.com"},
                {"text": "cws087a.dia", "url": "https://example.com"},
            ]

            self.popup = PopupMenu(data_list)

            # 計算彈出位置
            btn_pos = self.btn_show.mapToGlobal(QPoint(0, 0))
            popup_x = btn_pos.x()
            popup_y = btn_pos.y() + self.btn_show.height() + 2

            self.popup.move(QCursor.pos())
            self.popup.show()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
