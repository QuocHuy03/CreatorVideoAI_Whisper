import os
import subprocess
from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips
from gtts import gTTS
from pydub import AudioSegment

WORDS_PER_SUB = 4  # mỗi sub có 3–4 từ
DURATION_PER_IMAGE = 3
TEMP_VIDEO = "temp.mp4"
SUB_FILE = "subtitles.srt"
AUDIO_FILE = "voice.mp3"
FINAL_VIDEO = "final_output.mp4"

# Tách đoạn văn thành sub ngắn 3–4 từ
def split_text_to_subs(text, words_per_sub=4):
    words = text.strip().split()
    return [" ".join(words[i:i + words_per_sub]) for i in range(0, len(words), words_per_sub)]

# Sinh file .srt

def create_srt_from_voice(audio_path, subs, output_file):
    audio = AudioSegment.from_file(audio_path)
    duration_ms = len(audio)
    duration_per_sub = duration_ms // len(subs)

    with open(output_file, "w", encoding="utf-8") as f:
        for i, line in enumerate(subs):
            start = i * duration_per_sub
            end = (i + 1) * duration_per_sub
            f.write(f"{i + 1}\n")
            f.write(f"{format_time_ms(start)} --> {format_time_ms(end)}\n")
            f.write(f"{line}\n\n")

def format_time_ms(ms):
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(ms):03d}"

# Tạo video từ từng ảnh/video tương ứng với từng sub
def create_video(media_files, duration, output_file):
    clips = []
    for file in media_files:
        ext = os.path.splitext(file)[1].lower()
        if ext in [".jpg", ".png"]:
            clip = ImageClip(file, duration=duration).resize(height=720)
        elif ext in [".mp4", ".mov"]:
            clip = VideoFileClip(file).subclip(0, duration).resize(height=720)
        else:
            print(f"⚠️ Bỏ qua file không hỗ trợ: {file}")
            continue
        clips.append(clip)
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(output_file, fps=24)

# Tạo file audio từ toàn bộ sub
def create_voice(text, output_file):
    tts = gTTS(text, lang="vi")
    tts.save(output_file)

# Gắn phụ đề và audio vào video, đẩy sub lên trên
def burn_sub_and_audio(video, srt, audio, output):
    command = [
        "ffmpeg", "-y",
        "-i", video,
        "-i", audio,
        "-filter_complex",
        f"[0:v]subtitles={srt}:force_style='Alignment=2, MarginV=40'[v]",
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
    folder = input("📁 Nhập đường dẫn thư mục ảnh/video: ").strip('"')
    text = input("📝 Nhập đoạn sub dài: ").strip()

    media = [
        os.path.join(folder, f)
        for f in sorted(os.listdir(folder))
        if f.lower().endswith((".jpg", ".png", ".mp4", ".mov"))
    ]

    if not media:
        print("❌ Không tìm thấy ảnh/video!")
        exit()

    subs = split_text_to_subs(text, WORDS_PER_SUB)

    if len(subs) > len(media):
        print(f"⚠️ Số ảnh/video không đủ. Cần ít nhất {len(subs)} media để hiển thị từng đoạn.")
        subs = subs[:len(media)]
    else:
        media = media[:len(subs)]

    print(f"📸 Tổng media dùng: {len(media)} — 📜 Tổng sub: {len(subs)}")

    create_voice(text, AUDIO_FILE)
    create_srt_from_voice(AUDIO_FILE, subs, SUB_FILE)
    create_video(media, DURATION_PER_IMAGE, TEMP_VIDEO)
    burn_sub_and_audio(TEMP_VIDEO, SUB_FILE, AUDIO_FILE, FINAL_VIDEO)

    print(f"🎉 Video đã tạo thành công: {FINAL_VIDEO}")
