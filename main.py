import sys
from PyQt5.QtWidgets import QApplication
from gui_app import VideoGeneratorApp
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoGeneratorApp()
    window.show()
    sys.exit(app.exec())
