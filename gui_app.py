import os
import random
import subprocess
import requests
import concurrent.futures
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel,
    QTextEdit, QProgressBar, QMessageBox, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QComboBox, QHeaderView, QGroupBox, QSizePolicy, QLineEdit, QPlainTextEdit
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
from subtitle_from_elevenlabs import generate_srt_from_audio
from video_creator import create_video_randomized_media, burn_sub_and_audio

MAX_THREADS = 2
OUTPUT_FOLDER = "outputs"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

class VideoGeneratorApp(QWidget):


    def save_preset(self):
        preset = {
            "api_key": self.api_key_input.text(),
            "voice_id": self.voice_id_input.text(),
            "ratio": self.ratio_selector.currentText(),
            "font": self.font_selector.currentText(),
            "font_size": self.subtitle_font_size_selector.currentText(),
            "font_color": self.subtitle_color_selector.currentData(),
            "music": self.music_selector.currentText(),
            "volume": self.volume_selector.currentText(),
            "subtitle_mode": self.subtitle_mode_selector.currentText(),
            "language_code": self.language_code_selector.currentText(),
            "subtitle_display": self.subtitle_display_selector.currentText()
        }
        try:
            with open("preset_config.json", "w", encoding="utf-8") as f:
                import json
                json.dump(preset, f, ensure_ascii=False, indent=2)
            self.safe_append_log("💾 Đã lưu preset thành công!")
        except Exception as e:
            self.safe_append_log(f"❌ Lỗi khi lưu preset: {e}")


    def load_preset(self):
        try:
            import json
            with open("preset_config.json", "r", encoding="utf-8") as f:
                preset = json.load(f)
            self.api_key_input.setText(preset.get("api_key", ""))
            self.voice_id_input.setText(preset.get("voice_id", ""))
            self.ratio_selector.setCurrentText(preset.get("ratio", "Dọc (9:16)"))
            self.font_selector.setCurrentText(preset.get("font", "Playbill"))
            self.subtitle_font_size_selector.setCurrentText(preset.get("font_size", "15"))
            self.subtitle_color_selector.setCurrentIndex(
                self.subtitle_color_selector.findData(preset.get("font_color", "00FFFF"))
            )
            self.music_selector.setCurrentText(preset.get("music", "Không có nhạc nền"))
            self.volume_selector.setCurrentText(preset.get("volume", "30%"))
            self.subtitle_mode_selector.setCurrentText(preset.get("subtitle_mode", "Từ văn bản nhập"))
            self.language_code_selector.setCurrentText(preset.get("language_code", "vie"))
            self.subtitle_display_selector.setCurrentText(preset.get("subtitle_display", "Hiển thị phụ đề"))
            self.safe_append_log("📂 Đã tải preset thành công!")
        except Exception as e:
            self.safe_append_log(f"❌ Lỗi khi tải preset: {e}")


    def setup_ui(self):
        self.setWindowTitle("🎬 AI Video Generator v1.1 - @huyit32")
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



        # --- Preset Buttons ---
        preset_buttons_layout = QHBoxLayout()
        preset_buttons_layout.setSpacing(15)

        self.save_preset_btn = QPushButton("💾 Lưu cấu hình")
        self.save_preset_btn.setToolTip("Lưu lại toàn bộ cấu hình hiện tại thành preset")
        self.save_preset_btn.clicked.connect(self.save_preset)
        preset_buttons_layout.addWidget(self.save_preset_btn)

        self.load_preset_btn = QPushButton("📂 Tải cấu hình")
        self.load_preset_btn.setToolTip("Tải lại cấu hình đã lưu trước đó")
        self.load_preset_btn.clicked.connect(self.load_preset)
        preset_buttons_layout.addWidget(self.load_preset_btn)

        main_layout.addLayout(preset_buttons_layout)





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


        # === Subtitle settings group ===
        subtitle_group = QGroupBox("📜 Tùy chọn phụ đề")
        subtitle_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        subtitle_layout = QHBoxLayout()

        # Chế độ phụ đề
        subtitle_layout.addWidget(QLabel("Chế độ tạo phụ đề:"))

        self.subtitle_mode_selector = QComboBox()
        self.subtitle_mode_selector.addItems(["Từ văn bản nhập (shorts)", "Tạo tự động bằng ElevenLabs (video)"])
        self.subtitle_mode_selector.setToolTip("Chọn cách tạo phụ đề")
        subtitle_layout.addWidget(self.subtitle_mode_selector)

        # Label + Combo chọn ngôn ngữ
        self.language_label = QLabel("Ngôn ngữ:")
        self.language_code_selector = QComboBox()
        self.language_code_selector.addItems(["vie", "en", "es", "fr", "de", "ja", "ko", "zh"])
        self.language_code_selector.setToolTip("Chọn ngôn ngữ cho ElevenLabs STT")

        # Ẩn mặc định cả label và combo
        self.language_label.hide()
        self.language_code_selector.hide()

        subtitle_layout.addWidget(self.language_label)
        subtitle_layout.addWidget(self.language_code_selector)

        # Cỡ chữ phụ đề
        font_size_label = QLabel("Cỡ chữ:")
        self.subtitle_font_size_selector = QComboBox()
        self.subtitle_font_size_selector.addItems([str(size) for size in range(10, 31)])
        self.subtitle_font_size_selector.setCurrentText("15")
        self.subtitle_font_size_selector.setToolTip("Chọn kích thước chữ phụ đề")
        subtitle_layout.addWidget(font_size_label)
        subtitle_layout.addWidget(self.subtitle_font_size_selector)

        # Màu chữ phụ đề
        font_color_label = QLabel("Màu chữ:")
        self.subtitle_color_selector = QComboBox()
        self.subtitle_color_selector.addItem("Trắng", "FFFFFF")
        self.subtitle_color_selector.addItem("Đen", "000000")
        self.subtitle_color_selector.addItem("Xanh Dương", "00FFFF")
        self.subtitle_color_selector.addItem("Đỏ", "FF0000")
        self.subtitle_color_selector.addItem("Vàng", "FFFF00")
        self.subtitle_color_selector.addItem("Xanh Lá", "00FF00")
        self.subtitle_color_selector.setCurrentText("Xanh Dương")
        self.subtitle_color_selector.setToolTip("Chọn màu chữ phụ đề")
        subtitle_layout.addWidget(font_color_label)
        subtitle_layout.addWidget(self.subtitle_color_selector)


        # Sự kiện khi thay đổi chế độ
        def toggle_language_ui(index):
            show_lang = index == 1  # chỉ hiển thị nếu chọn "Tạo tự động bằng ElevenLabs"
            self.language_label.setVisible(show_lang)
            self.language_code_selector.setVisible(show_lang)

        self.subtitle_mode_selector.currentIndexChanged.connect(toggle_language_ui)

        subtitle_group.setLayout(subtitle_layout)


        # === Subtitle display option group ===
        subtitle_display_group = QGroupBox("🎛️ Tuỳ chọn hiển thị phụ đề")
        subtitle_display_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        subtitle_display_layout = QHBoxLayout()

        subtitle_display_layout.addWidget(QLabel("Phụ đề:"))

        self.subtitle_display_selector = QComboBox()
        self.subtitle_display_selector.addItems(["Hiển thị phụ đề", "Ẩn phụ đề"])
        self.subtitle_display_selector.setToolTip("Chọn xem có muốn hiển thị phụ đề trong video hay không")
        subtitle_display_layout.addWidget(self.subtitle_display_selector)
        subtitle_display_layout.addStretch()

        subtitle_display_group.setLayout(subtitle_display_layout)

        # === Đưa 2 group vào cùng 1 hàng ngang ===
        subtitle_row_layout = QHBoxLayout()
        subtitle_row_layout.setSpacing(20)
        subtitle_row_layout.addWidget(subtitle_group, 2)
        subtitle_row_layout.addWidget(subtitle_display_group, 1)
        main_layout.addLayout(subtitle_row_layout)

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

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)
        self.log_output.setPlaceholderText("📋 Log chi tiết sẽ hiển thị tại đây...")
        main_layout.addWidget(self.log_output)

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


    @pyqtSlot(str)
    def append_log(self, message):
        self.log_output.appendPlainText(message)

    def safe_append_log(self, message: str):
        QMetaObject.invokeMethod(self, "append_log", Qt.QueuedConnection, Q_ARG(str, message))


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

        # Clear log cũ trước khi chạy batch mới
        self.log_output.clear()
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
        def log(msg):
            self.safe_append_log(f"[Video #{index + 1}] {msg}")

        log("🔄 Bắt đầu xử lý")

        audio_file = f"temp_audio_{index}.mp3"
        sub_file = f"temp_sub_{index}.srt"
        temp_video = f"temp_video_{index}.mp4"

        voice_id = self.voice_id_input.text().strip()
        if not voice_id:
            voice_id = "EXAVITQu4vr4xnSDxMaL"

        try:
            log(f"🎤 Đang tạo giọng với Voice ID: {voice_id}")

            for f in [audio_file, sub_file, temp_video]:
                if os.path.exists(f):
                    os.remove(f)
                    log(f"🧹 Xóa file tạm: {f}")

            create_or_replace_voice(text, audio_file, api_key, voice_id=voice_id)
            log("📝 Tạo giọng và lưu file audio thành công")

            subtitle_mode = self.subtitle_mode_selector.currentText()
            if subtitle_mode == "Tạo tự động bằng ElevenLabs (video)":
                language_code = self.language_code_selector.currentText()
                log(f"📝 Gửi audio đến ElevenLabs để tạo phụ đề tự động (ngôn ngữ: {language_code})")
                generate_srt_from_audio(audio_file, sub_file, api_key, language_code=language_code)
                log("✅ Đã tạo phụ đề từ ElevenLabs thành công")
            else:
                log("📝 Tạo phụ đề Từ văn bản nhập (shorts)")
                create_srt_word_by_word(audio_file, text, sub_file)
                log("✅ Đã tạo phụ đề từ văn bản")

            duration = AudioSegment.from_file(audio_file).duration_seconds
            log(f"⏳ Độ dài audio: {duration:.2f} giây")

            media_files = [
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if f.lower().endswith((".jpg", ".png", ".mp4", ".mov"))
            ]
            log(f"📂 Tìm thấy {len(media_files)} file media trong thư mục")

            aspect_ratio = self.ratio_selector.currentText()
            is_vertical = aspect_ratio == "Dọc (9:16)"
            log(f"📐 Tỉ lệ video: {aspect_ratio}")

            create_video_randomized_media(
                media_files=media_files,
                total_duration=duration,
                change_every=5,
                word_count=len(text.split()),
                output_file=temp_video,
                is_vertical=is_vertical
            )
            log("🎞️ Tạo video nền hoàn tất")

            font_name = self.font_selector.currentText()
            font_size = self.subtitle_font_size_selector.currentText()
            font_color_hex = self.subtitle_color_selector.currentData() or "00FFFF"  # fallback nếu không chọn
            subtitle_visible = self.subtitle_display_selector.currentText() == "Hiển thị phụ đề"


            background_music = self.music_selector.currentText()
            music_path = os.path.join("background_music", background_music)
            if not os.path.exists(music_path) or background_music == "Không có nhạc nền":
                music_path = None
                log("🎵 Không sử dụng nhạc nền")
            else:
                log(f"🎵 Nhạc nền: {background_music}")

            volume_str = self.volume_selector.currentText().replace("%", "").strip()
            try:
                music_volume = int(volume_str)
            except ValueError:
                music_volume = 30
            log(f"🔊 Âm lượng nhạc nền: {music_volume}%")

            # Kiểm tra có hiển thị phụ đề không
            hide_subtitle = self.subtitle_display_selector.currentText() == "Ẩn phụ đề"
            if hide_subtitle:
                log("👁️‍🗨️ Đã chọn ẩn phụ đề trong video")

            # Gọi hàm render
            burn_sub_and_audio(
                video=temp_video,
                srt=sub_file,
                audio=audio_file,
                output=output_path,
                font_name=font_name,
                font_size=font_size,
                font_color=font_color_hex,
                show_subtitle=subtitle_visible,
                bg_music_path=music_path,
                bg_music_volume=music_volume
            )

            log("🎬 Video cuối cùng đã được render và lưu")

            self.safe_update_status(index, "✅ Hoàn thành")

        except Exception as e:
            log(f"❌ Lỗi: {e}")
            self.safe_update_status(index, "❌ Lỗi")
            return

        for f in [audio_file, sub_file, temp_video]:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    log(f"🧹 Đã xóa file tạm: {f}")
            except Exception as cleanup_err:
                log(f"⚠️ Không thể xoá file tạm {f}: {cleanup_err}")
