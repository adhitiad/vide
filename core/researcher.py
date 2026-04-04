import random
import requests
import urllib3
import re
import xml.etree.ElementTree as ET
from logger import logger

# Nonaktifkan peringatan SSL Request Tidak Aman
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _get_google_news_fallback() -> str:
    """Fallback ke RSS Google News dengan penanganan error yang lebih baik."""
    # Variasikan query untuk menghindari deteksi pattern yang membosankan
    queries = [
        "teknologi+terbaru",
        "kecerdasan+buatan+masa+depan",
        "breaking+news+indonesia+viral",
        "gadget+canggih+2024",
        "startup+sukses+jakarta",
    ]
    query = random.choice(queries)
    url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"

    logger.info(f"🕵️‍♂️ Fallback: Memindai RSS Google News ({query})...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()

        # Cek jika konten kosong atau bukan XML
        if not response.text or "<rss" not in response.text.lower():
            raise ValueError("Respon bukan XML/RSS valid.")

        root = ET.fromstring(response.text)
        headlines = []
        for item in root.findall("./channel/item"):
            title_node = item.find("title")
            if title_node is not None and title_node.text:
                headlines.append(str(title_node.text))

        if not headlines:
            raise ValueError("Tidak ada headline yang ditemukan.")

        chosen = random.choice(headlines[:10])
        # Bersihkan sumber berita di akhir judul (misal: "Judul - Detikcom")
        clean_title = (
            chosen.rsplit(" - ", 1)[0].strip() if " - " in chosen else chosen.strip()
        )
        return clean_title

    except Exception as e:
        logger.error(f"❌ Fallback Google News Gagal: {e}")
        # Final Fallback: Hot Topics Manusiawi (Evergreen)
        evergreen_topics = [
            "Cara Cerdas Mengatur Keuangan di Usia Muda",
            "Masa Depan AI: Apakah Mengancam Pekerjaan Kita?",
            "Tips Sukses Startup Tanpa Modal Besar",
            "Perang Teknologi: Mengapa Chip Menjadi Harta Karun?",
            "Rahasia Psikologi di Balik Viralitas Konten Media Sosial",
        ]
        topic = random.choice(evergreen_topics)
        logger.info(f"🛡️ Menggunakan Topik Evergreen: '{topic}'")
        return topic


def get_trending_topic() -> str:
    """
    Crystal Ball Trend Predictor 🔮
    Mengambil topik viral dari Reddit JSON publik.
    Jika gagal (sering terjadi di Indonesia krn Internet Positif), beralih ke News RSS.
    """
    logger.info("🔮 Crystal Ball Predictor memindai tren Reddit...")

    # Subreddit yang relevan dengan niche AI/Tech/Bisnis
    subreddits = ["indonesia", "finansial", "technology", "artificial", "programming"]
    chosen_sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{chosen_sub}/top.json?limit=25&t=day"

    # User-Agent harus terlihat seperti real browser agar tidak diblokir CDN Reddit
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Cache-Control": "no-cache",
    }

    target_keywords = [
        "kripto",
        "saham",
        "ai",
        "hot",
        "sensasi",
        "viral",
        "trending",
        "programming",
        "tech",
        "bisnis",
        "bitcoin",
        "programming",
        "teknologi",
        "viral",
    ]
    pattern = re.compile(
        r"\b(?:" + "|".join(map(re.escape, target_keywords)) + r")\b", re.IGNORECASE
    )

    try:
        # verify=False penting untuk lingkungan dengan injeksi DNS (Internet Positif)
        response = requests.get(url, headers=headers, timeout=12, verify=False)
        response.raise_for_status()

        data = response.json()
        posts = data.get("data", {}).get("children", [])

        if not posts:
            raise ValueError("JSON Reddit tidak berisi postingan.")

        parsed_posts = []
        for p in posts:
            p_data = p.get("data", {})
            title = p_data.get("title", "")
            num_comments = p_data.get("num_comments", 0)

            # Jika subreddit luar, biarkan AI memproses (bisa ditranslate otomatis oleh prompt nanti)
            # Di sini kita filter berdasarkan keyword agar relevan dengan niche
            if pattern.search(title) or chosen_sub in ["indonesia", "finansial"]:
                parsed_posts.append((title, num_comments))

        if parsed_posts:
            # Utamakan yang memancing engagement terbanyak
            parsed_posts.sort(key=lambda x: x[1], reverse=True)
            chosen_topic = parsed_posts[0][0]
            logger.info(
                f"💡 Reddit Predictor: '{chosen_topic}' ({parsed_posts[0][1]} Komentar)"
            )
            return chosen_topic

        logger.warning(
            "⚠️ Tidak ada tren Reddit yang spesifik. Pindah ke Google News..."
        )
        return _get_google_news_fallback()

    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, "status_code", "TIMEOUT")
        logger.warning(
            f"⚠️ Reddit Kendala (Code: {status_code}). Alasan: {type(e).__name__}. Melompat ke Fallback..."
        )
        return _get_google_news_fallback()
    except Exception as e:
        logger.error(f"❌ Kesalahan Researcher: {e}")
        return _get_google_news_fallback()
