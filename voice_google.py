import os
import json
import random
import requests
from faster_whisper import WhisperModel
import base64
import ffmpeg
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from pathlib import Path


def get_proxy_list():
    try:
        res = requests.get("http://62.171.131.164:5000/api/get_proxies", timeout=5)
        if res.status_code == 200:
            proxy_list = res.json().get("proxies", [])
            if proxy_list:
                print(f"✅ Lấy được {len(proxy_list)} proxy.")
                return proxy_list
        print("⚠️ Danh sách proxy rỗng hoặc không lấy được.")
    except Exception as e:
        print(f"❌ Lỗi khi lấy proxy: {e}")
    return []


def format_proxy(raw_proxy):
    parts = raw_proxy.strip().split(":")
    if len(parts) == 4:
        ip, port, user, pwd = parts
        return {
            "http": f"http://{user}:{pwd}@{ip}:{port}",
            "https": f"http://{user}:{pwd}@{ip}:{port}"
        }
    elif len(parts) == 2:
        ip, port = parts
        return {
            "http": f"http://{ip}:{port}",
            "https": f"http://{ip}:{port}"
        }
    else:
        raise ValueError(f"❌ Proxy không đúng định dạng: {raw_proxy}")


def send_with_proxy_retry(method, url, headers=None, json_data=None, files_path=None, data=None, max_retries=5):
    proxy_list = get_proxy_list()
    random.shuffle(proxy_list)

    for attempt, raw_proxy in enumerate(proxy_list[:max_retries], 1):
        try:
            proxy = format_proxy(raw_proxy)
            print(f"🔁 [Thử {attempt}] Đang thử với proxy: {raw_proxy}")

            if files_path:
                file_key, file_path, mime = files_path
                with open(file_path, "rb") as f:
                    files = {file_key: (os.path.basename(file_path), f, mime)}
                    res = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=json_data,
                        files=files,
                        data=data,
                        proxies=proxy,
                        timeout=15
                    )
            else:
                res = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    data=data,
                    proxies=proxy,
                    timeout=15
                )

            if res.status_code == 200:
                return res
            else:
                print(f"⚠️ Lỗi HTTP {res.status_code} - thử tiếp...")
                print(res.text[:500])
        except Exception as e:
            print(f"❌ Proxy lỗi ({raw_proxy}): {e}")
            continue

    raise Exception("❌ Tất cả proxy đều thất bại!")


def fetch_api_keys():
    """Fetch the list of available Gemini API keys."""
    url = "http://62.171.131.164:5000/api/get_gemini_keys"
    response = requests.get(url)

    if response.status_code == 200:
        keys_data = response.json()
        return keys_data.get("keys", [])
    else:
        print(f"❌ Error fetching API keys: {response.status_code}")
        return []


