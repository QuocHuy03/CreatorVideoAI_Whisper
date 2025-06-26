import os
import random
import subprocess
import hashlib
import time
from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips
from pydub import AudioSegment
from moviepy.video.fx.all import fadein, fadeout

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


def apply_random_effect(clip, width, height):
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


def percent_to_db(percent):
    """Chuyển % volume về decibel tương đối (dB giảm)."""
    percent = max(1, min(percent, 100))  # tránh chia 0
    return 40 * (1 - percent / 100)  # càng nhỏ càng giảm mạnh


def burn_sub_and_audio(video, srt, audio, output, font_name="Playbill", font_size="15", font_color="00FFFF", show_subtitle=True, bg_music_path=None, bg_music_volume=30):
    print("🎬 Bắt đầu render với phụ đề và âm thanh...")

    base_audio = AudioSegment.from_file(audio)
    temp_combined_audio = None

    if bg_music_path and os.path.exists(bg_music_path):
        try:
            bg_audio = AudioSegment.from_file(bg_music_path)

            # Lặp lại nhạc nền đủ dài
            times = int(len(base_audio) / len(bg_audio)) + 1
            bg_audio = (bg_audio * times)[:len(base_audio)]

            volume_db = percent_to_db(bg_music_volume)
            bg_audio = bg_audio - volume_db

            combined = base_audio.overlay(bg_audio)

            # Tạo file audio tạm
            hash_id = hashlib.md5(output.encode()).hexdigest()[:8]
            temp_combined_audio = f"combined_temp_audio_{hash_id}.mp3"
            combined.export(temp_combined_audio, format="mp3")

            for _ in range(20):
                if os.path.exists(temp_combined_audio):
                    break
                time.sleep(0.1)
            else:
                raise FileNotFoundError(f"Không tìm thấy file {temp_combined_audio}")

            audio = temp_combined_audio
            print(f"🔊 Nhạc nền: {bg_music_path} | Âm lượng: {bg_music_volume}% ({volume_db:.2f} dB)")

        except Exception as e:
            print(f"❌ Lỗi xử lý nhạc nền: {e}")
            return

    try:
        # Cấu hình filter phụ đề nếu không ẩn
        filter_complex = None
        if show_subtitle:
            filter_complex = (
                f"[0:v]subtitles={srt}:force_style='FontName={font_name},FontSize={font_size},PrimaryColour=&H00{font_color}&,"
                f"OutlineColour=&H000000&,Outline=1'[v]"
            )
            print(f"🎨 Hiển thị phụ đề: font={font_name}, size={font_size}, màu=#{font_color}")
        else:
            print("🚫 Không hiển thị phụ đề")

        command = [
            "ffmpeg", "-y",
            "-i", video,
            "-i", audio,
        ]

        if show_subtitle:
            command += [
                "-filter_complex", filter_complex,
                "-map", "[v]",
            ]
        else:
            command += ["-map", "0:v"]

        command += [
            "-map", "1:a",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            output
        ]


        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✅ Xuất video hoàn tất: {output}")

    except Exception as e:
        print(f"❌ Lỗi render video: {e}")

    if temp_combined_audio and os.path.exists(temp_combined_audio):
        try:
            os.remove(temp_combined_audio)
            print(f"🧹 Xoá file tạm: {temp_combined_audio}")
        except Exception as e:
            print(f"⚠️ Không thể xoá file tạm: {e}")
