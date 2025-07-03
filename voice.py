import requests
import json
import time
import os
import pygame

# === CẤU HÌNH CỦA BOSS ===
API_KEY = "sk_e5c77364a55b0a7f4da8690c58dc6adfd4886d29878a026a"
VOICE_ID = "BUPPIXeDaJWBz696iXRS"
TEXT = """InterLink V3 آرہا ہے: نئے گیمز، پوائنٹ ملٹیپلائر، tier ranking، میں $23,000 کے انعامات ہیں—MacBook، AirPods، نقدی اور ITLX whitelist!
نئے صارفین کے لیے منصفانہ ٹریک: کوئی whales یا KOLs کا فائدہ نہیں۔
ابھی ایپ Apple/Google کی منظوری میں ہے—صبر کریں، بہت جلد یہ آپ کے ہاتھ میں ہوگا!
تیار ہو جاؤ—InterLink پاکستان میں حاکم بننے والا ہے!"""

# === PROXY CONFIG ===
PROXIES = {
    "http": "http://Vilas:Hien0104@103.164.154.115:1223",
    "https": "http://Vilas:Hien0104@103.164.154.115:1223"
}


def generate_voice_from_text(text, output_path, voice_id, api_key):
    print("🔄 Đang tạo giọng nói...")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    data = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.75
        }
    }

    response = requests.post(url, json=data, headers=headers, proxies=PROXIES)

    if response.ok:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Đã tạo file MP3: {output_path}")
    else:
        raise Exception(f"Lỗi tạo voice: {response.status_code} - {response.text}")


def generate_srt_from_audio(audio_path, output_srt_path, api_key, language_code="urd"):
    print("🔄 Đang xử lý phụ đề SRT...")

    additional_formats = [ {
        "format": "srt",
        "include_timestamps": True,
        "include_speakers": False,
        "max_characters_per_line": 20,
        "segment_on_silence_longer_than_s": 1.2,
        "max_segment_duration_s": 5,
        "max_segment_chars": 20
    } ]

    with open(audio_path, "rb") as f:
        files = {
            "file": (audio_path, f, "audio/mpeg")
        }
        data = {
            "model_id": "scribe_v1",
            "language_code": language_code,
            "diarize": "true",
            "additional_formats": json.dumps(additional_formats)
        }
        
        response = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": api_key},
            files=files,
            data=data,
            proxies=PROXIES
        )

    if response.ok:
        result = response.json()

        srt_content = next((f["content"] for f in result.get("additional_formats", []) if f["file_extension"] == "srt"), None)
        if srt_content:
            with open(output_srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            print(f"✅ Đã xuất SRT: {output_srt_path}")
        else:
            print("⚠️ Không tìm thấy nội dung SRT.")

        if "words" in result:
            filtered_words = [w for w in result["words"] if w.get("type") == "word"]
            with open("karaoke_words.json", "w", encoding="utf-8") as f:
                json.dump(filtered_words, f, ensure_ascii=False, indent=2)
            print("✅ Đã xuất karaoke words JSON: karaoke_words.json")
        else:
            print("⚠️ Không có dữ liệu từ-level (words[]) để xuất karaoke.")
    else:
        raise Exception(f"Lỗi API: {response.status_code} - {response.text}")



def karaoke_with_audio(json_path, audio_path):
    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    # Câu đầy đủ
    full_sentence = " ".join([w["text"] for w in words])
    print("🎤 Câu sẽ đọc:", full_sentence)
    time.sleep(1)

    # Bắt đầu pygame mixer
    pygame.mixer.init()
    pygame.mixer.music.load(audio_path)
    pygame.mixer.music.play()

    # Đếm thời gian
    start_time = time.time()

    for i, word in enumerate(words):
        text = word.get("text")
        start = word.get("start", 0)
        end = word.get("end", 0)

        while time.time() - start_time < start:
            time.sleep(0.005)

        # In cả câu, highlight từ đang đọc
        os.system('cls' if os.name == 'nt' else 'clear')
        display_line = ""
        for j, w in enumerate(words):
            if j == i:
                display_line += f"\033[93m{w['text']}\033[0m "
            else:
                display_line += w['text'] + " "
        print(display_line.strip())

        time.sleep(end - start)

    print("\n✅ Karaoke kết thúc!")

    # Đợi phát xong rồi thoát
    while pygame.mixer.music.get_busy():
        time.sleep(0.5)



# === CHẠY TOÀN BỘ QUY TRÌNH ===
if __name__ == "__main__":
    mp3_path = "output_voice.mp3"
    srt_path = "output_subtitle.srt"

    generate_voice_from_text(TEXT, mp3_path, VOICE_ID, API_KEY)
    generate_srt_from_audio(mp3_path, srt_path, API_KEY)
    karaoke_with_audio("karaoke_words.json", mp3_path)