def create_voice_with_retry(text, output_file_pcm, api_key_list, voice_name="achird", max_workers=5):
    """
    ✅ Tạo voice sử dụng nhiều key và proxy cùng lúc (song song)
    ✅ Dừng lại khi 1 key thành công
    """
    proxy_list = get_proxy_list()
    if not proxy_list:
        proxy_list = [None]

    success_event = threading.Event()
    result_holder = {}
    lock = threading.Lock()

    def task(api_key, proxy_str, thread_id):
        if success_event.is_set():
            return

        try:
            proxy_dict = format_proxy(proxy_str) if proxy_str else None
            print(f"[{thread_id}] 🧪 Thử key: {api_key[:10]}... với proxy: {proxy_str}")

            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"
            data = {
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": voice_name
                            }
                        }
                    }
                },
                "model": "gemini-2.5-flash-preview-tts",
            }

            response = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=data,
                proxies=proxy_dict,
                timeout=60
            )

            if response.status_code != 200:
                print(f"❌ [{thread_id}] Lỗi API: {response.status_code}")
                return

            if success_event.is_set():
                return

            success_event.set()

            audio_data = response.json()['candidates'][0]['content']['parts'][0]['inlineData']['data']
            decoded_audio = base64.b64decode(audio_data)

            unique_id = random.randint(1000, 9999)
            temp_pcm = output_file_pcm.replace(".pcm", f"_{unique_id}.pcm")
            with open(temp_pcm, "wb") as f:
                f.write(decoded_audio)

            base_name, _ = os.path.splitext(temp_pcm)
            timestamp = time.strftime("%Y%m%d%H%M%S")
            mp3_file = f"{base_name}_{timestamp}.mp3"

            ffmpeg.input(temp_pcm, f='s16le', ar='24000', ac='1') \
                .output(mp3_file, **{'y': None}) \
                .run(overwrite_output=True, quiet=True)

            os.remove(temp_pcm)
            print(f"🧹 Đã xóa file PCM tạm: {temp_pcm}")
            print(f"✅ Voice generated successfully. Saved as {mp3_file}")

            with lock:
                result_holder["result"] = mp3_file

        except Exception as e:
            print(f"❌ [{thread_id}] Key {api_key[:10]} lỗi: {e}")

    # Start thread pool
    tasks = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        thread_id = 0
        for proxy_str in proxy_list:
            for api_key in api_key_list:
                thread_id += 1
                tasks.append(executor.submit(task, api_key, proxy_str, thread_id))

        for future in as_completed(tasks):
            if success_event.is_set():
                break

    if "result" in result_holder:
        return result_holder["result"]
    else:
        raise Exception("🛑 Không có key nào khả dụng để tạo voice.")


def split_text_smart(segment, max_words=6):
    """Tách đoạn thành nhiều phần nhỏ theo dấu câu và số từ."""
    text = segment.text.strip()
    # Ưu tiên tách theo dấu phẩy, chấm, hoặc xuống dòng
    split_points = re.split(r'([,.!?;:])', text)
    
    # Gộp lại thành các câu đầy đủ
    phrases = []
    phrase = ""
    for part in split_points:
        phrase += part
        if part in [",", ".", "!", "?", ";", ":"]:
            phrases.append(phrase.strip())
            phrase = ""
    if phrase:
        phrases.append(phrase.strip())

    # Nếu các câu nhỏ > max_words, tiếp tục tách theo từ
    final_segments = []
    for phrase in phrases:
        words = phrase.split()
        if len(words) <= max_words:
            final_segments.append(phrase)
        else:
            # Tách tiếp theo số từ
            for i in range(0, len(words), max_words):
                final_segments.append(" ".join(words[i:i + max_words]))
    return final_segments


def split_text_and_timestamps(segment, max_words=6):
    """Tách segment thành nhiều phần nhỏ theo dấu câu và max_words, tính thời gian chính xác."""
    parts = split_text_smart(segment, max_words)
    total_duration = segment.end - segment.start

    # Tổng số từ thực tế sau khi chia
    total_words = sum(len(part.split()) for part in parts)
    if total_words == 0:
        return [(segment.start, segment.end, segment.text.strip())]

    # Thời gian trên mỗi từ
    duration_per_word = total_duration / total_words

    # Tính thời gian theo số từ của từng đoạn
    timestamps = []
    current_start = segment.start

    for part in parts:
        word_count = len(part.split())
        part_duration = duration_per_word * word_count
        current_end = current_start + part_duration
        timestamps.append((round(current_start, 3), round(current_end, 3), part))
        current_start = current_end

    return timestamps


