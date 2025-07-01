import sys
from PyQt5.QtWidgets import QApplication
from gui_app import VideoGeneratorApp


if __name__ == '__main__':
    # ensure_ffmpeg()
    app = QApplication(sys.argv)
    window = VideoGeneratorApp()
    window.show()
    sys.exit(app.exec())
