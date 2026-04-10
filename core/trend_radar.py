import feedparser
from langchain_groq import ChatGroq
from data.mongodb_client import db
from logger import logger

def scan_trending_topics():
    """Memantau berita viral dari RSS Feed Indonesia."""
    feeds = [
        "https://www.antaranews.com/rss/top-news.xml",
        "https://rss.detik.com/index.php/detikcom"
    ]
    
    trends = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # Ambil 5 berita teratas
                trends.append({"title": entry.title, "summary": entry.summary})
        except Exception as e:
            logger.error(f"Failed to parse RSS {url}: {e}")
    return trends

def match_trend_with_user_niche(user_id):
    """Mencocokkan tren internet dengan minat khusus (niche) user."""
    user = db.users.find_one({"_id": user_id})
    if not user:
        return None
        
    user_niche = user.get("niche_keywords", ["bisnis", "motivasi", "edukasi"])
    trends = scan_trending_topics()
    
    if not trends:
        return None
        
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1)
    
    prompt = f"""
    Berita Tren: {trends}
    Minat User: {user_niche}
    Pilih satu berita yang paling bisa dibuat video konten menarik sesuai minat user. 
    Jika tidak ada yang cocok, jawab 'NONE'. Jika ada, berikan judul beritanya saja (maksimal 1 kalimat).
    """
    
    try:
        selected_trend = str(llm.invoke(prompt).content).strip()
        return None if "NONE" in selected_trend.upper() else selected_trend
    except Exception as e:
        logger.error(f"Error LLM trend mapping: {e}")
        return None
