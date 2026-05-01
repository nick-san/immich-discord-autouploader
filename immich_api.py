import aiohttp
import asyncio
from config import API_KEY, IMMICH_URL

async def upload_to_immich(session, attachment, file_data, target_dt, source_type):
    """Immich APIへマルチパートアップロードを実行"""
    # Immichは末尾にZをつけたUTC形式を期待する
    naive_iso = target_dt.replace(tzinfo=None).isoformat() + "Z"
    
    headers = {
        'x-api-key': API_KEY,
        'Accept': 'application/json'
    }

    form_data = aiohttp.FormData()
    form_data.add_field('deviceAssetId', f"discord-{attachment.id}")
    form_data.add_field('deviceId', 'discord-bot')
    form_data.add_field('fileCreatedAt', naive_iso)
    form_data.add_field('fileModifiedAt', naive_iso)
    form_data.add_field('isFavorite', 'false')
    form_data.add_field('assetData', file_data, 
                        filename=attachment.filename, 
                        content_type=attachment.content_type)

    try:
        # 通信全体のタイムアウト設定
        timeout = aiohttp.ClientTimeout(total=300, connect=10)
        async with session.post(IMMICH_URL, headers=headers, data=form_data, timeout=timeout) as response:
            if response.status in [200, 201]:
                return True, f"✅ 保存完了 ({source_type}): {attachment.filename}"
            elif response.status == 409:
                return True, f"⚠️ 既に保存済みです: {attachment.filename}"
            else:
                resp_text = await response.text()
                return False, f"❌ Immichエラー ({response.status}): {resp_text}"
    except asyncio.TimeoutError:
        return False, f"❌ タイムアウト: Immichからの応答が300秒間ありませんでした"
    except Exception as e:
        return False, f"❌ 通信エラー: {e}"
