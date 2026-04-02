import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import random
import requests
import re
from logger import logger

def _get_google_news_fallback() -> str:
    """Fallback ke fungsi RSS Google News ID lama."""
    url = "https://news.google.com/rss/search?q=kripto+OR+bitcoin+OR+saham+global+OR+artificial+intelligence+OR+teknologi+when:1d&hl=id&gl=ID&ceid=ID:id"
    logger.info("🕵️‍♂️ Fallback: Memindai RSS Google News...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)

        headlines = [item.find('title').text for item in root.findall('./channel/item') if item.find('title') is not None]
        if not headlines:
            raise ValueError("Tidak ada headline di RSS.")

        chosen = random.choice(headlines[:15])
        return chosen.rsplit(" - ", 1)[0].strip() if " - " in chosen else chosen.strip()
    except Exception as e:
        logger.error(f"❌ Fallback Google News Gagal: {e}")
        return "Berita Teknologi dan Startup Terbaru"

def get_trending_topic() -> str:
    """
    Crystal Ball Trend Predictor 🔮
    Mengambil topik viral dari Reddit JSON publik (r/indonesia atau r/finansial).
    Memfilter judul berdasarkan kata kunci target dan memilih postingan dengan komentar terbanyak.
    """
    logger.info("🔮 Crystal Ball Predictor memindai tren Reddit...")

    # Pilih subreddit secara acak
    subreddits = ["indonesia", "finansial"]
    chosen_sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{chosen_sub}/top.json?limit=25&t=day"

    # Header wajib agar tidak terkena Rate Limit / Error 429
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Clipper-Bot/1.0'
    }

    target_keywords = ["kripto", "saham", "ai", "programming", "tech", "viral", "bisnis", "bitcoin", "uang"]

    # Gunakan Regex Word Boundary (\b) untuk mencegah false positive (contoh: "baik" terhitung "ai")
    pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, target_keywords)) + r')\b', re.IGNORECASE)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Lempar error jika HTTP status code bukan 200

        data = response.json()
        posts = data.get("data", {}).get("children", [])

        if not posts:
            raise ValueError("Data JSON Reddit kosong.")

        # Ekstrak data yang relevan: judul dan jumlah komentar
        parsed_posts = []
        for p in posts:
            p_data = p.get("data", {})
            title = p_data.get("title", "")
            num_comments = p_data.get("num_comments", 0)

            # Filter menggunakan pola regex
            if pattern.search(title):
                parsed_posts.append((title, num_comments))

        # Urutkan berdasarkan komentar terbanyak (komunitas paling aktif berdiskusi)
        parsed_posts.sort(key=lambda x: x[1], reverse=True)

        if parsed_posts:
            # Ambil yang paling viral (komentar tertinggi)
            chosen_topic = parsed_posts[0][0]
            logger.info(f"💡 Reddit Predictor menemukan topik panas: '{chosen_topic}' ({parsed_posts[0][1]} Komentar)")
            return chosen_topic
        else:
            logger.warning("⚠️ Tidak ada tren Reddit yang cocok dengan kata kunci target.")
            return _get_google_news_fallback()

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Gagal mengambil data Reddit: {e}")
        return _get_google_news_fallback()
    except Exception as e:
        logger.error(f"❌ Kesalahan saat memparsing Reddit: {e}")
        return _get_google_news_fallback()
