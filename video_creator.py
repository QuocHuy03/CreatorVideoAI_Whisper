import os
import random
import subprocess
from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips

def is_valid_video(path):
    try:
        clip = VideoFileClip(path)
        clip.close()
        return True
    except Exception:
        return False

def create_video_randomized_media(media_files, total_duration, change_every, word_count, output_file, is_vertical=True):
    clips = []
    num_segments = max(1, word_count // change_every)
    duration_per_segment = total_duration / num_segments
    retries = 5

    # Chọn kích thước video theo chiều
    width, height = (1080, 1920) if is_vertical else (1920, 1080)

    for _ in range(num_segments):
        valid_clip = None
        attempt = 0

        while attempt < retries and not valid_clip:
            file = random.choice(media_files)
            ext = os.path.splitext(file)[1].lower()

            try:
                if ext in [".jpg", ".png"]:
                    valid_clip = ImageClip(file, duration=duration_per_segment).resize(width=width, height=height)
                elif ext in [".mp4", ".mov"] and is_valid_video(file):
                    video = VideoFileClip(file)
                    valid_clip = video.subclip(0, min(duration_per_segment, video.duration)).resize(width=width, height=height)
            except Exception as e:
                print(f"⚠️ Lỗi khi dùng {file}: {e}")
                attempt += 1

        if valid_clip:
            clips.append(valid_clip)
        else:
            print("❌ Không tìm được clip hợp lệ trong giới hạn thử lại.")

    if clips:
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_file, fps=30, logger=None)
    else:
        raise Exception("❌ Không có clip hợp lệ nào để tạo video.")

def burn_sub_and_audio(video, srt, audio, output, font_name="Playbill"):
    command = [
        "ffmpeg", "-y",
        "-i", video,
        "-i", audio,
        "-filter_complex",
        f"[0:v]subtitles={srt}:force_style='FontName={font_name},Alignment=2,MarginV=40'[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        output
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
