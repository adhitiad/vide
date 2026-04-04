import yt_dlp
import traceback

def test():
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'match_filter': yt_dlp.utils.match_filter_func("duration > 60 and duration <= 1200"),
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info("ytsearch5:harga bitcoin opini podcast indonesia", download=False)
            entries = [e for e in info.get('entries', []) if e is not None]
            print(f"Got {len(entries)} entries")
            for e in entries:
                print(e.get('title'), e.get('duration'), e.get('view_count'), e.get('upload_date'))
        except Exception as e:
            traceback.print_exc()
test()
