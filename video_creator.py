import os
import random
import hashlib
import time
from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip
from pydub import AudioSegment
import ffmpeg
from pathlib import Path
from moviepy.video.fx.all import fadein, fadeout
from PIL import Image


def is_valid_video(path):
    try:
        clip = VideoFileClip(path)
        clip.close()
        return True
    except Exception:
        return False


def resize_and_crop_center(clip, target_width, target_height):
    """Ensure the clip is resized to the target width and height while preserving aspect ratio."""
    # Resize while maintaining aspect ratio
    clip = clip.resize(width=target_width) if clip.w > target_width else clip
    clip = clip.resize(height=target_height) if clip.h > target_height else clip

    # Log the new size
    print(f"🔧 Đã resize: {clip.filename if hasattr(clip, 'filename') else 'Image'} → size sau: {clip.w}x{clip.h}")

    # If after resizing, clip dimensions are still smaller, apply padding instead of cropping
    if clip.w < target_width or clip.h < target_height:
        print(f"⚠️ Không thể crop đúng kích thước {target_width}x{target_height}. Sử dụng padding.")
        clip = clip.resize(width=target_width, height=target_height)

    # Crop the center of the clip to get the desired dimensions
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


def apply_random_effect(clip, width, height):
    """Apply random effects such as fade, zoom, and slide."""
    effects = ["fade", "zoom", "slide_left", "slide_right", "slide_up", "slide_down", "none"]
    effect = random.choice(effects)

    duration = min(0.7, clip.duration / 2)

    if effect == "fade":
        return fadein(fadeout(clip, duration), duration), effect

    elif effect == "zoom":
        return clip.resize(lambda t: 1 + 0.03 * t), effect

    elif effect.startswith("slide"):
        start_pos = {
            "slide_left": lambda: (-width, 0),
            "slide_right": lambda: (width, 0),
            "slide_up": lambda: (0, -height),
            "slide_down": lambda: (0, height)
        }.get(effect, lambda: (0, 0))()

        animated_clip = clip.set_position(lambda t: (
            int(start_pos[0] * (1 - t / duration)) if abs(start_pos[0]) > 0 else "center",
            int(start_pos[1] * (1 - t / duration)) if abs(start_pos[1]) > 0 else "center"
        ))
        return animated_clip, effect

    return clip, effect  # "none"


def create_video_randomized_media(media_files, total_duration, change_every, word_count, output_file, is_vertical=True, transition_effect="fade"):
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
                    img = ImageClip(file, duration=5)  # Chỉnh lại thời gian cho mỗi ảnh
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
            valid_clip, effect = apply_random_effect(valid_clip, width, height)
            print(f"✨ Segment {seg+1}: hiệu ứng {effect}")

        else:
            print(f"❌ Segment {seg+1} thất bại sau {retries} lần thử.\n")

    if clips:
        print("🔄 Ghép tất cả clip thành video cuối...")
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_file, fps=30, logger=None)
        print(f"✅ Xuất video hoàn tất: {output_file}")
    else:
        raise Exception("❌ Không có clip hợp lệ nào để tạo video.")


def burn_sub_and_audio(video_path, srt_path, voice_path, output_path,
                       font_name="Arial", font_size="14", font_color="#FFFFFF",
                       bg_music_path=None, bg_music_volume=30):
    print("🎬 Bắt đầu render với phụ đề và âm thanh...")

    voice_duration = AudioFileClip(voice_path).duration
    temp_combined_audio = None

    # Xử lý âm thanh
    base_audio = AudioSegment.from_file(voice_path)

    if bg_music_path and os.path.exists(bg_music_path):
        bg_audio = AudioSegment.from_file(bg_music_path)
        times = int(len(base_audio) / len(bg_audio)) + 1
        bg_audio = (bg_audio * times)[:len(base_audio)]
        volume_db = percent_to_db(bg_music_volume)
        bg_audio = bg_audio - volume_db
        combined = base_audio.overlay(bg_audio)

        # Tạo file âm thanh tạm thời kết hợp giữa voice và nhạc nền
        hash_id = hashlib.md5(output_path.encode()).hexdigest()[:8]
        temp_combined_audio = f"combined_temp_audio_{hash_id}.mp3"
        combined.export(temp_combined_audio, format="mp3")

        for _ in range(20):
            if os.path.exists(temp_combined_audio):
                break
            time.sleep(0.1)

        audio_path = temp_combined_audio
        print(f"🔊 Nhạc nền đã thêm từ: {bg_music_path} - Âm lượng: {bg_music_volume}%")
    else:
        # Nếu không có nhạc nền, chỉ sử dụng voice
        audio_path = voice_path
        print("🎵 Không sử dụng nhạc nền, chỉ dùng âm thanh voice.")

    # Convert màu sang định dạng ASS
    ff_color = f"&H{font_color[5:7]}{font_color[3:5]}{font_color[1:3]}&"
    fonts_dir = "fonts"

    # Subtitle filter
    srt_safe = srt_path.replace("\\", "/")
    subtitle_filter = ""
    ass_path = srt_path.replace(".srt", ".ass").replace("\\", "/")

    if os.path.exists(ass_path):
        ass_safe = ass_path.replace(":", "\\\\:").replace("'", "\\'")
        subtitle_filter = f"ass={ass_safe}"
    else:
        subtitle_filter = (
            f"subtitles='{srt_safe}':fontsdir='{fonts_dir}':"
            f"force_style='FontName={font_name},FontSize={font_size},PrimaryColour={ff_color},Alignment=2,MarginV=9'"
        )

    # Thử lại tối đa 3 lần nếu lỗi
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"🚀 Render attempt {attempt}...")
            input_video = ffmpeg.input(video_path, t=voice_duration)
            input_audio = ffmpeg.input(audio_path)

            (
                ffmpeg
                .output(
                    input_video,
                    input_audio,
                    output_path,
                    vf=subtitle_filter,
                    vcodec="libx264",
                    acodec="aac",
                    preset="ultrafast",
                    pix_fmt="yuv420p",
                )
                .overwrite_output()
                .run()
            )

            print(f"✅ Xuất video hoàn tất: {output_path}")
            break  # ✅ Thành công, thoát khỏi vòng lặp

        except ffmpeg.Error as e:
            print(f"❌ Lỗi render (lần {attempt}):")
            print(e.stderr.decode() if e.stderr else str(e))

            if attempt < max_retries:
                print("🔁 Đợi 1.5s rồi thử lại...")
                time.sleep(1.5)
            else:
                print("❌ Render thất bại sau 3 lần thử.")
                raise e

    # Xóa file âm thanh tạm nếu có
    if temp_combined_audio and os.path.exists(temp_combined_audio):
        os.remove(temp_combined_audio)
        print(f"🧹 Đã xoá file tạm: {temp_combined_audio}")


def percent_to_db(percent):
    """Chuyển % volume về decibel tương đối (dB giảm)."""
    percent = max(1, min(percent, 100))  # tránh chia 0
    return 40 * (1 - percent / 100)  # càng nhỏ càng giảm mạnh


