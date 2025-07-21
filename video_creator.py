import os
import random
import hashlib
import time
from moviepy.editor import VideoFileClip, AudioFileClip
from pydub import AudioSegment
import ffmpeg
import subprocess
from pathlib import Path

def has_audio_stream(video_path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return bool(result.stdout.strip())


def is_valid_video(path):
    try:
        clip = VideoFileClip(path)
        clip.close()
        return True
    except Exception:
        return False


def adjust_segment_timing(total_duration: float, target_segment_duration: float = 4.5, max_transition_duration: float = 1.2):
    rough_segments = max(1, int(total_duration // target_segment_duration))
    optimal_dur = None
    optimal_t = None
    for s in range(rough_segments, rough_segments + 3):
        t = min(max_transition_duration, total_duration / (3 * s))
        d = (total_duration + (s - 1) * t) / s
        if 3.8 <= d <= 5.2:
            optimal_dur = d
            optimal_t = t
            break
    return s, optimal_dur, optimal_t


def create_video_randomized_media(media_files, total_duration, change_every, word_count, output_file,
                                         is_vertical=True, crop=True, transition_effects=None):
    width, height = (1080, 1920) if is_vertical else (1920, 1080)

    num_segments, duration_per_segment, dur = adjust_segment_timing(total_duration, target_segment_duration=4.5, max_transition_duration=1.2)


    print(f"📊 Mỗi segment: {duration_per_segment:.2f}s | Hiệu ứng chuyển: {dur:.2f}s | Tổng khớp: {duration_per_segment * num_segments - dur * (num_segments - 1):.2f}s")


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
            input_ff = ffmpeg.input(src, loop=1, t=duration_per_segment) if ext in [".jpg", ".png"] else ffmpeg.input(src)

            if crop:
                input_ff = input_ff.filter('scale', width, height)
            else:
                input_ff = (
                    input_ff
                    .filter('scale',
                            f"if(gt(a,{width}/{height}),{width},-1)",
                            f"if(gt(a,{width}/{height}),-1,{height})")
                    .filter('pad', width, height, '(ow-iw)/2', '(oh-ih)/2')
                )

            (
                input_ff
                .output(str(out_path), t=duration_per_segment, vcodec='libx264', pix_fmt='yuv420p', r=30, loglevel='error')
                .overwrite_output()
                .run()
            )
            segment_paths.append(str(out_path))
        except Exception as e:
            print(f"❌ Lỗi xử lý {src}: {e}")
            continue

    if not segment_paths:
        raise Exception("❌ Không có segment nào được tạo!")

    # 🔄 Ghép bằng ffmpeg filter_complex + xfade
    print("🔄 Ghép segment kèm hiệu ứng chuyển cảnh...")

    filter_complex = ""
    inputs = ""
    maps = []
    last_v = ""
    last_a = ""
    offset = 0.0
    dur = min(0.7, duration_per_segment / 2)

    has_audio = []

    cmd = ["ffmpeg"]

    # Chuẩn bị input và kiểm tra audio
    for i, path in enumerate(segment_paths):
        cmd += ["-i", path]
        filter_complex += f"[{i}:v]format=yuv420p,scale={width}:{height},fps=30[v{i}];"
        
        if has_audio_stream(path):
            filter_complex += f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];"
            has_audio.append(True)
        else:
            has_audio.append(False)

    last_v = "v0"
    last_a = "a0" if has_audio[0] else None
    if transition_effects is None:
            transition_effects = [
                "fade",         # Làm mờ dần
                "fadeblack",    # Mờ thành đen
                "fadewhite",    # Mờ thành trắng
                "slideleft",    # Trượt sang trái
                "slideright",   # Trượt sang phải
                "slideup",      # Trượt lên trên
                "slidedown",    # Trượt xuống dưới
                "crossfade",    # Giao thoa mờ
                "circleopen",   # Mở tròn
                "circleclose",  # Đóng tròn
                "wipeleft",     # Vuốt sang trái
                "wiperight",    # Vuốt sang phải
                "wipeup",       # Vuốt lên
                "wipedown"      # Vuốt xuống
            ]

    print(f"📽 Số hiệu ứng chuyển cảnh: {len(transition_effects)} | Hiệu ứng mẫu: {transition_effects}")

    for i in range(1, len(segment_paths)):
        effect = random.choice(transition_effects)
        filter_complex += f"[{last_v}][v{i}]xfade=transition={effect}:duration={dur}:offset={offset:.2f}[v{i}_out];"
        last_v = f"v{i}_out"

        if has_audio[i] and last_a:
            filter_complex += f"[{last_a}][a{i}]acrossfade=d={dur}[a{i}_out];"
            last_a = f"a{i}_out"
        else:
            last_a = None

        offset += duration_per_segment - dur

    # Tạo và chạy lệnh ffmpeg
    
    cmd += sum([["-i", path] for path in segment_paths], [])

    cmd += [
    "-filter_complex", filter_complex,
    "-map", f"[{last_v}]"
    ]

    if last_a:
        cmd += ["-map", f"[{last_a}]"]

    cmd += [
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-shortest",
        "-y",
        output_file
    ]


    
    try:
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # In log chi tiết FFmpeg (dễ debug)
        print("📥 FFmpeg output:")
        print(result.stdout)

        for i in range(10):
            if os.path.exists(output_file) and os.path.getsize(output_file) > 1024:
                break
            print(f"⏳ Đợi FFmpeg hoàn tất ghi file... ({i+1}s)")
            time.sleep(1)

        if result.returncode != 0:
            print(f"❌ Lỗi khi ghép video. Exit code: {result.returncode}")
            raise Exception("FFmpeg failed. Xem log ở trên để biết chi tiết.")

        print(f"✅ Đã tạo video hoàn tất: {output_file}")

    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi ghép video: {e}")

    # Dọn temp
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
    font_name = font_name.replace("-", " ").replace("_", " ")
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