def transcribe_audio(audio_path, folder_path, output_base="output", language_code=None, model_name="small", device="cpu"):
    """Transcribe audio to text using fast-whisper and generate subtitle files."""

    output_dir = folder_path
    os.makedirs(output_dir, exist_ok=True)
    model = WhisperModel(model_name, device=device)  # Use dynamic model size and device

    print(f"🧠 Transcribing audio file: {audio_path}")
    segments_gen, info = model.transcribe(audio_path, language=language_code, word_timestamps=True)
    segments = list(segments_gen)  # Convert the generator to a list

    if not segments:
        print("❌ No transcriptions available.")
        return {}

    srt_path = os.path.join(output_dir, f"{output_base}.srt")
    json_path = os.path.join(output_dir, f"{output_base}.json")

    # Write the SRT file
    with open(srt_path, "w", encoding="utf-8") as srt_file:
        idx = 1
        for segment in segments:
            split_parts = split_text_and_timestamps(segment, max_words=5)
            for start, end, text in split_parts:
                srt_file.write(f"{idx}\n")
                srt_file.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
                srt_file.write(f"{text}\n\n")
                idx += 1

    # Save karaoke JSON
    words_data = []
    for segment in segments:
        if hasattr(segment, "words") and segment.words:
            for word in segment.words:
                words_data.append({
                    "start": word.start,
                    "end": word.end,
                    "text": word.word,
                    "type": "word"
                })
        else:
            split_parts = split_text_and_timestamps(segment, max_words=5)
            for start, end, text in split_parts:
                words_data.append({
                    "start": start,
                    "end": end,
                    "text": text,
                    "type": "segment"
                })

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(words_data, json_file, ensure_ascii=False, indent=2)

    print(f"✅ Transcription completed. Files saved to {srt_path} and {json_path}")
    return {
        "srt_path": srt_path,
        "karaoke_path": json_path
    }


