import discord
import aiohttp
from datetime import datetime
import config
import image_utils
import immich_api

# Discordクライアントの初期化
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'[{datetime.now()}] ログインしました: {client.user}')

@client.event
async def on_message(message):
    # 自分自身のメッセージや、指定チャンネル以外を無視
    if message.author == client.user or message.channel.id != config.TARGET_CHANNEL_ID:
        return

    # メッセージに添付ファイルがない場合は無視
    if not message.attachments:
        return

    # メッセージ受信時のJST時刻を取得
    jst_now = message.created_at.astimezone(image_utils.JST)

    # 非同期セッションの開始
    async with aiohttp.ClientSession() as session:
        for attachment in message.attachments:
            # 拡張子チェック
            if not any(attachment.filename.lower().endswith(ext) for ext in config.TARGET_EXTENSIONS):
                continue

            print(f"[{datetime.now()}] --- 処理開始: {attachment.filename} ---")

            try:
                # 1. ダウンロード
                file_data = await attachment.read()
                
                # 2. 日時の決定
                target_dt = image_utils.get_date_from_filename(attachment.filename)
                source_type = "📂 ファイル名解析"
                
                if not target_dt:
                    target_dt = jst_now
                    source_type = "🕒 Discord投稿日時"
                
                # 3. EXIF書き換え (JPGのみ)
                modified_data = file_data
                if attachment.filename.lower().endswith(config.IMAGE_EXTENSIONS):
                    try:
                        modified_data, time_str = image_utils.update_exif(file_data, target_dt)
                        print(f"  ✨ EXIF書き換え成功: {time_str}")
                    except Exception as e:
                        print(f"  ⚠️ EXIF書き換えスキップ: {e}")
                
                # 4. アップロード実行
                success, result_msg = await immich_api.upload_to_immich(
                    session, attachment, modified_data, target_dt, source_type
                )
                
                print(f"[{datetime.now()}] {result_msg}")
                await message.channel.send(result_msg)

            except Exception as e:
                err_msg = f"❌ システムエラー ({attachment.filename}): {e}"
                print(err_msg)
                await message.channel.send(err_msg)

if __name__ == "__main__":
    client.run(config.DISCORD_TOKEN)
