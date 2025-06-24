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

def resize_and_crop_center(clip, target_width, target_height):
    # Resize theo chiều phù hợp
    clip = clip.resize(width=target_width)
    if clip.h < target_height:
        clip = clip.resize(height=target_height)

    # In log kích thước sau resize
    print(f"🔧 Đã resize: {clip.filename if hasattr(clip, 'filename') else 'Image'} → size sau: {clip.w}x{clip.h}")

    # Crop phần giữa
    x_center = clip.w // 2
    y_center = clip.h // 2
    cropped = clip.crop(
        x_center - target_width // 2,
        y_center - target_height // 2,
        x_center + target_width // 2,
        y_center + target_height // 2
    )
    print(f"✂️ Crop giữa: giữ lại vùng {target_width}x{target_height}")
    return cropped

def create_video_randomized_media(media_files, total_duration, change_every, word_count, output_file, is_vertical=True):
    clips = []
    num_segments = max(1, word_count // change_every)
    duration_per_segment = total_duration / num_segments
    retries = 5

    # Kích thước theo chiều video
    width, height = (1080, 1920) if is_vertical else (1920, 1080)

    print(f"📐 Tạo video với chiều {'Dọc (9:16)' if is_vertical else 'Ngang (16:9)'} → kích thước: {width}x{height}")
    print(f"📋 Tổng segment: {num_segments} | Mỗi đoạn dài: {duration_per_segment:.2f}s")

    for seg in range(num_segments):
        valid_clip = None
        attempt = 0

        while attempt < retries and not valid_clip:
            file = random.choice(media_files)
            ext = os.path.splitext(file)[1].lower()

            try:
                if ext in [".jpg", ".png"]:
                    print(f"🖼️ Đang xử lý ảnh: {file}")
                    img = ImageClip(file, duration=duration_per_segment)
                    valid_clip = resize_and_crop_center(img, width, height)

                elif ext in [".mp4", ".mov"] and is_valid_video(file):
                    print(f"🎞️ Đang xử lý video: {file}")
                    video = VideoFileClip(file)
                    subclip = video.subclip(0, min(duration_per_segment, video.duration))
                    subclip.filename = file  # để in log
                    valid_clip = resize_and_crop_center(subclip, width, height)

            except Exception as e:
                print(f"⚠️ Lỗi khi dùng {file}: {e}")
                attempt += 1

        if valid_clip:
            print(f"✅ Segment {seg+1}/{num_segments} đã sẵn sàng.\n")
            clips.append(valid_clip)
        else:
            print(f"❌ Segment {seg+1} thất bại sau {retries} lần thử.\n")

    if clips:
        print("🔄 Ghép tất cả clip thành video cuối...")
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_file, fps=30, logger=None)
        print(f"✅ Xuất video hoàn tất: {output_file}")
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
