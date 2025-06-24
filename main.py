import os
import random
import subprocess
from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips
from pydub import AudioSegment
import requests

# === CẤU HÌNH ===
DURATION_PER_IMAGE = 3
TEMP_VIDEO = "temp.mp4"
SUB_FILE = "subtitles.srt"
AUDIO_FILE = "voice.mp3"
FINAL_VIDEO = "final_output.mp4"

# === VOICE BẰNG API ELEVENLABS ===
def create_voice_with_elevenlabs(text, output_file, api_key, voice_id="EXAVITQu4vr4xnSDxMaL"):  # Rachel
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
        print(f"✅ Đã lưu voice vào {output_file}")
    else:
        print(f"❌ Lỗi tạo voice: {response.status_code}")
        print(response.text)
        exit()

# === TÁCH VĂN BẢN ===
def split_text_to_words(text):
    return text.strip().split()

# === TẠO PHỤ ĐỀ TỪNG TỪ ===
def format_time_ms(ms):
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(ms):03d}"

def create_srt_word_by_word(audio_path, text, output_file):
    words = text.strip().split()
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

# === TẠO VIDEO TỪ ẢNH HOẶC VIDEO NỀN ===
def create_video_randomized_media(media_files, total_duration, change_every=5, word_count=0, output_file=TEMP_VIDEO):
    import random
    clips = []

    num_segments = max(1, word_count // change_every)
    duration_per_segment = total_duration / num_segments

    for _ in range(num_segments):
        file = random.choice(media_files)
        ext = os.path.splitext(file)[1].lower()
        if ext in [".jpg", ".png"]:
            clip = ImageClip(file, duration=duration_per_segment).resize(height=1920, width=1080)
        elif ext in [".mp4", ".mov"]:
            clip = VideoFileClip(file).subclip(0, duration_per_segment).resize(height=1920, width=1080)
        else:
            print(f"⚠️ Bỏ qua file không hỗ trợ: {file}")
            continue
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(output_file, fps=30)


# === GHÉP VOICE + SUB VÀO VIDEO ===
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

# === MAIN ===
if __name__ == "__main__":
    print("🎙️ TẠO VIDEO SUB NHẢY TỪNG TỪ VỚI ELEVENLABS")
    folder = input("📁 Nhập đường dẫn thư mục ảnh/video nền: ").strip('"')
    text = input("📝 Nhập nội dung sub (text sẽ được lồng voice): ").strip()
    api_key = input("🔐 Nhập ElevenLabs API Key: ").strip()

    words = split_text_to_words(text)

    all_media = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith((".jpg", ".png", ".mp4", ".mov"))
    ]

    if not all_media:
        print("❌ Không tìm thấy ảnh/video!")
        exit()

    print("🎤 Tạo voice bằng ElevenLabs...")
    create_voice_with_elevenlabs(text, AUDIO_FILE, api_key)

    print("📝 Tạo phụ đề theo từng từ...")
    create_srt_word_by_word(AUDIO_FILE, text, SUB_FILE)

    audio_duration = AudioSegment.from_file(AUDIO_FILE).duration_seconds
    media = random.choices(all_media, k=1)  # Dùng 1 ảnh/video nền

    print("🎬 Tạo video nền...")
    create_video_randomized_media(all_media, audio_duration, change_every=5, word_count=len(words), output_file=TEMP_VIDEO)

    print("🔥 Ghép sub và audio vào video...")
    burn_sub_and_audio(TEMP_VIDEO, SUB_FILE, AUDIO_FILE, FINAL_VIDEO)

    print(f"✅ Đã tạo video hoàn chỉnh: {FINAL_VIDEO}")
