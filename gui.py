import sys
import os
import random
import threading
import subprocess
import requests
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
                             QLabel, QTextEdit, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt
from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips
from pydub import AudioSegment
import concurrent.futures

MAX_THREADS = 2
TEMP_VIDEO = "temp.mp4"
SUB_FILE = "subtitles.srt"
AUDIO_FILE = "voice.mp3"
OUTPUT_FOLDER = "outputs"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def create_voice_with_elevenlabs(text, output_file, api_key, voice_id="EXAVITQu4vr4xnSDxMaL"):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        with open(output_file, "wb") as f:
            f.write(response.content)
    else:
        print(f"❌ Lỗi tạo voice: {response.status_code}")
        print(response.text)
        raise Exception("Lỗi ElevenLabs")

def split_text_to_words(text):
    return text.strip().split()

def format_time_ms(ms):
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(ms):03d}"

def create_srt_word_by_word(audio_path, text, output_file):
    words = split_text_to_words(text)
    audio = AudioSegment.from_file(audio_path)
    duration_ms = len(audio)
    duration_per_word = duration_ms // len(words)
    with open(output_file, "w", encoding="utf-8") as f:
        for i, word in enumerate(words):
            start = i * duration_per_word
            end = (i + 1) * duration_per_word
            f.write(f"{i + 1}\n")
            f.write(f"{format_time_ms(start)} --> {format_time_ms(end)}\n")
            f.write(f"{word}\n\n")

def create_video_randomized_media(media_files, total_duration, change_every, word_count, output_file):
    clips = []
    num_segments = max(1, word_count // change_every)
    duration_per_segment = total_duration / num_segments
    for _ in range(num_segments):
        file = random.choice(media_files)
        ext = os.path.splitext(file)[1].lower()
        try:
            if ext in [".jpg", ".png"]:
                clip = ImageClip(file, duration=duration_per_segment).resize(height=1920, width=1080)
            elif ext in [".mp4", ".mov"]:
                video = VideoFileClip(file)
                clip = video.subclip(0, min(duration_per_segment, video.duration)).resize(height=1920, width=1080)
            else:
                print(f"⚠️ Bỏ qua file không hỗ trợ: {file}")
                continue
            clips.append(clip)
        except Exception as e:
            print(f"⚠️ Lỗi khi xử lý file {file}: {e}")
            continue
    if clips:
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_file, fps=30)

def burn_sub_and_audio(video, srt, audio, output):
    command = [
        "ffmpeg", "-y",
        "-i", video,
        "-i", audio,
        "-filter_complex",
        f"[0:v]subtitles={srt}:force_style='Alignment=2,MarginV=40'[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        output
    ]
    subprocess.run(command)

class VideoGeneratorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 AI Video Generator with ElevenLabs")
        self.setGeometry(200, 200, 700, 500)

        self.folder_path = ""
        self.text_list = []

        self.layout = QVBoxLayout()
        self.select_folder_btn = QPushButton("📁 Chọn thư mục chứa ảnh/video nền")
        self.select_folder_btn.clicked.connect(self.select_folder)
        self.layout.addWidget(self.select_folder_btn)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("==|==\nText 1\n==|==\nText 2...")
        self.layout.addWidget(self.text_input)

        self.api_key_input = QTextEdit()
        self.api_key_input.setPlaceholderText("🔐 Nhập API Key ElevenLabs")
        self.api_key_input.setMaximumHeight(50)
        self.layout.addWidget(self.api_key_input)

        self.generate_btn = QPushButton("🚀 Tạo Video (đa luồng tối đa 2)")
        self.generate_btn.clicked.connect(self.start_batch_generation)
        self.layout.addWidget(self.generate_btn)

        self.progress = QProgressBar()
        self.layout.addWidget(self.progress)

        self.setLayout(self.layout)

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
        self.progress.setMaximum(total_jobs)
        self.progress.setValue(0)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS)
        futures = []

        for idx, text in enumerate(self.text_list):
            output_filename = os.path.join(OUTPUT_FOLDER, f"video_{idx+1}.mp4")
            futures.append(executor.submit(self.run_video_job, text, self.folder_path, output_filename, api_key, idx))

        def update_progress(f):
            self.progress.setValue(self.progress.value() + 1)

        for future in futures:
            future.add_done_callback(update_progress)

    def run_video_job(self, text, folder_path, output_path, api_key, index):
        try:
            create_voice_with_elevenlabs(text, AUDIO_FILE, api_key)
            create_srt_word_by_word(AUDIO_FILE, text, SUB_FILE)
            duration = AudioSegment.from_file(AUDIO_FILE).duration_seconds
            media_files = [
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if f.lower().endswith((".jpg", ".png", ".mp4", ".mov"))
            ]
            create_video_randomized_media(media_files, duration, change_every=5, word_count=len(split_text_to_words(text)), output_file=TEMP_VIDEO)
            burn_sub_and_audio(TEMP_VIDEO, SUB_FILE, AUDIO_FILE, output_path)
        except Exception as e:
            print(f"❌ Lỗi tại video {index+1}: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoGeneratorApp()
    window.show()
    sys.exit(app.exec_())