import sys
import data.keystore as keystore
from data.logger import setup_logger
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.theme import build_qss

if __name__ == "__main__":
    setup_logger()
    keystore.load_if_exists()
    from core.memory_loader import ensure_workspace_files
    ensure_workspace_files()
    app = QApplication(sys.argv)
    app.setStyleSheet(build_qss())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
