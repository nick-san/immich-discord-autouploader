import re
import piexif
from io import BytesIO
from datetime import timezone, timedelta, datetime
from dateutil import parser

JST = timezone(timedelta(hours=9), 'JST')

def get_date_from_filename(filename):
    """ファイル名から日時を抽出する"""
    # Google Pixel 形式 (PXL_YYYYMMDD_HHMMSS)
    pixel_pattern = r'PXL_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})'
    match = re.search(pixel_pattern, filename)
    if match:
        try:
            y, m, d, H, M, S = map(int, match.groups())
            dt_utc = datetime(y, m, d, H, M, S, tzinfo=timezone.utc)
            return dt_utc.astimezone(JST)
        except ValueError:
            pass

    # その他の形式をdateutilで試行
    try:
        dt = parser.parse(filename, fuzzy=True)
        current_year = datetime.now().year + 1
        if 1990 <= dt.year <= current_year:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            return dt
    except (ValueError, OverflowError):
        pass

    return None

def update_exif(file_data, target_dt):
    """JPGバイナリのEXIF日時を書き換える"""
    exif_time_str = target_dt.strftime("%Y:%m:%d %H:%M:%S")
    
    try:
        try:
            exif_dict = piexif.load(file_data)
        except:
            exif_dict = {"0th":{}, "Exif":{}, "GPS":{}, "1st":{}, "thumbnail":None}

        # 日時情報の更新
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = exif_time_str
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = exif_time_str
        exif_dict['0th'][piexif.ImageIFD.DateTime] = exif_time_str

        # タイムゾーンオフセットを削除（Immich側での誤判定を防ぐため）
        exif_dict['Exif'].pop(piexif.ExifIFD.OffsetTimeOriginal, None)
        exif_dict['Exif'].pop(piexif.ExifIFD.OffsetTime, None)

        exif_bytes = piexif.dump(exif_dict)
        output = BytesIO()
        piexif.insert(exif_bytes, file_data, output)
        return output.getvalue(), exif_time_str
    except Exception as e:
        raise RuntimeError(f"EXIF書き換え失敗: {e}")
