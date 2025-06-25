import requests

def create_voice_with_elevenlabs(text, output_file, api_key, voice_id="EXAVITQu4vr4xnSDxMaL"):
    """Chỉ tạo giọng mới, không xóa giọng cũ"""
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
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        with open(output_file, "wb") as f:
            f.write(response.content)
    else:
        raise Exception(f"ElevenLabs error: {response.status_code}, {response.text}")


def create_or_replace_voice(text, output_file, api_key, voice_id="EXAVITQu4vr4xnSDxMaL"):
    """
    Tạo giọng mới nhưng xóa giọng cũ nếu tồn tại trước khi tạo mới.
    App gọi hàm này nếu cần thay thế giọng.
    """
    try:
        existing_voices = get_my_custom_voices(api_key)
        existing_voice_ids = [v.get("voice_id") for v in existing_voices]
        if voice_id in existing_voice_ids:
            delete_voice(api_key, voice_id)
            print(f"🗑️ Giọng cũ {voice_id} đã được xóa trước khi tạo mới.")
        else:
            print(f"ℹ️ Giọng {voice_id} không tồn tại, không cần xóa.")
    except Exception as e:
        print(f"⚠️ Không lấy/xóa giọng cũ được: {e}")

    # Tạo giọng mới
    create_voice_with_elevenlabs(text, output_file, api_key, voice_id)


def validate_api_key(api_key):
    test_url = "https://api.elevenlabs.io/v1/text-to-speech/Xb7hH8MSUJpSbSDYk0k2"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "text": "Test",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
    }
    valid = False
    try:
        res = requests.post(test_url, headers=headers, json=payload, timeout=5)

        if res.status_code == 200:
            print(f"✅ Key {api_key[:4]}...{api_key[-4:]} hợp lệ (200)")
            valid = True

        elif res.status_code == 400:
            try:
                json_data = res.json()
                detail = json_data.get("detail", {})
                status = detail.get("status", "").lower()
                message = detail.get("message", "").lower()
            except Exception:
                print(f"⚠️ Không parse được JSON từ key {api_key[:4]}...{api_key[-4:]} — raw: {res.text}")
                status = ""
                message = res.text.lower()

            print(f"⚠️ Key {api_key[:4]}...{api_key[-4:]} | 400: {status} - {message}")

            if "voice_limit_reached" in status or "voice_limit_reached" in message:
                valid = True
            elif "missing_default_voice" in status or "missing_default_voice" in message:
                valid = False
            else:
                valid = False

        elif res.status_code == 401:
            print(f"❌ Key {api_key[:4]}...{api_key[-4:]} | 401: Invalid API Key")
            valid = False

        else:
            print(f"❓ Key {api_key[:4]}...{api_key[-4:]} | Status {res.status_code}: {res.text}")
            valid = False

    except Exception as e:
        print(f"API Key validation error: {e}")
        valid = False

    return valid


def get_my_custom_voices(api_key):
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        all_voices = response.json().get("voices", [])
        return [v for v in all_voices if v.get("category") == "professional"]
    else:
        raise Exception(f"❌ Lỗi khi lấy danh sách voice: {response.text}")


def delete_voice(api_key, voice_id):
    url = f"https://api.elevenlabs.io/v1/voices/{voice_id}"
    headers = {"xi-api-key": api_key}
    response = requests.delete(url, headers=headers)
    if response.status_code in [200, 204]:
        print(f"🗑️ Đã xóa voice: {voice_id}")
    else:
        if response.status_code == 400 and "voice_does_not_exist" in response.text:
            raise Exception(f"❌ Giọng nói {voice_id} không tồn tại.")
        raise Exception(f"❌ Lỗi xóa voice: {voice_id} - {response.status_code} - {response.text}")