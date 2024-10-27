# main.py

import sys
import logging
from PySide6.QtWidgets import QApplication

from gui import AppGUI

def setup_logging():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s',
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler("app.log", mode='a')])

def main():
    setup_logging()
    app = QApplication(sys.argv)
    gui = AppGUI()
    gui.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