def format_srt_time(seconds):
    """Convert seconds to SRT time format (HH:MM:SS,MS)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

# === Subtitle ===

def hex_to_ass_color(hex_color: str) -> str:
    """Chuyển mã hex RGB (ví dụ 'FF69B4') sang định dạng màu ASS (&H00BBGGRR)."""
    hex_color = hex_color.strip("#")
    if len(hex_color) != 6:
        return "&H00FFFFFF"  # fallback trắng
    r = hex_color[0:2]
    g = hex_color[2:4]
    b = hex_color[4:6]
    return f"&H00{b}{g}{r}"  # BGR cho ASS


def sanitize_path(path: str) -> str:
    filename = Path(path).name
    safe_name = re.sub(r'[,:\"\'<>|?* ]+', '_', filename)
    return str(Path(path).with_name(safe_name))


def generate_karaoke_ass_from_srt_and_words(
    srt_path,
    karaoke_json_path,
    output_ass_path,
    font="Arial",
    size=14,
    position="dưới",
    base_color="&H00FFFFFF",
    highlight_color="&H00FFFF00",
    mode="Phụ đề thường (toàn câu)"
):
    def convert_srt_time(srt_time):
        h, m, s = srt_time.split(":")
        s, ms = s.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    def format_ass_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02}:{s:02}.{cs:02}"

    with open(karaoke_json_path, "r", encoding="utf-8") as f:
        word_items = [w for w in json.load(f) if w.get("type") == "word"]

    def parse_srt(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        blocks = re.split(r'\n\s*\n', content.strip())
        segments = []
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                time_line = lines[1]
                text = ' '.join(lines[2:])
                match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', time_line)
                if match:
                    start = convert_srt_time(match.group(1))
                    end = convert_srt_time(match.group(2))
                    segments.append({"start": start, "end": end, "text": text})
        return segments

    alignment_map = {
        "trên": 8,
        "giữa": 5,
        "dưới": 2
    }
    alignment = alignment_map.get(position.lower(), 2)

    output_ass_path = sanitize_path(output_ass_path)
    output_dir = os.path.dirname(output_ass_path)
    os.makedirs(output_dir, exist_ok=True)

    segments = parse_srt(srt_path)

    with open(output_ass_path, "w", encoding="utf-8") as f:
        # Header
        f.write("[Script Info]\nTitle: Karaoke Sub\nScriptType: v4.00+\n\n")
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        outline_color = "&H00303030"
        f.write(f"Style: Base,{font},{size},{base_color},{outline_color},0,0,0,0,100,100,0,0,1,1,0,{alignment},10,10,20,1\n")
        f.write(f"Style: Highlight,{font},{size},{highlight_color},{outline_color},0,0,0,0,100,100,0,0,1,1,0,{alignment},10,10,20,1\n\n")

        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

        word_idx = 0
        for seg in segments:
            seg_start = seg["start"]
            seg_end = seg["end"]
            ass_start = format_ass_time(seg_start)
            ass_end = format_ass_time(seg_end)
            full_text = seg["text"]

            # Lấy các từ thuộc đoạn
            line_words = []
            temp_idx = word_idx
            while temp_idx < len(word_items):
                w = word_items[temp_idx]
                if w["end"] <= seg_start:
                    temp_idx += 1
                    continue
                if w["start"] >= seg_end:
                    break
                line_words.append({
                    "start": w["start"],
                    "end": w["end"],
                    "text": w["text"].replace("{", "").replace("}", ""),
                    "dur": int((w["end"] - w["start"]) * 100)
                })
                temp_idx += 1

            # Ghi phụ đề theo mode
            if mode == "Phụ đề thường (toàn câu)":
                f.write(f"Dialogue: -1,{ass_start},{ass_end},Base,,0,0,0,,{{\\1a&H80&}}{full_text}\n")
                f.write(f"Dialogue: 0,{ass_start},{ass_end},Base,,0,0,0,,{full_text}\n")

            elif mode == "Highlight từng từ (karaoke)":
                ass_line = "".join([f"{{\\k{w['dur']}}}{w['text']}" for w in line_words])
                f.write(f"Dialogue: 0,{ass_start},{ass_end},Highlight,,0,0,0,,{ass_line}\n")

            elif mode == "Highlight tuần tự (màu chữ)":
                for i, _ in enumerate(line_words):
                    ass_line = "".join([
                        f"{{\\1c{highlight_color}}}{w['text']}" if j == i else f"{{\\1c{base_color}}}{w['text']}"
                        for j, w in enumerate(line_words)
                    ])
                    start = format_ass_time(line_words[i]["start"])
                    end = format_ass_time(line_words[i]["end"])
                    f.write(f"Dialogue: 0,{start},{end},Highlight,,0,0,0,,{ass_line.strip()}\n")

            elif mode == "Highlight tuần tự (zoom chữ)":
                for i, _ in enumerate(line_words):
                    ass_line = "".join([
                        (
                            f"{{\\1c{highlight_color}\\fs{size}"
                            f"\\t(0,100,\\fs{int(size * 1.3)})"
                            f"\\t(100,300,\\fs{size})}}{w['text']}"
                            if j == i else f"{{\\1c{base_color}\\fs{size}}}{w['text']}"
                        )
                        for j, w in enumerate(line_words)
                    ])
                    start = format_ass_time(line_words[i]["start"])
                    end = format_ass_time(line_words[i]["end"])
                    f.write(f"Dialogue: 0,{start},{end},Highlight,,0,0,0,,{ass_line.strip()}\n")

            elif mode == "Highlight tuần tự (ô vuông)":
                for i, _ in enumerate(line_words):
                    ass_line = "".join([
                        (
                            f"{{\\1c{highlight_color}\\bord2\\shad0\\3c&H000000&}}{w['text']}"
                            if j == i else f"{{\\1c{base_color}\\bord0\\shad0}}{w['text']}"
                        )
                        for j, w in enumerate(line_words)
                    ])
                    start = format_ass_time(line_words[i]["start"])
                    end = format_ass_time(line_words[i]["end"])
                    f.write(f"Dialogue: 0,{start},{end},Highlight,,0,0,0,,{ass_line.strip()}\n")

            elif mode == "Hiệu ứng từng chữ một (chuyên sâu)":
                for w in line_words:
                    w_start = format_ass_time(w["start"])
                    w_end = format_ass_time(w["end"])
                    scale_up = int(size * 1.2)
                    effect = f"{{\\fad(100,100)\\fs{size}\\t(0,200,\\fs{scale_up})}}{w['text']}"
                    f.write(f"Dialogue: 0,{w_start},{w_end},Highlight,,0,0,0,,{effect}\n")

            word_idx = temp_idx

    print(f"✅ Đã tạo phụ đề .ass ({mode}): {output_ass_path}")