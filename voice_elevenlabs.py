import os
import json
import random
import requests

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

            # Nếu có file path thì mở lại mỗi lần
            if files_path:
                file_key, file_path, mime = files_path
                with open(file_path, "rb") as f:
                    files = {
                        file_key: (os.path.basename(file_path), f, mime)
                    }
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


def create_voice(text, output_file, api_key, voice_id="EXAVITQu4vr4xnSDxMaL", use_proxy=True):
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

    if use_proxy:
        res = send_with_proxy_retry("POST", url, headers=headers, json_data=payload)
    else:
        res = requests.post(url, headers=headers, json=payload)

    if res.status_code == 200:
        with open(output_file, "wb") as f:
            f.write(res.content)
        print("✅ Đã tạo voice thành công.")
    else:
        raise Exception(f"❌ Tạo voice thất bại: {res.status_code} - {res.text}")

def validate_api_key(api_key, use_proxy=True):
    url = "https://api.elevenlabs.io/v1/text-to-speech/Xb7hH8MSUJpSbSDYk0k2"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "text": "Test",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
    }

    try:
        if use_proxy:
            res = send_with_proxy_retry("POST", url, headers=headers, json_data=payload)
        else:
            res = requests.post(url, headers=headers, json=payload, timeout=10)

        if res.status_code == 200:
            print(f"✅ API Key hợp lệ: {api_key[:4]}...{api_key[-4:]}")
            return True
        elif res.status_code == 401:
            print(f"❌ API Key không hợp lệ: {api_key}")
            return False
        else:
            print(f"⚠️ Lỗi không xác định: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        print(f"❌ Lỗi kiểm tra API Key: {e}")
        return False

def transcribe_audio(audio_path, folder_path, output_base="output", api_key=None, language_code=None, use_proxy=True):
    if not api_key:
        raise ValueError("❌ Thiếu API Key ElevenLabs!")

    output_dir = folder_path
    os.makedirs(output_dir, exist_ok=True)

    srt_path = os.path.join(output_dir, f"{output_base}.srt")
    json_path = os.path.join(output_dir, f"{output_base}.json")

    payload = {
        "model_id": "scribe_v1",
        "diarize": "true",
        "additional_formats": json.dumps([{
            "format": "srt",
            "include_timestamps": True,
            "include_speakers": False,
            "max_characters_per_line": 26,
            "segment_on_silence_longer_than_s": 1.2,
            "max_segment_duration_s": 6,
            "max_segment_chars": 24
        }])
    }

    if language_code:
        payload["language_code"] = language_code

    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": api_key}

    if use_proxy:
        # Gửi kèm đường dẫn để send_with_proxy_retry mở lại file mỗi lần
        files_path = ("file", audio_path, "audio/mpeg")
        res = send_with_proxy_retry("POST", url, headers=headers, data=payload, files_path=files_path)
    else:
        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
            res = requests.post(url, headers=headers, files=files, data=payload)

    if not res.ok:
        raise Exception(f"❌ Lỗi STT ElevenLabs: {res.status_code} - {res.text}")

    result = res.json()

    srt_content = next((f["content"] for f in result.get("additional_formats", []) if f["file_extension"] == "srt"), None)
    if not srt_content:
        raise Exception("❌ Không có nội dung SRT trả về.")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    if "words" in result:
        words = [w for w in result["words"] if w.get("type") == "word"]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
    else:
        raise Exception("❌ Không có word-level data!")

    print("✅ Đã xử lý xong phụ đề và karaoke JSON")
    return {
        "srt_path": srt_path,
        "karaoke_path": json_path
    }



# === 🔄 Giao diện quản lý giọng nói ===
def get_my_custom_voices(api_key):
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}
    res = requests.get(url, headers=headers)
    if res.ok:
        return [v for v in res.json().get("voices", []) if v.get("category") == "professional"]
    else:
        raise Exception(f"❌ Lỗi lấy voice: {res.status_code} - {res.text}")


def delete_voice(api_key, voice_id):
    url = f"https://api.elevenlabs.io/v1/voices/{voice_id}"
    headers = {"xi-api-key": api_key}
    res = requests.delete(url, headers=headers)
    if res.status_code in [200, 204]:
        print(f"🗑️ Đã xoá voice: {voice_id}")
    elif res.status_code == 400 and "voice_does_not_exist" in res.text:
        print(f"⚠️ Voice không tồn tại: {voice_id}")
    else:
        raise Exception(f"❌ Lỗi xoá voice: {res.status_code} - {res.text}")


def create_or_replace_voice(text, output_file, api_key, voice_id="EXAVITQu4vr4xnSDxMaL"):
    try:
        voices = get_my_custom_voices(api_key)
        if any(v["voice_id"] == voice_id for v in voices):
            delete_voice(api_key, voice_id)
            print(f"🧹 Đã xoá voice cũ: {voice_id}")
    except Exception as e:
        print(f"⚠️ Lỗi khi xoá voice cũ: {e}")

    create_voice(text, output_file, api_key, voice_id)



# === Subtitle ===

def generate_karaoke_ass_from_srt_and_words(srt_path, karaoke_json_path, output_ass_path,
                                             font="Arial", size=14):

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

    with open(karaoke_json_path, "r", encoding="utf-8") as f:
        word_items = [w for w in json.load(f) if w.get("type") == "word"]

    with open(output_ass_path, "w", encoding="utf-8") as f:
        # Header
        f.write("[Script Info]\nTitle: Karaoke Sub\nScriptType: v4.00+\n\n")
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write(f"Style: Highlight,{font},{size},&H00FFFF00,1,0,0,0,100,100,0,0,1,1,0,2,10,10,9,1\n\n")

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