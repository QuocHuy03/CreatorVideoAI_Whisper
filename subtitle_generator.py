from pydub import AudioSegment

def split_text_to_words(text):
    return text.strip().split()

def format_time_ms(ms):
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(ms):03d}"

def create_srt_word_by_word(audio_path, text, output_file):
    words = split_text_to_words(text)
    audio = AudioSegment.from_file(audio_path)
    duration_ms = len(audio)
    duration_per_word = duration_ms // len(words)
    with open(output_file, "w", encoding="utf-8") as f:
        for i, word in enumerate(words):
            start = i * duration_per_word
            end = (i + 1) * duration_per_word
            f.write(f"{i + 1}\n")
            f.write(f"{format_time_ms(start)} --> {format_time_ms(end)}\n")
            f.write(f"{word}\n\n")

