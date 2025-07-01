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

from voice_elevenlabs import transcribe_audio, create_or_replace_voice, generate_karaoke_ass_from_srt_and_words, validate_api_key

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
            "volume": self.volume_selector.currentText()
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
            self.safe_append_log("📂 Đã tải preset thành công!")
        except Exception as e:
            self.safe_append_log(f"❌ Lỗi khi tải preset: {e}")


    def setup_ui(self):
        self.setWindowTitle("🎬 AI Video Generator v1.1 - @huyit32")
        self.setGeometry(200, 200, 1240, 850)

        self.folder_path = ""
        self.text_list = []
        self.fonts = [
            "Arial", "Tahoma", "Times New Roman", "Verdana", "Helvetica",
            "Georgia", "Courier New", "Comic Sans MS", "Impact", "Trebuchet MS",
            "Lucida Console", "Palatino Linotype", "Garamond", "Segoe UI",
            "Candara", "Playbill", "Consolas", "Century Gothic", "Calibri"
        ]

        main_layout = QHBoxLayout()  # Sử dụng QHBoxLayout để chia layout thành 2 cột
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Cột trái (Form chính)
        left_column_layout = QVBoxLayout()

        # --- Preset Buttons ---
        preset_buttons_layout = QHBoxLayout()
        preset_buttons_layout.setSpacing(15)

        self.save_preset_btn = QPushButton("💾 Lưu cấu hình")
        self.save_preset_btn.clicked.connect(self.save_preset)
        preset_buttons_layout.addWidget(self.save_preset_btn)

        self.load_preset_btn = QPushButton("📂 Tải cấu hình")
        self.load_preset_btn.clicked.connect(self.load_preset)
        preset_buttons_layout.addWidget(self.load_preset_btn)

        left_column_layout.addLayout(preset_buttons_layout)

        # --- API Key + Folder ---
        top_h_layout = QHBoxLayout()
        top_h_layout.setSpacing(30)

        api_group = QGroupBox("🔐 Cấu hình ElevenLabs API")
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        api_layout.addWidget(self.api_key_input)

        api_layout.addWidget(QLabel("Voice ID:"))
        self.voice_id_input = QLineEdit()
        api_layout.addWidget(self.voice_id_input)
        api_group.setLayout(api_layout)

        folder_group = QGroupBox("📁 Chọn thư mục media")
        folder_layout = QHBoxLayout()
        self.select_folder_btn = QPushButton("Chọn thư mục")
        self.select_folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.select_folder_btn)
        folder_group.setLayout(folder_layout)

        top_h_layout.addWidget(api_group, 2)
        top_h_layout.addWidget(folder_group, 1)
        left_column_layout.addLayout(top_h_layout)

        # --- Video & Music Settings ---
        second_h_layout = QHBoxLayout()

        settings_group = QGroupBox("🎞️ Video & Font Settings")
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Tỉ lệ video:"))
        self.ratio_selector = QComboBox()
        self.ratio_selector.addItems(["Dọc (9:16)", "Ngang (16:9)"])
        settings_layout.addWidget(self.ratio_selector)

        settings_layout.addWidget(QLabel("Font chữ phụ đề:"))
        self.font_selector = QComboBox()
        self.font_selector.addItems(self.fonts)
        settings_layout.addWidget(self.font_selector)
        settings_group.setLayout(settings_layout)

        subtitle_group = QGroupBox("📜 Subtitle Options")
        subtitle_layout = QHBoxLayout()
        subtitle_layout.addWidget(QLabel("Cỡ chữ:"))
        self.subtitle_font_size_selector = QComboBox()
        self.subtitle_font_size_selector.addItems([str(size) for size in range(10, 31)])
        self.subtitle_font_size_selector.setCurrentText("15")
        subtitle_layout.addWidget(self.subtitle_font_size_selector)

        subtitle_layout.addWidget(QLabel("Màu chữ:"))
        self.subtitle_color_selector = QComboBox()
        self.subtitle_color_selector.addItem("Trắng", "FFFFFF")
        self.subtitle_color_selector.addItem("Đen", "000000")
        self.subtitle_color_selector.addItem("Xanh Dương", "00FFFF")
        self.subtitle_color_selector.addItem("Đỏ", "FF0000")
        self.subtitle_color_selector.addItem("Vàng", "FFFF00")
        self.subtitle_color_selector.addItem("Xanh Lá", "00FF00")
        self.subtitle_color_selector.setCurrentText("Xanh Dương")
        subtitle_layout.addWidget(self.subtitle_color_selector)
        subtitle_group.setLayout(subtitle_layout)

        second_h_layout.addWidget(settings_group, 2)
        second_h_layout.addWidget(subtitle_group, 2)
        left_column_layout.addLayout(second_h_layout)

        music_group = QGroupBox("🎵 Background Music")
        music_layout = QHBoxLayout()
        music_layout.addWidget(QLabel("Nhạc nền:"))
        self.music_selector = QComboBox()
        music_dir = "background_music"
        if not os.path.exists(music_dir):
            os.makedirs(music_dir)
        music_files = [f for f in os.listdir(music_dir) if f.endswith((".mp3", ".wav"))]
        if music_files:
            self.music_selector.addItem("Không có nhạc nền")
            self.music_selector.addItems(music_files)
        else:
            self.music_selector.addItem("Không có nhạc nền")

        music_layout.addWidget(self.music_selector)

        music_layout.addWidget(QLabel("Âm lượng:"))
        self.volume_selector = QComboBox()
        self.volume_selector.addItems([f"{i}%" for i in range(10, 110, 10)])
        self.volume_selector.setCurrentText("30%")
        music_layout.addWidget(self.volume_selector)
        music_group.setLayout(music_layout)

        left_column_layout.addWidget(music_group)

        # --- Text input ---
        text_group = QGroupBox("📝 Video Text Content")
        text_layout = QVBoxLayout()
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("==|==\nVideo 1\n==|==\nVideo 2")
        text_layout.addWidget(self.text_input)
        text_group.setLayout(text_layout)
        left_column_layout.addWidget(text_group)

        # Add Left column layout to the main layout (first column)
        main_layout.addLayout(left_column_layout, 4)  # Tăng tỷ lệ cho cột trái

        # --- Right column layout ---
        right_column_layout = QVBoxLayout()

        # --- Log output GroupBox ---
        log_group = QGroupBox("📋 Log Output")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        log_layout = QVBoxLayout()

        # Log Output widget
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("📋 Log chi tiết sẽ hiển thị tại đây...")
        log_layout.addWidget(self.log_output)

        log_group.setLayout(log_layout)

        # --- Table GroupBox ---
        table_group = QGroupBox("📊 Table: Video Status")
        table_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        table_layout = QVBoxLayout()

        # Table widget
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Nội dung", "Trạng thái", "Font chữ", "Âm thanh", "Tỉ lệ Video", "Xem Video"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.table)

        table_group.setLayout(table_layout)

        # Add Log GroupBox, Table GroupBox, and other components to right_column_layout
        right_column_layout.addWidget(log_group)  # Add Log Output group
        right_column_layout.addWidget(table_group)  # Add Table group

        # --- Bottom section for progress and render button ---
        bottom_section_layout = QVBoxLayout()

        # --- Progress Bar ---
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        bottom_section_layout.addWidget(self.progress)

        # --- Generate Button ---
        self.generate_btn = QPushButton("🚀 Render Video")
        self.generate_btn.clicked.connect(self.start_batch_generation)
        bottom_section_layout.addWidget(self.generate_btn)

        # Add bottom section layout to right column layout
        right_column_layout.addLayout(bottom_section_layout)

        # Add right_column_layout to main layout (second column)
        main_layout.addLayout(right_column_layout, 3)  # Right column takes less space

        # Set main layout
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
                try:
                    if os.path.exists(f):
                        os.remove(f)
                        log(f"🧹 Đã xóa file tạm: {f}")
                except Exception as cleanup_err:
                    log(f"⚠️ Không thể xoá file tạm {f}: {cleanup_err}")
    
            create_or_replace_voice(text, audio_file, api_key, voice_id=voice_id)
            log("📝 Tạo giọng và lưu file audio thành công")

            log("🧠 Đang dùng ElevenLabs để tạo phụ đề...")
            trans_result = transcribe_audio(
                    audio_path=audio_file,
                    output_base=f"video_{index+1}",
                    api_key=api_key
                )
            sub_file = trans_result["srt_path"]
            karaoke_json = trans_result["karaoke_path"]

            log("✨ Đang tạo file karaoke .ass từ ElevenLabs...")
            ass_file = os.path.join("outputs", f"video_{index+1}.ass")
            generate_karaoke_ass_from_srt_and_words(
                    sub_file,
                    karaoke_json,
                    ass_file,
                    font=self.font_selector.currentText(),
                    size = int(self.subtitle_font_size_selector.currentText())
                )
            log(f"🎉 Đã tạo file phụ đề .ass: {ass_file}")


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
            font_color_hex = self.subtitle_color_selector.currentData() or "00FFFF"


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



            print(f"[DEBUG] Xuất ra: {output_path} | type: {type(output_path)}")

            # Gọi hàm render
            burn_sub_and_audio(
                video_path=temp_video,
                srt_path=ass_file,
                voice_path=audio_file,
                output_path=output_path,
                font_name=font_name,
                font_size=font_size,
                font_color=font_color_hex,
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

        extra_temp_files = [ass_file, karaoke_json]
        for f in extra_temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    log(f"🧹 Đã xóa file phụ trợ: {f}")
            except Exception as cleanup_err:
                log(f"⚠️ Không thể xoá file phụ trợ {f}: {cleanup_err}")

