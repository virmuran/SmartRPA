"""SmartRPA v3 主入口"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from smartrpa.ui.main_window import MainWindow
from smartrpa.ui.theme import build_base_qss


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SmartRPA")
    app.setFont(QFont("Microsoft YaHei", 10))
    app.setStyle("Fusion")
    app.setStyleSheet(build_base_qss())

    mw = MainWindow()
    mw.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()