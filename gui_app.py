import os
import time
import requests
import torch
import concurrent.futures
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel,
    QTextEdit, QProgressBar, QMessageBox, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QComboBox, QHeaderView, QGroupBox, QPlainTextEdit
)
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QFont
from pydub import AudioSegment
from voice_google import transcribe_audio, generate_karaoke_ass_from_srt_and_words, fetch_api_keys, create_voice_with_retry
from video_creator import create_video_randomized_media, burn_sub_and_audio


def wait_for_file(filepath, timeout=10):
        start = time.time()
        while not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            if time.time() - start > timeout:
                raise TimeoutError(f"⏰ File chưa sẵn sàng sau {timeout}s: {filepath}")
            time.sleep(0.2)



def fetch_languages():
    try:
        response = requests.get("http://62.171.131.164:5000/api/get_gemini_languages", timeout=5)
        if response.ok:
            return response.json().get("languages", [])
    except Exception as e:
        print(f"❌ Không thể lấy danh sách ngôn ngữ: {e}")
    return []


def safe_remove_file(file_path, log_func=None, retries=3, delay=0.5):
        for attempt in range(retries):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    if log_func:
                        log_func(f"🧹 Đã xóa file: {file_path}")
                    return True
                else:
                    return True
            except PermissionError:
                if log_func:
                    log_func(f"⚠️ File đang được sử dụng, thử lại lần {attempt + 1}/{retries}: {file_path}")
                time.sleep(delay)
        if log_func:
            log_func(f"❌ Không thể xóa file sau {retries} lần thử: {file_path}")
        return False


MAX_THREADS = 3


