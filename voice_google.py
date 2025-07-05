import os
import json
import random
import requests
from faster_whisper import WhisperModel
import base64
import ffmpeg
import time


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


def create_voice(text, output_file_pcm, api_key, voice_name="achird"):
    """Generate voice audio using the Google Gemini TTS API."""
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
        json=data
    )

    if response.status_code == 200:
        response_data = response.json()
        audio_data = response_data['candidates'][0]['content']['parts'][0]['inlineData']['data']
        decoded_audio = base64.b64decode(audio_data)

        # Save the PCM file
        with open(output_file_pcm, "wb") as audio_file:
            audio_file.write(decoded_audio)

        # Create MP3 file name
        base_name, _ = os.path.splitext(output_file_pcm)
        timestamp = time.strftime("%Y%m%d%H%M%S")
        mp3_file = f"{base_name}_{timestamp}.mp3"

        # Ensure no file overwrite
        while os.path.exists(mp3_file):
            unique_suffix = random.randint(1000, 9999)
            mp3_file = f"{base_name}_{timestamp}_{unique_suffix}.mp3"

        # Convert PCM to MP3
        ffmpeg.input(output_file_pcm, f='s16le', ar='24000', ac='1') \
            .output(mp3_file, **{'y': None}) \
            .run(overwrite_output=True)

        # Delete the PCM file after conversion
        try:
            os.remove(output_file_pcm)
            print(f"🧹 Đã xóa file PCM tạm: {output_file_pcm}")
        except Exception as e:
            print(f"⚠️ Không thể xóa file PCM {output_file_pcm}: {e}")

        print(f"✅ Voice generated successfully. Saved as {mp3_file}")
        return mp3_file
    else:
        print(f"❌ Failed to generate voice: {response.status_code} - {response.text}")
        raise Exception(f"❌ Failed to generate voice. Status Code: {response.status_code}")


def create_voice_with_retry(text, output_file, api_key_list, voice_name="achird"):
    """Attempt to generate voice using a list of API keys, retrying with a new key if one fails."""
    for api_key in api_key_list:
        try:
            print(f"🎤 Đang thử với API Key: {api_key}")
            audio_path = create_voice(text, output_file, api_key, voice_name)
            return audio_path
        except Exception as e:
            print(f"❌ Lỗi khi tạo giọng với API Key {api_key}: {e}")
            continue
    raise Exception("❌ Tất cả các API Key đều thất bại trong việc tạo giọng!")


def transcribe_audio(audio_path, folder_path, output_base="output", language_code=None):
    """Transcribe audio to text using fast-whisper and generate subtitle files."""

    output_dir = folder_path
    os.makedirs(output_dir, exist_ok=True)
    model = WhisperModel("small", device="cpu")  # Có thể thay bằng "medium" nếu cần

    print(f"🧠 Transcribing audio file: {audio_path}")
    segments_gen, info = model.transcribe(audio_path, language=language_code, word_timestamps=True)
    segments = list(segments_gen)  # Chuyển generator thành list

    if not segments:
        print("❌ No transcriptions available.")
        return {}

    srt_path = os.path.join(output_dir, f"{output_base}.srt")
    json_path = os.path.join(output_dir, f"{output_base}.json")

    # Viết SRT file
    with open(srt_path, "w", encoding="utf-8") as srt_file:
        for idx, segment in enumerate(segments, 1):
            start = segment.start
            end = segment.end
            text = segment.text

            start_time = format_srt_time(start)
            end_time = format_srt_time(end)

            srt_file.write(f"{idx}\n{start_time} --> {end_time}\n{text}\n\n")

    # Viết JSON karaoke
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
            words_data.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
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
    """Convert hex color (e.g., 'FF69B4') to ASS color (&H00BBGGRR)"""
    hex_color = hex_color.strip("#")
    if len(hex_color) != 6:
        return "&H00FFFFFF"  # fallback to white
    r = hex_color[0:2]
    g = hex_color[2:4]
    b = hex_color[4:6]
    return f"&H00{b}{g}{r}"  # ASS uses BGR order


def generate_karaoke_ass_from_srt_and_words(srt_path, karaoke_json_path, output_ass_path,
                                             font="Arial", size=14, position="dưới", color="FFFFFF"):
    def convert_srt_time(srt_time):
        h, m, s = srt_time.split(":")
        s, ms = s.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    def format_ass_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round((seconds % 1) * 100))
        return f"{h}:{m:02}:{s:02}.{cs:02}"
    ass_color = hex_to_ass_color(color)
    alignment_map = {
        "trên": 8,    # top-center
        "giữa": 5,    # middle-center
        "dưới": 2     # bottom-center
    }
    alignment = alignment_map.get(position.lower(), 2)  # fallback: dưới

    with open(karaoke_json_path, "r", encoding="utf-8") as f:
        word_items = [w for w in json.load(f) if w.get("type") == "word"]

    with open(output_ass_path, "w", encoding="utf-8") as f:
        # Header
        f.write("[Script Info]\nTitle: Karaoke Sub\nScriptType: v4.00+\n\n")
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write(f"Style: Highlight,{font},{size},{ass_color},1,0,0,0,100,100,0,0,1,1,0,{alignment},10,10,9,1\n\n")

        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

        for word in word_items:
            start = word.get("start")
            end = word.get("end")
            text = word.get("text") or word.get("word") or ""
            text = text.replace("{", "").replace("}", "")

            if not text.strip():
                continue

            start_ts = format_ass_time(start)
            end_ts = format_ass_time(end)
            scale_up = int(size * 1.2)

            effect = f"{{\\fad(100,100)\\fs{size}\\t(0,200,\\fs{scale_up})}}{text}"
            f.write(f"Dialogue: 0,{start_ts},{end_ts},Highlight,,0,0,0,,{effect}\n")

    print(f"✅ Đã tạo file karaoke .ass với hiệu ứng từng chữ: {output_ass_path}")
