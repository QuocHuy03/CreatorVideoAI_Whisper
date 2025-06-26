import requests
import json

def generate_srt_from_audio(audio_path, output_srt_path, api_key, language_code):
    additional_formats = [{
        "format": "srt",
        "include_timestamps": True,
        "include_speakers": True,
        "max_characters_per_line": 60,
        "segment_on_silence_longer_than_s": 2,
        "max_segment_duration_s": 6,
        "max_segment_chars": 100
    }]

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
            data=data
        )

    if response.ok:
        result = response.json()
        srt_content = next((f["content"] for f in result.get("additional_formats", []) if f["file_extension"] == "srt"), None)
        if srt_content:
            with open(output_srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
        else:
            raise Exception("Không tìm thấy nội dung SRT trong phản hồi ElevenLabs.")
    else:
        raise Exception(f"Lỗi API: {response.status_code} - {response.text}")
