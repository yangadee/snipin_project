import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QMessageBox,
    QDialogButtonBox,
)


# =====================================================================
# Custom QMessageBox Class with Static Wrapper Method
# =====================================================================
class CustomMessageBox(QMessageBox):
    """Custom message box with no icon and centered action buttons."""

    def __init__(self, title, text, buttons, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(text)

        # Remove the default icon completely
        self.setIcon(QMessageBox.Icon.NoIcon)

        # Set standard buttons combined via bitwise OR (|)
        self.setStandardButtons(buttons)

        # Find the internal button box and force horizontal centering
        button_box = self.findChild(QDialogButtonBox)
        if button_box:
            button_box.setCenterButtons(True)

    @staticmethod
    def information(parent, title, text, buttons=QMessageBox.StandardButton.Ok):
        """
        Static wrapper method mimicking QMessageBox.information().
        Instantiates, centers buttons, executes the dialog, and returns the result.
        """
        # Create the custom message box instance
        dialog = CustomMessageBox(title, text, buttons, parent)
        return dialog.exec()


# =====================================================================
# Main Window Test Rig
# =====================================================================
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Static Wrapper Test")
        self.resize(300, 200)

        self.btn = QPushButton("Trigger Message Box", self)
        self.btn.setGeometry(80, 80, 140, 40)
        self.btn.clicked.connect(self.show_my_box)

    def show_my_box(self):
        # 🎯 One-line wrapper call just like QMessageBox.information()
        result = CustomMessageBox.information(
            self,
            "Save Changes",
            "Do you want to save current changes to your hotkeys?",
            QMessageBox.StandardButton.Ok
            | QMessageBox.StandardButton.Cancel
            | QMessageBox.StandardButton.Apply,
        )

        # Evaluate user choice directly from the return value
        if result == QMessageBox.StandardButton.Ok:
            print("User clicked: OK")
        elif result == QMessageBox.StandardButton.Cancel:
            print("User clicked: Cancel")
        elif result == QMessageBox.StandardButton.Apply:
            print("User clicked: Apply")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
