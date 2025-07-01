import os
import json
import re
import requests


# === 🔊 TTS: Tạo giọng nói với ElevenLabs ===
def create_voice(text, output_file, api_key, voice_id="EXAVITQu4vr4xnSDxMaL"):
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

    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        with open(output_file, "wb") as f:
            f.write(res.content)
    else:
        raise Exception(f"❌ Tạo voice thất bại: {res.status_code} - {res.text}")


# === 🔍 Kiểm tra key API ===
def validate_api_key(api_key):
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
        res = requests.post(url, headers=headers, json=payload, timeout=5)

        if res.status_code == 200:
            print(f"✅ API Key hợp lệ: {api_key[:4]}...{api_key[-4:]}")
            return True

        elif res.status_code == 400:
            detail = res.json().get("detail", {})
            status = detail.get("status", "").lower()
            message = detail.get("message", "").lower()
            print(f"⚠️ API Key bị giới hạn: {status} | {message}")
            return "voice_limit_reached" in status or "voice_limit_reached" in message

        elif res.status_code == 401:
            print(f"❌ API Key không hợp lệ: {api_key[:4]}...{api_key[-4:]}")
            return False

        else:
            print(f"❓ Status khác thường ({res.status_code}): {res.text}")
            return False

    except Exception as e:
        print(f"❌ Lỗi khi kiểm tra API Key: {e}")
        return False


# === 📥 Tạo phụ đề từ audio bằng STT của ElevenLabs ===
def transcribe_audio(audio_path, output_base="output", api_key=None):
    if not api_key:
        raise ValueError("❌ Thiếu API Key ElevenLabs!")

    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    srt_path = os.path.join(output_dir, f"{output_base}.srt")
    json_path = os.path.join(output_dir, f"{output_base}.json")

    with open(audio_path, "rb") as f:
        files = {
            "file": (os.path.basename(audio_path), f, "audio/mpeg")
        }

        payload = {
            "model_id": "scribe_v1",
            "language_code": "vi",
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

        res = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": api_key},
            files=files,
            data=payload
        )

    if not res.ok:
        raise Exception(f"❌ Lỗi STT ElevenLabs: {res.status_code} - {res.text}")

    result = res.json()

    # Save SRT
    srt_content = next((f["content"] for f in result.get("additional_formats", []) if f["file_extension"] == "srt"), None)
    if not srt_content:
        raise Exception("❌ Không có nội dung SRT trả về.")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    # Save karaoke JSON
    if "words" in result:
        words = [w for w in result["words"] if w.get("type") == "word"]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
    else:
        raise Exception("❌ Không có word-level data!")

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
