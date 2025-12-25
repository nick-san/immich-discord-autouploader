import discord
import requests
import os
import re  # ← これが必要です！
from io import BytesIO
from datetime import timezone, timedelta, datetime
from dotenv import load_dotenv
from PIL import Image, ExifTags
from dateutil import parser

load_dotenv()

# --- 環境変数設定 ---
TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID'))
API_KEY = os.getenv('API_KEY')
IMMICH_URL = os.getenv('IMMICH_URL')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if not all([TARGET_CHANNEL_ID, API_KEY, IMMICH_URL, DISCORD_TOKEN]):
    raise ValueError("Error: .envファイルの設定が不足しています。")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

TARGET_EXTENSIONS = [
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    'mp4', 'mov', 'webm', 'avi', 'mkv'
]

JST = timezone(timedelta(hours=9), 'JST')

# --- 1. ファイル名から日時を抽出する関数（Pixel専用処理付き） ---
def get_date_from_filename(filename):
    
    # ---------------------------------------------------------
    # パターンA: Google Pixel (PXL_...) の場合 -> UTCなのでJSTに変換
    # ---------------------------------------------------------
    if "PXL_" in filename:
        # PXL_YYYYMMDD_HHMMSS... の数字部分を抽出
        pixel_pattern = r'PXL_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})'
        match = re.search(pixel_pattern, filename)
        
        if match:
            try:
                y, m, d, H, M, S = map(int, match.groups())
                # UTCとして定義
                dt_utc = datetime(y, m, d, H, M, S, tzinfo=timezone.utc)
                # JSTに変換
                dt_jst = dt_utc.astimezone(JST)
                return dt_jst.isoformat()
            except ValueError:
                pass 

    # ---------------------------------------------------------
    # パターンB: その他のAndroid / スクショ / Galaxy / Xiaomiなど
    # 基本的に「端末のローカル時間(JST)」で保存されている
    # ---------------------------------------------------------
    try:
        # dateutilで日付を抽出
        dt = parser.parse(filename, fuzzy=True)
        
        current_year = discord.utils.utcnow().year + 1
        if 1990 <= dt.year <= current_year:
            # タイムゾーン情報がない場合は JST とみなす
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            return dt.isoformat()
            
    except (ValueError, OverflowError):
        pass
            
    return None           
    return None

# --- 2. EXIFから日時を抽出する関数 ---
def get_exif_date(file_stream):
    try:
        image = Image.open(file_stream)
        exif = image._getexif()
        
        if not exif:
            return None

        # 36867: DateTimeOriginal, 306: DateTime
        date_str = exif.get(36867) or exif.get(306)

        if date_str:
            # EXIFの形式を dateutil で読むことも可能ですが、ここはフォーマットが決まっているのでそのままで
            # YYYY:MM:DD HH:MM:SS 形式
            dt = parser.parse(date_str.replace(':', '-', 2)) # コロンをハイフンに変えてparseさせるテクニック
            return dt.isoformat()
            
    except Exception:
        pass
    
    return None

@client.event
async def on_ready():
    print(f'ログインしました: {client.user}')
    print(f'監視対象のチャンネルID: {TARGET_CHANNEL_ID}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id == TARGET_CHANNEL_ID:
        jst_time = message.created_at.astimezone(JST)
        
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in TARGET_EXTENSIONS):
                print(f"--- 処理開始: {attachment.filename} ---")

                try:
                    file_data = await attachment.read()
                    file_io = BytesIO(file_data)
                    
                    final_date = None
                    source_type = ""

                    # 1. ファイル名解析 (dateutilにお任せ)
                    filename_date = get_date_from_filename(attachment.filename)
                    if filename_date:
                        final_date = filename_date
                        source_type = "📂 ファイル名解析(Auto)"
                    
                    # 2. EXIF解析
                    if not final_date:
                        exif_date = get_exif_date(file_io)
                        file_io.seek(0) # ストリームリセット
                        if exif_date:
                            final_date = exif_date
                            source_type = "📷 EXIFデータ"
                    
                    # 3. 投稿日時
                    if not final_date:
                        final_date = jst_time.isoformat()
                        source_type = "🕒 Discord投稿日時"

                    print(f"  決定日時: {final_date} (由来: {source_type})")

                    headers = {
                        'x-api-key': API_KEY,
                        'Accept': 'application/json'
                    }

                    files = {
                        'assetData': (attachment.filename, file_io, attachment.content_type)
                    }

                    data = {
                        'deviceAssetId': f"discord-{attachment.id}",
                        'deviceId': 'discord-bot',
                        'fileCreatedAt': final_date,
                        'fileModifiedAt': final_date,
                        'isFavorite': 'false'
                    }

                    response = requests.post(IMMICH_URL, headers=headers, data=data, files=files)

                    if response.status_code == 201:
                        await message.channel.send(f"✅ 保存完了 ({source_type}): {attachment.filename}")
                    else:
                        print(f"エラー: {response.text}")
                        await message.channel.send(f"❌ エラー ({response.status_code})")

                except Exception as e:
                    print(f"例外エラー: {e}")
                    await message.channel.send(f"❌ プログラムエラー: {e}")

client.run(DISCORD_TOKEN)
