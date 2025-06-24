import os
import random
import subprocess
import requests
import concurrent.futures
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel,
    QTextEdit, QProgressBar, QMessageBox, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QComboBox, QHeaderView
)
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QIcon
from pydub import AudioSegment
from voice_generator import create_voice_with_elevenlabs
from subtitle_generator import create_srt_word_by_word
from video_creator import create_video_randomized_media, burn_sub_and_audio

MAX_THREADS = 2
OUTPUT_FOLDER = "outputs"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

class VideoGeneratorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 AI Video Generator - @huyit32")
        self.setGeometry(200, 200, 800, 600)

        self.folder_path = ""
        self.text_list = []
        self.fonts = [
            "Arial", "Tahoma", "Times New Roman", "Verdana", "Helvetica",
            "Georgia", "Courier New", "Comic Sans MS", "Impact", "Trebuchet MS",
            "Lucida Console", "Palatino Linotype", "Garamond", "Segoe UI",
            "Candara", "Playbill", "Consolas", "Century Gothic", "Calibri"
        ]

        self.layout = QVBoxLayout()

        self.select_folder_btn = QPushButton("📁 Chọn thư mục chứa ảnh/video nền")
        self.select_folder_btn.clicked.connect(self.select_folder)
        self.layout.addWidget(self.select_folder_btn)

        ratio_layout = QHBoxLayout()
        ratio_layout.addWidget(QLabel("Tỉ lệ video:"))
        self.ratio_selector = QComboBox()
        self.ratio_selector.addItems(["Dọc (9:16)", "Ngang (16:9)"])
        ratio_layout.addWidget(self.ratio_selector)
        self.layout.addLayout(ratio_layout)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("==|==\nVideo 1\n==|==\nVideo 2")
        self.layout.addWidget(self.text_input)

        self.api_key_input = QTextEdit()
        self.api_key_input.setPlaceholderText("🔐 Nhập API Key ElevenLabs")
        self.api_key_input.setMaximumHeight(50)
        self.layout.addWidget(self.api_key_input)

        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font chữ phụ đề:"))
        self.font_selector = QComboBox()
        self.font_selector.addItems(self.fonts)
        font_layout.addWidget(self.font_selector)
        self.layout.addLayout(font_layout)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nội dung", "Trạng thái", "Font chữ", "Tỉ lệ Video", "Xem Video"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.table)

        self.progress = QProgressBar()
        self.layout.addWidget(self.progress)

        self.generate_btn = QPushButton("🚀 Render Video")
        self.generate_btn.setEnabled(True)
        self.generate_btn.clicked.connect(self.start_batch_generation)
        self.layout.addWidget(self.generate_btn)

        self.setLayout(self.layout)

    def safe_update_status(self, index, status):
        QMetaObject.invokeMethod(self, "_update_status_gui", Qt.QueuedConnection, 
                                 Q_ARG(int, index), Q_ARG(str, status))

    @pyqtSlot(int, str)
    def _update_status_gui(self, index, status):
        item = QTableWidgetItem(status)
        item.setTextAlignment(Qt.AlignCenter)  # ✅ Căn giữa text
        self.table.setItem(index, 1, item)

        btn = self.table.cellWidget(index, 4)
        if status == "✅ Hoàn thành" and os.path.exists(os.path.join(OUTPUT_FOLDER, f"video_{index+1}.mp4")):
            if btn:
                btn.setEnabled(True)

        self.progress.setValue(self.progress.value() + 1)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục media")
        if folder:
            self.folder_path = folder
            self.select_folder_btn.setText(f"📁 Đã chọn: {folder}")

    def start_batch_generation(self):
        if not self.folder_path:
            QMessageBox.warning(self, "Thiếu thông tin", "Bạn cần chọn thư mục media trước.")
            return

        raw_text = self.text_input.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Thiếu văn bản", "Bạn cần nhập danh sách nội dung video.")
            return

        api_key = self.api_key_input.toPlainText().strip()
        if not api_key:
            QMessageBox.warning(self, "Thiếu API Key", "Vui lòng nhập API Key của ElevenLabs")
            return

        self.text_list = [txt.strip() for txt in raw_text.split("==|==") if txt.strip()]
        total_jobs = len(self.text_list)

        if total_jobs == 0:
            QMessageBox.warning(self, "Không có nội dung", "Vui lòng nhập ít nhất một đoạn text.")
            return

        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("🔄 Đang xử lý...")

        self.progress.setMaximum(total_jobs)
        self.progress.setValue(0)
        self.table.setRowCount(0)

        for f in os.listdir(OUTPUT_FOLDER):
            os.remove(os.path.join(OUTPUT_FOLDER, f))

        self.jobs_completed = 0
        self.total_jobs = total_jobs

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS)
        futures = []

        def update_progress_and_check(future):
            self.jobs_completed += 1
            if self.jobs_completed == self.total_jobs:
                self.generate_btn.setEnabled(True)
                self.generate_btn.setText("🚀 Tạo Video")

        for idx, text in enumerate(self.text_list):
            output_filename = os.path.join(OUTPUT_FOLDER, f"video_{idx+1}.mp4")
            self.add_table_row(idx, text)
            future = executor.submit(self.run_video_job, text, self.folder_path, output_filename, api_key, idx)
            future.add_done_callback(update_progress_and_check)

    def add_table_row(self, index, text):
        row = self.table.rowCount()
        self.table.insertRow(row)

        ratio_text = self.ratio_selector.currentText()
        font_text = self.font_selector.currentText()

        # Nội dung
        content_item = QTableWidgetItem(text[:50] + ("..." if len(text) > 50 else ""))
        content_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 0, content_item)

        # Trạng thái
        status_item = QTableWidgetItem("⏳ Đang xử lý")
        status_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 1, status_item)

        # Font chữ
        font_item = QTableWidgetItem(font_text)
        font_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 2, font_item)

        # Tỉ lệ video
        ratio_item = QTableWidgetItem(ratio_text)
        ratio_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 3, ratio_item)

        # Nút Player
        btn = QPushButton("Player")
        btn.setEnabled(False)
        btn.clicked.connect(lambda _, idx=index: self.open_video(idx + 1))
        self.table.setCellWidget(row, 4, btn)


    def open_video(self, index):
        path = os.path.join(OUTPUT_FOLDER, f"video_{index}.mp4")
        if os.path.exists(path):
            os.startfile(path)

    def run_video_job(self, text, folder_path, output_path, api_key, index):
        audio_file = f"temp_audio_{index}.mp3"
        sub_file = f"temp_sub_{index}.srt"
        temp_video = f"temp_video_{index}.mp4"

        try:
            for f in [audio_file, sub_file, temp_video]:
                if os.path.exists(f):
                    os.remove(f)

            create_voice_with_elevenlabs(text, audio_file, api_key)
            create_srt_word_by_word(audio_file, text, sub_file)
            duration = AudioSegment.from_file(audio_file).duration_seconds

            media_files = [
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if f.lower().endswith((".jpg", ".png", ".mp4", ".mov"))
            ]

            aspect_ratio = self.ratio_selector.currentText()
            is_vertical = aspect_ratio == "Dọc (9:16)"

            create_video_randomized_media(
                media_files=media_files,
                total_duration=duration,
                change_every=5,
                word_count=len(text.split()),
                output_file=temp_video,
                is_vertical=is_vertical
            )

            font_name = self.font_selector.currentText()

            burn_sub_and_audio(
                temp_video,
                sub_file,
                audio_file,
                output_path,
                font_name=font_name
            )

            self.safe_update_status(index, "✅ Hoàn thành")

        except Exception as e:
            print(f"❌ Lỗi tại video {index + 1}: {e}")
            self.safe_update_status(index, "❌ Lỗi")
            return

        for f in [audio_file, sub_file, temp_video]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as cleanup_err:
                print(f"⚠️ Không thể xoá file tạm {f}: {cleanup_err}")
