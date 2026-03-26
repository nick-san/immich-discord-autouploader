import discord
import requests
import os
import re
import piexif 
import certifi
from io import BytesIO
from datetime import timezone, timedelta, datetime
from dotenv import load_dotenv
from PIL import Image
from dateutil import parser 

os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

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

def get_date_from_filename(filename):
    pixel_pattern = r'PXL_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})'
    match = re.search(pixel_pattern, filename)
    if match:
        try:
            y, m, d, H, M, S = map(int, match.groups())
            dt_utc = datetime(y, m, d, H, M, S, tzinfo=timezone.utc)
            return dt_utc.astimezone(JST)
        except ValueError:
            pass

    try:
        dt = parser.parse(filename, fuzzy=True)
        current_year = discord.utils.utcnow().year + 1
        if 1990 <= dt.year <= current_year:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            return dt
    except (ValueError, OverflowError):
        pass
    
    return None

@client.event
async def on_ready():
    print(f'ログインしました: {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id == TARGET_CHANNEL_ID:
        jst_now = message.created_at.astimezone(JST)
        
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in TARGET_EXTENSIONS):
                print(f"--- 処理開始: {attachment.filename} ---")

                try:
                    # 1. ファイルをダウンロード
                    file_data = await attachment.read()
                    
                    # 2. 正しい日時を決定
                    target_dt = get_date_from_filename(attachment.filename)
                    source_type = "📂 ファイル名解析"
                    
                    if not target_dt:
                        target_dt = jst_now
                        source_type = "🕒 Discord投稿日時"
                    
                    modified_file_data = file_data
                    
                    # 3. 画像ファイル(JPG)ならEXIF書き換え
                    if attachment.filename.lower().endswith(('.jpg', '.jpeg')):
                        try:
                            exif_time_str = target_dt.strftime("%Y:%m:%d %H:%M:%S")
                            try:
                                exif_dict = piexif.load(file_data)
                            except:
                                exif_dict = {"0th":{}, "Exif":{}, "GPS":{}, "1st":{}, "thumbnail":None}

                            exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = exif_time_str
                            exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = exif_time_str
                            exif_dict['0th'][piexif.ImageIFD.DateTime] = exif_time_str

                            if piexif.ExifIFD.OffsetTimeOriginal in exif_dict['Exif']:
                                del exif_dict['Exif'][piexif.ExifIFD.OffsetTimeOriginal]
                            if piexif.ExifIFD.OffsetTime in exif_dict['Exif']:
                                del exif_dict['Exif'][piexif.ExifIFD.OffsetTime]

                            exif_bytes = piexif.dump(exif_dict)
                            output = BytesIO()
                            piexif.insert(exif_bytes, file_data, output)
                            modified_file_data = output.getvalue()
                            print(f"  ✨ EXIF書き換え成功: {exif_time_str}")
                        except Exception as e:
                            print(f"  ⚠️ EXIF書き換えスキップ: {e}")
                    
                    # 4. アップロード準備
                    naive_iso = target_dt.replace(tzinfo=None).isoformat() + "Z"
                    
                    headers = {
                        'x-api-key': API_KEY,
                        'Accept': 'application/json'
                    }

                    # Immich APIへの送信データ
                    files = {
                        'assetData': (attachment.filename, BytesIO(modified_file_data), attachment.content_type)
                    }

                    data = {
                        'deviceAssetId': f"discord-{attachment.id}",
                        'deviceId': 'discord-bot',
                        'fileCreatedAt': naive_iso,
                        'fileModifiedAt': naive_iso,
                        'isFavorite': 'false'
                    }

                    # 5. 送信
                    response = requests.post(IMMICH_URL, headers=headers, data=data, files=files)

                    if response.status_code in [200, 201]:
                        await message.channel.send(f"✅ 保存完了 ({source_type}): {attachment.filename}")
                    elif response.status_code == 409:
                        await message.channel.send(f"⚠️ 既に保存済みです: {attachment.filename}")
                    else:
                        print(f"エラー: {response.status_code} - {response.text}")
                        await message.channel.send(f"❌ エラー ({response.status_code})")

                except Exception as e:
                    print(f"例外エラー: {e}")
                    await message.channel.send(f"❌ プログラムエラー: {e}")

client.run(DISCORD_TOKEN)
