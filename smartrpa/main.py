"""SmartRPA v3 启动入口

New architecture entry point — uses the modular MainWindow
with sidebar + 4 tabs instead of the monolithic gui.py.
"""
import sys
import os

# Ensure the project root is on sys.path so that smartrpa can be imported
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from smartrpa.ui.main_window import MainWindow
from smartrpa.ui.theme import build_base_qss


def main():
    """Launch SmartRPA v3 with the new modular UI."""
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