class VideoGeneratorApp(QWidget):

    def save_preset(self):
        preset = {
            "ratio": self.ratio_selector.currentText(),
            "font": self.font_selector.currentText(),
            "font_size": self.subtitle_font_size_selector.currentText(),
            "base_color": self.subtitle_base_color_selector.currentData(),
            "highlight_color": self.subtitle_highlight_color_selector.currentData(),
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
            self.ratio_selector.setCurrentText(preset.get("ratio", "Dọc (9:16)"))
            self.font_selector.setCurrentText(preset.get("font", "Playbill"))
            self.subtitle_font_size_selector.setCurrentText(preset.get("font_size", "15"))
            self.subtitle_base_color_selector.setCurrentIndex(
                self.subtitle_base_color_selector.findData(preset.get("base_color", "FFFFFF"))
            )
            self.subtitle_highlight_color_selector.setCurrentIndex(
                self.subtitle_highlight_color_selector.findData(preset.get("highlight_color", "FFFF00"))
            )
            self.music_selector.setCurrentText(preset.get("music", "Không có nhạc nền"))
            self.volume_selector.setCurrentText(preset.get("volume", "30%"))
            self.safe_append_log("📂 Đã tải preset thành công!")
        except Exception as e:
            self.safe_append_log(f"❌ Lỗi khi tải preset: {e}")


    def setup_ui(self):
        self.setWindowTitle("🎬 AI Video Generator v2.0 - @huyit32")
        self.setGeometry(200, 200, 1340, 900)
        self.setFont(QFont("Roboto", 10))

        self.folder_path = ""
        self.text_list = []

        # Thư mục chứa các font
        fonts_folder = "fonts"
        self.fonts = []

        if os.path.exists(fonts_folder):
            # Lấy tất cả các font .ttf trong thư mục "fonts"
            font_files = [f for f in os.listdir(fonts_folder) if f.endswith(".ttf")]
            self.fonts = [os.path.splitext(font)[0] for font in font_files]  # Lấy tên font mà không có đuôi .ttf

        # Nếu không có font nào, thêm một số font mặc định vào
        if not self.fonts:
            self.fonts = [
                "Arial", "Tahoma", "Times New Roman", "Verdana", "Helvetica",
                "Georgia", "Courier New", "Comic Sans MS", "Impact", "Trebuchet MS",
                "Lucida Console", "Palatino Linotype", "Garamond", "Segoe UI",
                "Candara", "Playbill", "Consolas", "Century Gothic", "Calibri"
            ]

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # === CỘT TRÁI ===
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

        self.reload_btn = QPushButton("🔄 Reload")
        self.reload_btn.clicked.connect(self.full_reload_ui)
        preset_buttons_layout.addWidget(self.reload_btn)

        left_column_layout.addLayout(preset_buttons_layout)

        # --- TOP ROW: Voice + Folder + Font Settings ---
        top_h_layout = QHBoxLayout()
        top_h_layout.setSpacing(10)

        # Voice config
        api_group = QGroupBox("🔐 Setting Voice")
        api_layout = QHBoxLayout()
        voices = [
            "achernar", "achird", "algenib", "algieba", "alnilam", "aoede", "autonoe", "callirrhoe", 
            "charon", "despina", "enceladus", "erinome", "fenrir", "gacrux", "iapetus", "kore", 
            "laomedeia", "leda", "orus", "puck", "pulcherrima", "rasalgethi", "sadachbia", "sadaltager", 
            "schedar", "sulafat", "umbriel", "vindemiatrix", "zephyr", "zubenelgenubi"
        ]
        api_layout.addWidget(QLabel("Voice:"))
        self.voice_selector = QComboBox()
        self.voice_selector.addItems(voices)
        api_layout.addWidget(self.voice_selector)
        api_group.setLayout(api_layout)

        # Folder selection
        folder_group = QGroupBox("📁 Folder media")
        folder_layout = QHBoxLayout()
        self.select_folder_btn = QPushButton("Chọn thư mục")
        self.select_folder_btn.clicked.connect(self.select_folder)
        self.select_folder_btn.setFixedWidth(150)
        folder_layout.addWidget(self.select_folder_btn)
        folder_group.setLayout(folder_layout)

        # Font Settings
        settings_group = QGroupBox("🎞️ Video Font Settings")
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Tỉ lệ video:"))
        self.ratio_selector = QComboBox()
        self.ratio_selector.addItems(["Dọc (9:16)", "Ngang (16:9)"])
        settings_layout.addWidget(self.ratio_selector)

        settings_layout.addWidget(QLabel("Font chữ phụ đề:"))
        self.font_selector = QComboBox()
        self.font_selector.addItems(self.fonts)  # Sử dụng font từ thư mục
        settings_layout.addWidget(self.font_selector)

        # ✅ Thêm checkbox "Crop video"
        self.crop_checkbox = QPushButton("🖼️ Crop: OFF")
        self.crop_checkbox.setCheckable(True)
        self.crop_checkbox.setChecked(False)
        self.crop_checkbox.clicked.connect(self.toggle_crop_checkbox)
        settings_layout.addWidget(self.crop_checkbox)

        settings_group.setLayout(settings_layout)


        # Add 3 group boxes vào hàng đầu
        top_h_layout.addWidget(api_group, 3)
        top_h_layout.addWidget(folder_group, 3)
        top_h_layout.addWidget(settings_group, 4)
        left_column_layout.addLayout(top_h_layout)

        # --- Subtitle Options ---
        subtitle_group = QGroupBox("📜 Subtitle Options")
        subtitle_layout = QVBoxLayout()

        # Row 1: Subtitle Toggle + Mode
        subtitle_row1 = QHBoxLayout()
        subtitle_row1.addWidget(QLabel("💬 Phụ đề:"))
        self.subtitle_enabled_selector = QComboBox()
        self.subtitle_enabled_selector.addItems(["Có phụ đề", "Không phụ đề"])
        subtitle_row1.addWidget(self.subtitle_enabled_selector)

        subtitle_row1.addSpacing(20)
        subtitle_row1.addWidget(QLabel("📺 Kiểu Phụ Đề:"))
        self.subtitle_mode = QComboBox()
        self.subtitle_mode.addItems([
            "Phụ đề thường (toàn câu)",
            "Hiệu ứng từng chữ một (chuyên sâu)",
        ])
        subtitle_row1.addWidget(self.subtitle_mode)

        subtitle_layout.addLayout(subtitle_row1)

        # Row 2: Font size + Base color + Highlight color
        subtitle_row2 = QHBoxLayout()
        subtitle_row2.addWidget(QLabel("Cỡ chữ:"))
        self.subtitle_font_size_selector = QComboBox()
        self.subtitle_font_size_selector.addItems([str(size) for size in range(10, 31)])
        self.subtitle_font_size_selector.setCurrentText("10")
        subtitle_row2.addWidget(self.subtitle_font_size_selector)

        subtitle_row2.addSpacing(20)
        subtitle_row2.addWidget(QLabel("🎨 Base Color:"))
        self.subtitle_base_color_selector = QComboBox()
        self.subtitle_base_color_selector.addItem("Trắng", "FFFFFF")
        self.subtitle_base_color_selector.addItem("Đen", "000000")
        self.subtitle_base_color_selector.addItem("Xanh Dương", "00FFFF")
        self.subtitle_base_color_selector.addItem("Đỏ", "FF0000")
        self.subtitle_base_color_selector.addItem("Vàng", "FFFF00")
        self.subtitle_base_color_selector.addItem("Xanh Lá", "00FF00")
        self.subtitle_base_color_selector.addItem("Tím", "800080")
        self.subtitle_base_color_selector.addItem("Hồng", "FF69B4")
        self.subtitle_base_color_selector.setCurrentText("Trắng")
        subtitle_row2.addWidget(self.subtitle_base_color_selector)

        subtitle_row2.addSpacing(20)
        subtitle_row2.addWidget(QLabel("✨ Highlight Color:"))
        self.subtitle_highlight_color_selector = QComboBox()
        self.subtitle_highlight_color_selector.addItem("Vàng", "FFFF00")
        self.subtitle_highlight_color_selector.addItem("Xanh Dương", "00FFFF")
        self.subtitle_highlight_color_selector.addItem("Đỏ", "FF0000")
        self.subtitle_highlight_color_selector.addItem("Trắng", "FFFFFF")
        self.subtitle_highlight_color_selector.addItem("Hồng", "FF69B4")
        self.subtitle_highlight_color_selector.setCurrentText("Vàng")
        subtitle_row2.addWidget(self.subtitle_highlight_color_selector)

        subtitle_layout.addLayout(subtitle_row2)

        # Row 3: Subtitle position + Language
        subtitle_row3 = QHBoxLayout()
        subtitle_row3.addWidget(QLabel("Vị trí phụ đề:"))
        self.subtitle_position_selector = QComboBox()
        self.subtitle_position_selector.addItems(["Dưới", "Giữa", "Trên"])
        subtitle_row3.addWidget(self.subtitle_position_selector)

        subtitle_row3.addSpacing(20)
        subtitle_row3.addWidget(QLabel("Ngôn ngữ:"))
        self.language_selector = QComboBox()
        self.languages = fetch_languages()
        self.language_selector.addItem("🔍 Auto Detect", None)
        if self.languages:
            for lang in self.languages:
                self.language_selector.addItem(lang["name"], lang["code"])
        subtitle_row3.addWidget(self.language_selector)

        subtitle_layout.addLayout(subtitle_row3)

        subtitle_group.setLayout(subtitle_layout)
        left_column_layout.addWidget(subtitle_group)

        # CPU/GPU and Model selection in one GroupBox on the same row
        cpu_model_group = QGroupBox("⚙️ Cấu hình CPU/GPU + Model")
        cpu_model_layout = QHBoxLayout()  # Horizontal layout for placing items in the same row

        # CPU/GPU selection
        cpu_layout = QHBoxLayout()
        cpu_layout.addWidget(QLabel("💻 CPU/GPU:"))
        self.cpu_selector = QComboBox()
        self.cpu_selector.addItems(["CPU", "GPU"])
        cpu_layout.addWidget(self.cpu_selector)

        # Model selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("🧠 Model:"))
        self.model_selector = QComboBox()
        self.model_selector.addItems(["tiny", "base", "small", "medium", "large"])
        model_layout.addWidget(self.model_selector)

        # Combine both layouts into the main layout for CPU/GPU and Model selection
        cpu_model_layout.addLayout(cpu_layout)
        cpu_model_layout.addLayout(model_layout)

        # Set the layout for the group box and add it to the main layout
        cpu_model_group.setLayout(cpu_model_layout)
        left_column_layout.addWidget(cpu_model_group)

        # --- Background Music ---
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

        # --- Text Input ---
        text_group = QGroupBox("📝 Video Text Content")
        text_layout = QVBoxLayout()
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("==|==\nVideo 1\n==|==\nVideo 2")
        text_layout.addWidget(self.text_input)
        text_group.setLayout(text_layout)
        left_column_layout.addWidget(text_group)

        main_layout.addLayout(left_column_layout, 4)

        # === CỘT PHẢI ===
        right_column_layout = QVBoxLayout()

        log_group = QGroupBox("📋 Log Output")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        log_layout = QVBoxLayout()
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("📋 Log chi tiết sẽ hiển thị tại đây...")
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)

        table_group = QGroupBox("📊 Table: Video Status")
        table_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        table_layout = QVBoxLayout()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Nội dung", "Trạng thái", "Font chữ", "Âm thanh", "Tỉ lệ Video", "Xem Video"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)

        bottom_section_layout = QVBoxLayout()
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        bottom_section_layout.addWidget(self.progress)

        self.generate_btn = QPushButton("🚀 Tạo Video")
        self.generate_btn.clicked.connect(self.start_batch_generation)
        bottom_section_layout.addWidget(self.generate_btn)

        right_column_layout.addWidget(log_group)
        right_column_layout.addWidget(table_group)
        right_column_layout.addLayout(bottom_section_layout)

        main_layout.addLayout(right_column_layout, 3)
        self.setLayout(main_layout)


    def full_reload_ui(self):
        confirm = QMessageBox.question(
            self,
            "Reload?",
            "Bạn có chắc chắn muốn khởi động lại toàn bộ dữ liệu?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self.safe_append_log("🔁 Đang reload toàn bộ dữ liệu...")

        self.new_instance = VideoGeneratorApp()
        self.new_instance.show()

        self.close()


    def toggle_crop_checkbox(self):
        if self.crop_checkbox.isChecked():
            self.crop_checkbox.setText("🖼️ Crop: ON")
        else:
            self.crop_checkbox.setText("🖼️ Crop: OFF")



    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.output_folder = ""


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

        # 🔄 Dùng self.output_folder thay vì OUTPUT_FOLDER
        if status == "✅ Hoàn thành" and self.output_folder:
            video_path = os.path.join(self.output_folder, f"video_{index+1}.mp4")
            if os.path.exists(video_path):
                if btn:
                    btn.setEnabled(True)

        self.progress.setValue(self.progress.value() + 1)




    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục media")
        if folder:
            self.folder_path = folder
            self.select_folder_btn.setText(f"📁 Đã chọn: {folder}")



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
        if not self.output_folder:
            QMessageBox.warning(self, "Chưa có thư mục lưu", "Không tìm thấy thư mục lưu video.")
            return

        path = os.path.join(self.output_folder, f"video_{index}.mp4")
        if os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.warning(self, "Không tìm thấy video", f"Không tìm thấy file: {path}")



    def start_batch_generation(self):
        if not self.folder_path:
            QMessageBox.warning(self, "Thiếu thông tin", "Bạn cần chọn thư mục media trước.")
            return

        raw_text = self.text_input.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Thiếu văn bản", "Bạn cần nhập danh sách nội dung video.")
            return

        # Fetch the API key dynamically (use Google Gemini API with proxy retries)
        try:
            api_key_list = fetch_api_keys()  # Fetch a list of available API keys
            if not api_key_list:
                raise Exception("❌ Không có API keys hợp lệ.")
            api_key = api_key_list  # Assign the list directly, no need to fetch again
        except Exception as e:
            QMessageBox.warning(self, "Thiếu API Key", f"Không thể lấy API Key: {str(e)}")
            return

        self.text_list = [txt.strip() for txt in raw_text.split("==|==") if txt.strip()]
        total_jobs = len(self.text_list)

        if total_jobs == 0:
            QMessageBox.warning(self, "Không có nội dung", "Vui lòng nhập ít nhất một đoạn text.")
            return

        # Allow the user to choose the folder to save videos
        self.output_folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu video")
        if not self.output_folder:
            QMessageBox.warning(self, "Chưa chọn thư mục lưu", "Bạn cần chọn thư mục để lưu video.")
            return

        # Clear old logs before running a new batch
        self.log_output.clear()
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("🔄 Đang xử lý...")

        self.progress.setMaximum(total_jobs)
        self.progress.setValue(0)
        self.table.setRowCount(0)

        # Clean up previous temporary files in the output folder
        for f in os.listdir(self.output_folder):
            try:
                os.remove(os.path.join(self.output_folder, f))
            except:
                pass  # If file is locked or can't be removed, skip it

        self.jobs_completed = 0
        self.total_jobs = total_jobs

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS)
        futures = []

        # Get selected settings for CPU/GPU, Model, and Subtitle Toggle
        selected_cpu = self.cpu_selector.currentText()  # "CPU" or "GPU"
        if selected_cpu == "GPU" and torch.cuda.is_available():
            device = 0  # Use GPU if selected and available
        else:
            device = "cpu"  # Default to CPU

        selected_model = self.model_selector.currentText()  # "tiny", "base", "small", "medium", "large"
        subtitles_enabled = self.subtitle_enabled_selector.currentText() == "Có phụ đề"


        def update_progress_and_check(future):
            self.jobs_completed += 1
            if self.jobs_completed == self.total_jobs:
                self.generate_btn.setEnabled(True)
                self.generate_btn.setText("🚀 Tạo Video")

        # Run jobs for each text entry
        for idx, text in enumerate(self.text_list):
            output_filename = os.path.join(self.output_folder, f"video_{idx+1}.mp4")
            self.add_table_row(idx, text)
            future = executor.submit(self.run_video_job, text, self.folder_path, output_filename, api_key_list, idx, device, selected_model, subtitles_enabled)
            future.add_done_callback(update_progress_and_check)



    def run_video_job(self, text, folder_path, output_path, api_key_list, index, device, model_name, subtitles_enabled):
        def log(msg):
            self.safe_append_log(f"[Video #{index + 1}] {msg}")

        log("🔄 Bắt đầu xử lý")

        audio_file = f"temp_audio_{index}.mp3"
        sub_file = f"temp_sub_{index}.srt"
        temp_video = os.path.abspath(f"temp_video_{index}.mp4")


        voice_id = self.voice_selector.currentText()
        if not voice_id:
            voice_id = "achird"  # Default voice in case no voice is selected

        try:
            log(f"🎤 Đang tạo giọng với Voice ID: {voice_id}")

            # Cleanup temporary files before proceeding
            for f in [audio_file, sub_file, temp_video]:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                        log(f"🧹 Đã xóa file tạm: {f}")
                except Exception as cleanup_err:
                    log(f"⚠️ Không thể xoá file tạm {f}: {cleanup_err}")

            # Generate audio with retry
            audio_file = create_voice_with_retry(text, audio_file, api_key_list, voice_name=voice_id)
            log("📝 Tạo giọng và lưu file audio thành công")

            language_code = self.language_selector.currentData()

            if language_code:
                log(f"🗣️ Ngôn ngữ chọn: {language_code}")
            else:
                log("🗣️ Đang sử dụng chế độ Auto Detect")

            log("🧠 Đang dùng fast-whisper để tạo phụ đề...")
            trans_result = transcribe_audio(
                audio_path=audio_file,
                folder_path=self.output_folder,
                output_base=f"video_{index + 1}",
                language_code=language_code,
                model_name=model_name,  # Use the selected model
                device=device  # Use CPU/GPU
            )
            sub_file = trans_result["srt_path"]
            karaoke_json = trans_result["karaoke_path"]

            log("✨ Đang tạo file karaoke .ass từ fast-whisper...")
            ass_file = os.path.join(self.output_folder, f"video_{index + 1}.ass")
            position = self.subtitle_position_selector.currentText().lower()
            subtitle_mode = self.subtitle_mode.currentText()
            base_hex = self.subtitle_base_color_selector.currentData()
            highlight_hex = self.subtitle_highlight_color_selector.currentData()
            font_name = self.font_selector.currentText()
            font_size = self.subtitle_font_size_selector.currentText()

            background_music = self.music_selector.currentText()

            if subtitles_enabled:
                generate_karaoke_ass_from_srt_and_words(
                    sub_file,
                    karaoke_json,
                    ass_file,
                    font=font_name,
                    size=int(font_size),
                    position=position,
                    base_color="&H00" + base_hex,
                    highlight_color="&H00" + highlight_hex,
                    mode=subtitle_mode
                )
                log(f"🎉 Đã tạo file phụ đề .ass: {ass_file}")
            else:
                ass_file = None  # No subtitles if disabled

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


            crop_enabled = self.crop_checkbox.isChecked()
            log(f"✂️ Crop mode: {'ON' if crop_enabled else 'OFF'}")

            create_video_randomized_media(
                media_files=media_files,
                total_duration=duration,
                change_every=5,
                word_count=len(text.split()),
                output_file=temp_video,
                is_vertical=is_vertical,
                crop=crop_enabled
            )

            log("🎞️ Tạo video nền hoàn tất")

          
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

            log(f"⏳ Chờ file video sẵn sàng: {temp_video}")
            wait_for_file(temp_video)


            # Render final video with subtitles and background audio
            burn_sub_and_audio(
                video_path=temp_video,
                srt_path=ass_file,
                voice_path=audio_file,
                output_path=output_path,
                font_name=font_name,
                font_size=font_size,
                font_color="&H00" + base_hex,
                bg_music_path=music_path,
                bg_music_volume=music_volume
            )

            log("🎬 Video cuối cùng đã được render và lưu")
            self.safe_update_status(index, "✅ Hoàn thành")

        except Exception as e:
            log(f"❌ Lỗi: {e}")
            self.safe_update_status(index, f"❌ Lỗi , {e}")
            return

        # Xóa file tạm sau khi xong
        for f in [ass_file, karaoke_json]:
            safe_remove_file(f, log_func=log)
        for f in [audio_file, sub_file, temp_video]:
            safe_remove_file(f, log_func=log)

          
