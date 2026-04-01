import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import random
from logger import logger

def get_trending_topic() -> str:
    """
    Mengambil topik viral terbaru dari Google News RSS berbahasa Indonesia (24 jam terakhir).
    Niche: crypto, saham, AI, atau bisnis.
    """
    url = "https://news.google.com/rss/search?q=crypto+OR+saham+OR+AI+OR+bisnis+when:1d&hl=id&gl=ID&ceid=ID:id"
    logger.info("🕵️‍♂️ AI Researcher sedang memindai tren terbaru di Google News...")

    # Header minimalis untuk bypass pembatasan ringan
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0'}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()

        # Parse XML RSS Feed
        root = ET.fromstring(xml_data)

        headlines = []
        # Item biasanya ada di dalam <channel>
        for item in root.findall('./channel/item'):
            title = item.find('title')
            if title is not None and title.text:
                headlines.append(title.text)

        if not headlines:
            raise ValueError("Tidak ada headline yang ditemukan di RSS feed.")

        # Ambil 15 teratas
        top_headlines = headlines[:15]

        # Pilih satu secara acak
        chosen_headline = random.choice(top_headlines)

        # Bersihkan judul dari nama media (biasanya dipisahkan dengan " - ")
        # Contoh: "Harga Bitcoin Tembus Rekor Baru - Kompas.com" -> "Harga Bitcoin Tembus Rekor Baru"
        if " - " in chosen_headline:
            chosen_topic = chosen_headline.rsplit(" - ", 1)[0].strip()
        else:
            chosen_topic = chosen_headline.strip()

        logger.info(f"💡 AI Researcher menemukan topik viral: '{chosen_topic}'")
        return chosen_topic

    except (urllib.error.URLError, ET.ParseError, ValueError, Exception) as e:
        logger.error(f"❌ AI Researcher gagal mengakses RSS Feed: {e}")
        fallback_topic = "Peluang Bisnis AI Terbaru"
        logger.warning(f"⚠️ Menggunakan topik fallback: '{fallback_topic}'")
        return fallback_topic
