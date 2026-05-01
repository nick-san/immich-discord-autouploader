import os
from dotenv import load_dotenv

load_dotenv()

# --- 環境変数設定 ---
TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID', 0))
API_KEY = os.getenv('API_KEY')
IMMICH_URL = os.getenv('IMMICH_URL')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# バリデーション
if not all([TARGET_CHANNEL_ID, API_KEY, IMMICH_URL, DISCORD_TOKEN]):
    raise ValueError("Error: .envファイルの設定が不足しています。")

# 定数
TARGET_EXTENSIONS = [
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    'mp4', 'mov', 'webm', 'avi', 'mkv'
]

# 画像拡張子の判定用
IMAGE_EXTENSIONS = ('.jpg', '.jpeg')
