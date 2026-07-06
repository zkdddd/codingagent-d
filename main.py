import sys

from PyQt6.QtWidgets import QApplication

from kagent import db
from kagent.ui.main_window import ChatWindow


def main():
    db.init_db()
    app = QApplication(sys.argv)
    app.setApplicationName("kagent")
    win = ChatWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
