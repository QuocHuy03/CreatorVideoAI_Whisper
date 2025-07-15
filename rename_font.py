import os
import re
from fontTools.ttLib import TTFont

def get_internal_font_name(font_path):
    try:
        font = TTFont(font_path)
        for record in font['name'].names:
            if record.nameID == 1:
                name = record.string.decode('utf-16-be') if b'\x00' in record.string else record.string.decode('utf-8')
                return name
    except Exception as e:
        print(f"❌ Không đọc được font {font_path}: {e}")
    return None

def sanitize_filename(name):
    # Loại bỏ ký tự lạ, chỉ giữ chữ cái, số, khoảng trắng và thay thế khoảng trắng bằng _
    return re.sub(r'[^A-Za-z0-9 ]+', '', name).strip().replace(' ', '_') + '.ttf'

fonts_folder = "fonts"

print("🔄 Đang đổi tên font theo tên nội bộ...\n")

for file in os.listdir(fonts_folder):
    if file.lower().endswith(".ttf"):
        full_path = os.path.join(fonts_folder, file)
        font_name = get_internal_font_name(full_path)
        if font_name:
            new_filename = sanitize_filename(font_name)
            new_path = os.path.join(fonts_folder, new_filename)
            if full_path != new_path:
                if os.path.exists(new_path):
                    print(f"⚠️ Đã tồn tại file {new_filename}, bỏ qua.")
                else:
                    os.rename(full_path, new_path)
                    print(f"✅ {file} ➜ {new_filename}")
            else:
                print(f"✅ {file} đã đúng tên.")
        else:
            print(f"⚠️ Không lấy được tên từ: {file}")
