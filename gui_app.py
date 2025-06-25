import os
import random
import subprocess
import requests
import concurrent.futures
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel,
    QTextEdit, QProgressBar, QMessageBox, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QComboBox, QHeaderView, QGroupBox, QSizePolicy, QLineEdit
)
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QFont
from pydub import AudioSegment

from voice_generator import (
    create_voice_with_elevenlabs,
    create_or_replace_voice,
    validate_api_key,
    delete_voice
)

from subtitle_generator import create_srt_word_by_word
from video_creator import create_video_randomized_media, burn_sub_and_audio

MAX_THREADS = 2
OUTPUT_FOLDER = "outputs"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

class VideoGeneratorApp(QWidget):

    def setup_ui(self):
        self.setWindowTitle("🎬 AI Video Generator - @huyit32")
        self.setGeometry(200, 200, 800, 900)

        self.folder_path = ""
        self.text_list = []
        self.fonts = [
            "Arial", "Tahoma", "Times New Roman", "Verdana", "Helvetica",
            "Georgia", "Courier New", "Comic Sans MS", "Impact", "Trebuchet MS",
            "Lucida Console", "Palatino Linotype", "Garamond", "Segoe UI",
            "Candara", "Playbill", "Consolas", "Century Gothic", "Calibri"
        ]

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # --- Top row: API config + Folder chooser ---
        top_h_layout = QHBoxLayout()
        top_h_layout.setSpacing(30)

        # API Config group
        api_group = QGroupBox("🔐 Cấu hình ElevenLabs API")
        api_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        api_layout = QHBoxLayout()

        api_key_label = QLabel("API Key:")
        api_key_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        api_layout.addWidget(api_key_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Nhập API Key ElevenLabs")
        self.api_key_input.setToolTip("Nhập API Key ElevenLabs của bạn tại đây")
        api_layout.addWidget(self.api_key_input)

        voice_id_label = QLabel("Voice ID:")
        voice_id_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        api_layout.addWidget(voice_id_label)

        self.voice_id_input = QLineEdit()
        self.voice_id_input.setPlaceholderText("Nhập Voice ID (mặc định nếu để trống)")
        self.voice_id_input.setToolTip("Nhập Voice ID muốn dùng, ví dụ: Xb7hH8MSUJpSbSDYk0k2")
        api_layout.addWidget(self.voice_id_input)

        api_group.setLayout(api_layout)

        # Folder chooser group
        folder_group = QGroupBox("📁 Chọn thư mục chứa ảnh/video nền")
        folder_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(10)

        self.select_folder_btn = QPushButton("Chọn thư mục")
        self.select_folder_btn.setToolTip("Chọn thư mục chứa ảnh và video làm nền cho video đầu ra")
        self.select_folder_btn.setFixedSize(140, 35)
        self.select_folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.select_folder_btn)
        folder_group.setLayout(folder_layout)

        top_h_layout.addWidget(api_group, 2)
        top_h_layout.addWidget(folder_group, 1)

        main_layout.addLayout(top_h_layout)

        # --- Second row: Video settings + Music settings ---
        second_h_layout = QHBoxLayout()
        second_h_layout.setSpacing(40)

        # Video settings group
        settings_group = QGroupBox("Cài đặt video font")
        settings_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        settings_layout = QHBoxLayout()

        ratio_label = QLabel("Tỉ lệ video:")
        ratio_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        settings_layout.addWidget(ratio_label)

        self.ratio_selector = QComboBox()
        self.ratio_selector.addItems(["Dọc (9:16)", "Ngang (16:9)"])
        self.ratio_selector.setToolTip("Chọn tỉ lệ khung hình video")
        settings_layout.addWidget(self.ratio_selector)

        font_label = QLabel("Font chữ phụ đề:")
        font_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        settings_layout.addWidget(font_label)

        self.font_selector = QComboBox()
        self.font_selector.addItems(self.fonts)
        self.font_selector.setToolTip("Chọn font chữ cho phụ đề video")
        settings_layout.addWidget(self.font_selector)

        settings_layout.addStretch()
        settings_group.setLayout(settings_layout)

        # Music settings group
        music_group = QGroupBox("Nhạc nền âm lượng")
        music_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        music_layout = QHBoxLayout()

        music_label = QLabel("🎵 Nhạc nền:")
        music_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        music_layout.addWidget(music_label)

        self.music_selector = QComboBox()
        music_dir = "background_music"
        if not os.path.exists(music_dir):
            os.makedirs(music_dir)
        music_files = [f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".wav"))]
        if music_files:
            self.music_selector.addItems(music_files)
        else:
            self.music_selector.addItem("Không có nhạc nền")
        self.music_selector.setToolTip("Chọn nhạc nền cho video")
        music_layout.addWidget(self.music_selector)

        volume_label = QLabel("Âm lượng nhạc nền:")
        volume_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        music_layout.addWidget(volume_label)

        self.volume_selector = QComboBox()
        self.volume_selector.addItems(["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"])
        self.volume_selector.setCurrentText("30%")
        self.volume_selector.setToolTip("Chọn âm lượng nhạc nền")
        music_layout.addWidget(self.volume_selector)

        music_layout.addStretch()
        music_group.setLayout(music_layout)

        second_h_layout.addWidget(settings_group, 2)
        second_h_layout.addWidget(music_group, 3)

        main_layout.addLayout(second_h_layout)

        # --- Text input group ---
        text_group = QGroupBox("Nội dung văn bản cho video")
        text_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        text_layout = QVBoxLayout()
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("==|==\nVideo 1\n==|==\nVideo 2")
        self.text_input.setMinimumHeight(180)
        self.text_input.setFont(QFont("Consolas", 11))
        text_layout.addWidget(self.text_input)
        text_group.setLayout(text_layout)
        main_layout.addWidget(text_group)

        # --- Table widget ---
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Nội dung", "Trạng thái", "Font chữ", "Âm thanh", "Tỉ lệ Video", "Xem Video"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.table)

        # --- Progress bar ---
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p% - %v / %m")
        self.progress.setMinimumHeight(23)
        main_layout.addWidget(self.progress)

        # --- Generate button ---
        self.generate_btn = QPushButton("🚀 Render Video")
        self.generate_btn.setEnabled(True)
        self.generate_btn.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.generate_btn.setFixedHeight(33)
        self.generate_btn.clicked.connect(self.start_batch_generation)
        main_layout.addWidget(self.generate_btn)

        self.setLayout(main_layout)


    def __init__(self):
        super().__init__()
        self.setup_ui()



    def safe_update_status(self, index, status):
        QMetaObject.invokeMethod(self, "_update_status_gui", Qt.QueuedConnection, 
                                 Q_ARG(int, index), Q_ARG(str, status))


    @pyqtSlot(int, str)
    def _update_status_gui(self, index, status):
        item = QTableWidgetItem(status)
        item.setTextAlignment(Qt.AlignCenter)  # ✅ Căn giữa text
        self.table.setItem(index, 1, item)

        btn = self.table.cellWidget(index, 5)
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

        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Thiếu API Key", "Vui lòng nhập API Key của ElevenLabs")
            return

        if not validate_api_key(api_key):
            QMessageBox.critical(self, "API Key không hợp lệ", "API Key ElevenLabs không hợp lệ hoặc không thể kết nối.")
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

        # Âm thanh nền
        audio_item = QTableWidgetItem(self.music_selector.currentText())
        audio_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 3, audio_item)


        # Tỉ lệ video
        ratio_item = QTableWidgetItem(ratio_text)
        ratio_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 4, ratio_item)

        # Nút Player
        btn = QPushButton("Player")
        btn.setEnabled(False)
        btn.clicked.connect(lambda _, idx=index: self.open_video(idx + 1))
        self.table.setCellWidget(row, 5, btn)


    def open_video(self, index):
        path = os.path.join(OUTPUT_FOLDER, f"video_{index}.mp4")
        if os.path.exists(path):
            os.startfile(path)


    def run_video_job(self, text, folder_path, output_path, api_key, index):
        audio_file = f"temp_audio_{index}.mp3"
        sub_file = f"temp_sub_{index}.srt"
        temp_video = f"temp_video_{index}.mp4"

        voice_id = self.voice_id_input.text().strip()
        if not voice_id:
            voice_id = "EXAVITQu4vr4xnSDxMaL"  # default voice id nếu không nhập

        try:
            # Xóa các file tạm cũ nếu có
            for f in [audio_file, sub_file, temp_video]:
                if os.path.exists(f):
                    os.remove(f)

            # Tạo hoặc thay thế giọng mới (tự xử xóa giọng cũ nếu cần)
            create_or_replace_voice(text, audio_file, api_key, voice_id=voice_id)

            # Tạo phụ đề word-by-word
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

            background_music = self.music_selector.currentText()
            music_path = os.path.join("background_music", background_music)
            if not os.path.exists(music_path) or background_music == "Không có nhạc nền":
                music_path = None

            volume_str = self.volume_selector.currentText().replace("%", "").strip()
            try:
                music_volume = int(volume_str)
            except ValueError:
                music_volume = 30  # fallback nếu lỗi

            burn_sub_and_audio(
                temp_video,
                sub_file,
                audio_file,
                output_path,
                font_name=font_name,
                bg_music_path=music_path,
                bg_music_volume=music_volume
            )

            self.safe_update_status(index, "✅ Hoàn thành")

        except Exception as e:
            print(f"❌ Lỗi tại video {index + 1}: {e}")
            self.safe_update_status(index, "❌ Lỗi")
            return

        # Dọn sạch file tạm
        for f in [audio_file, sub_file, temp_video]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as cleanup_err:
                print(f"⚠️ Không thể xoá file tạm {f}: {cleanup_err}")
