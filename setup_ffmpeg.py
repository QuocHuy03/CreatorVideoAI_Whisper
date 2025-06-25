# setup_ffmpeg.py

import os
import sys
import zipfile
import urllib.request
import shutil
import subprocess

def is_ffmpeg_installed():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False

def download_and_setup_ffmpeg():
    print("🔽 FFmpeg chưa cài đặt. Đang tải về...")
    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zip_path = "ffmpeg_temp.zip"
    extract_dir = "ffmpeg_temp"

    try:
        urllib.request.urlretrieve(ffmpeg_url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        os.remove(zip_path)

        for root, dirs, files in os.walk(extract_dir):
            if "ffmpeg.exe" in files:
                bin_path = root
                break
        else:
            raise FileNotFoundError("Không tìm thấy ffmpeg.exe trong file zip.")

        shutil.copy(os.path.join(bin_path, "ffmpeg.exe"), os.getcwd())
        print("✅ Đã cài FFmpeg tại:", os.getcwd())

    except Exception as e:
        print("❌ Lỗi khi tải/cài FFmpeg:", e)
        sys.exit("Không thể tiếp tục nếu không có FFmpeg")

def ensure_ffmpeg():
    if not is_ffmpeg_installed() and not os.path.exists("ffmpeg.exe"):
        download_and_setup_ffmpeg()

    if not is_ffmpeg_installed() and not os.path.exists("ffmpeg.exe"):
        sys.exit("⚠️ Không tìm thấy FFmpeg. Vui lòng cài đặt thủ công.")

    if os.path.exists("ffmpeg.exe"):
        os.environ["PATH"] += os.pathsep + os.getcwd()
