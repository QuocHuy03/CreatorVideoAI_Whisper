import os
import random
import hashlib
import re
import time
from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip
from pydub import AudioSegment
import ffmpeg
from moviepy.video.fx.all import fadein, fadeout
from pathlib import Path

def is_valid_video(path):
    try:
        clip = VideoFileClip(path)
        clip.close()
        return True
    except Exception:
        return False


def resize_and_crop_center_fixed(clip, target_width, target_height):
    """Resize + crop để vừa khít khung hình đích, giữ nguyên tỉ lệ, crop giữa."""

    # Tính aspect ratio đích và gốc
    target_ratio = target_width / target_height
    clip_ratio = clip.w / clip.h

    # Resize sao cho *một chiều >= khung*, chiều kia có thể dư để crop
    if clip_ratio > target_ratio:
        # Quá ngang → resize theo height
        new_height = target_height
        new_width = int(new_height * clip_ratio)
    else:
        # Quá dọc → resize theo width
        new_width = target_width
        new_height = int(new_width / clip_ratio)

    clip = clip.resize(newsize=(new_width, new_height))

    # Crop ở giữa
    x1 = (new_width - target_width) // 2
    y1 = (new_height - target_height) // 2
    x2 = x1 + target_width
    y2 = y1 + target_height

    clip = clip.crop(x1=x1, y1=y1, x2=x2, y2=y2)

    print(f"✅ Resize+Crop: input {clip.w}x{clip.h} → output {target_width}x{target_height}")
    return clip


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
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    num_segments = max(1, word_count // change_every)
    duration_per_segment = total_duration / num_segments
    hash_id = hashlib.md5(output_file.encode()).hexdigest()[:8]
    temp_dir = Path(f"temp_ffmpeg_{hash_id}").resolve()
    temp_dir.mkdir(exist_ok=True)

    segment_paths = []

    print(f"📐 Video size: {width}x{height}, segments: {num_segments}, mỗi đoạn: {duration_per_segment:.2f}s")

    for i in range(num_segments):
        src = random.choice(media_files)
        ext = Path(src).suffix.lower()
        out_path = temp_dir / f"seg_{i:03}.mp4"

        try:
            if ext in [".jpg", ".png"]:
                (
                    ffmpeg
                    .input(src, loop=1, t=duration_per_segment)
                    .filter('scale', width, height)
                    .output(str(out_path), vcodec='libx264', pix_fmt='yuv420p', r=30, loglevel='error')
                    .overwrite_output()
                    .run()
                )
            elif ext in [".mp4", ".mov"] and is_valid_video(src):
                (
                    ffmpeg
                    .input(src)
                    .filter('scale', width, height)
                    .output(str(out_path), t=duration_per_segment, vcodec='libx264', pix_fmt='yuv420p', r=30, loglevel='error')
                    .overwrite_output()
                    .run()
                )
            else:
                print(f"⚠️ Bỏ qua file không hợp lệ: {src}")
                continue

            # Dùng đường dẫn tuyệt đối, posix-style để tránh lỗi
            segment_paths.append(f"file '{out_path.as_posix()}'")

        except Exception as e:
            print(f"❌ Lỗi xử lý {src}: {e}")

    if not segment_paths:
        raise Exception("❌ Không có segment nào được tạo!")

    # Tạo concat list
    concat_list_path = temp_dir / "concat_list.txt"
    with open(concat_list_path, "w", encoding="utf-8") as f:
        f.write("\n".join(segment_paths))

    print("🔄 Đang ghép các đoạn lại...")

    try:
        (
            ffmpeg
            .input(str(concat_list_path), format='concat', safe=0)
            .output(output_file, vcodec='libx264', acodec='aac', pix_fmt='yuv420p', r=30, loglevel='error')
            .overwrite_output()
            .run()
        )
        print(f"✅ Đã tạo xong video nền: {output_file}")
    except ffmpeg.Error as e:
        print(f"❌ Lỗi concat ffmpeg: {e.stderr.decode() if e.stderr else str(e)}")
        raise e
    finally:
        # Cleanup an toàn
        for f in temp_dir.glob("*"):
            try: f.unlink()
            except: pass
        try: temp_dir.rmdir()
        except: pass


def burn_sub_and_audio(video_path, srt_path, voice_path, output_path,
                       font_name=None, font_size="14", font_color="#FFFFFF",
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

    # Kiểm tra font
    font_path = os.path.join(fonts_dir, font_name + ".ttf")
    if not os.path.exists(font_path):
        print(f"❌ Font '{font_name}' không tìm thấy trong thư mục fonts. Sử dụng font mặc định.")
        

    # Filter subtitle
    srt_safe = srt_path.replace("\\", "/")
    subtitle_filter = (
        f"subtitles='{srt_safe}':fontsdir='{fonts_dir}':"
        f"force_style='FontName={font_name},FontSize={font_size},PrimaryColour={ff_color},Alignment=2,MarginV=9'"
    )
    
    # Subtitle filter
    vf_filters = []
    ass_path = srt_path.replace(".srt", ".ass").replace("\\", "/")

    if os.path.exists(ass_path):
        ass_safe = ass_path.replace(":", "\\\\:").replace("'", "\\'")
        vf_filters.append(f"ass={ass_safe}:fontsdir=fonts")
    else:
        vf_filters.append(subtitle_filter)

    print("----------------------", vf_filters)
    # Thử lại tối đa 3 lần nếu lỗi
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"🚀 Render attempt {attempt}...")
            input_video = ffmpeg.input(video_path, t=voice_duration)
            input_audio = ffmpeg.input(audio_path)

            ffmpeg.output(
                    input_video,
                    input_audio,
                    output_path,
                    vf=",".join(vf_filters),
                    vcodec="libx264",
                    acodec="aac",
                    preset="slow",
                    pix_fmt="yuv420p",
                    t=voice_duration,
                    video_bitrate="5000k"
            ).overwrite_output().run()
       

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
