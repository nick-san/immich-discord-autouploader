import aiohttp
import asyncio
import config  # config全体をインポートして柔軟に値を読み込めるようにします

async def upload_to_immich(session, attachment, file_data, target_dt, source_type):
    """Immich APIへマルチパートアップロードを実行 (Cloudflare Access & タイムアウト最適化版)"""
    naive_iso = target_dt.replace(tzinfo=None).isoformat() + "Z"
    
    # 基本のヘッダー設定
    headers = {
        'x-api-key': config.API_KEY,
        'Accept': 'application/json'
    }

    # .env に Cloudflare Access の設定がある場合のみ、ヘッダーに自動追加
    if config.CF_CLIENT_ID and config.CF_CLIENT_SECRET:
        headers['CF-Access-Client-Id'] = config.CF_CLIENT_ID
        headers['CF-Access-Client-Secret'] = config.CF_CLIENT_SECRET

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
        # 524 Timeout (100秒制限) 回避のため、totalを90秒に設定
        timeout = aiohttp.ClientTimeout(total=90, connect=10, sock_read=30)
        
        async with session.post(config.IMMICH_URL, headers=headers, data=form_data, timeout=timeout) as response:
            if response.status in [200, 201]:
                return True, f"✅ 保存完了 ({source_type}): {attachment.filename}"
            elif response.status == 409:
                return True, f"⚠️ 既に保存済みです: {attachment.filename}"
            elif response.status == 403:
                return False, f"❌ Cloudflare Access 認証エラー (403): クライアントIDまたはシークレットが正しくないか、設定されていません。"
            elif response.status == 524:
                return False, f"❌ Cloudflareタイムアウト (524): Immichサーバーの処理が100秒を超えました。"
            else:
                resp_text = await response.text()
                return False, f"❌ Immichエラー ({response.status}): {resp_text}"
                
    except asyncio.TimeoutError:
        return False, f"❌ タイムアウト: CloudflareまたはImmichからの応答が時間内にありませんでした"
    except Exception as e:
        return False, f"❌ 通信エラー: {e}"
