"""
core/comment_generator.py
==========================
Generator komentar provokatif menggunakan LangChain + Groq.

Mode Hybrid LLM:
  - Normal         → llama-3.1-8b-instant (Super cepat, 560 T/s)
  - is_aggressive  → llama-3.3-70b-versatile (Intelijensi tinggi untuk manipulasi emosi)
"""

import os
import random
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from logger import logger
from data.mongodb_client import db
from pydantic import SecretStr


def get_fallback_comment(topic: str, is_aggressive: bool = False) -> str:
    """Komentar cadangan dari template lokal jika LLM gagal atau rate limit."""
    try:
        topic_data = db["topics"].find_one({"name": topic})
        topic_name = topic_data.get("name", topic) if topic_data else topic

        if is_aggressive:
            fallbacks = [
                f"⚠️ Jujur aja, orang yang percaya sama {topic_name} itu biasanya belum baca data aslinya. Coba kasih gue satu bukti konkret yang gak bisa gue bantah? 👇",
                f"🔥 Konten soal {topic_name} ini terlalu diperhalus. Kenyataannya jauh lebih brutal. Kalian berani dengerin versi yang sebenarnya nggak?",
                f"Teori soal {topic_name} ini kedengarannya bagus di atas kertas. Tapi siapa di sini yang udah buktiin sendiri dan hasilnya beda 180 derajat? Gue tunggu. 👇",
            ]
        else:
            fallbacks = [
                f"Teori sih gampang, tapi di lapangan soal {topic_name} gak seindah itu ngab. Ada pendapat lain? 👇",
                f"Menurut gue sih {topic_name} ini agak overated ya. Kalian ada yang pro gak sama video ini? Coba komen!",
                f"Setuju gak sih sama statement soal {topic_name} di video ini? Atau malah sebaliknya? Tulis dong opini kalian!",
            ]
        return random.choice(fallbacks)

    except Exception as e:
        logger.error(f"❌ Gagal mengambil fallback dari MongoDB: {e}")
        return f"Gimana pendapat kalian soal {topic}? Komen di bawah ya! 👇"


def generate_provocative_comment(
    transcript_text: str,
    topic: str,
    is_aggressive: bool = False,
) -> str:
    """
    Menghasilkan komentar provokatif menggunakan LangChain dan Groq dengan Dynamic Model Routing.
    """
    # PEMILIHAN MODEL DINAMIS BERDASARKAN MODE ALGORITMA
    model_id = "llama-3.3-70b-versatile" if is_aggressive else "llama-3.1-8b-instant"
    mode_label = "🔥 AGGRESSIVE (70B)" if is_aggressive else "💬 Normal (8B Instant)"

    logger.info(f"🧠 [{mode_label}] Generasi komentar LangChain untuk topik: '{topic}'")

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        logger.warning("⚠️ GROQ_API_KEY tidak ditemukan. Menggunakan fallback.")
        return get_fallback_comment(topic, is_aggressive)

    try:
        # Temperature dinaikkan di mode agresif untuk variasi kalimat yang lebih natural/chaos
        temperature = 0.95 if is_aggressive else 0.8

        # Inisialisasi Groq dengan model pilihan
        llm = ChatGroq(
            temperature=temperature,
            model=model_id,
            max_retries=2,
            timeout=15,
            api_key=SecretStr(api_key),
        )

        if is_aggressive:
            template = """\
Kamu adalah seorang influencer kontroversial Indonesia yang terkenal sangat berani menyatakan pendapat \
yang bertentangan dengan opini mainstream. Gaya bicaramu direct, sedikit provokatif, dan selalu memancing \
orang untuk membela diri atau berdebat.

Topik video: {topic}
Transkrip singkat: {transcript}

TUGASMU: Tulis SATU komentar pertama (2-3 kalimat MAKSIMAL) dalam bahasa Indonesia gaul/kasual yang:
1. LANGSUNG menyerang atau menantang opini umum tentang {topic} — jangan basa-basi
2. Buat penonton merasa TERTANTANG secara personal (gunakan "lu", "kalian", atau "siapa yang berani")
3. WAJIB diakhiri dengan pertanyaan konfrontatif yang memaksa penonton untuk membuktikan diri atau membela opini mereka
4. Boleh pakai 1-2 emoji yang relevan (⚠️ 🔥 😤 💀) tapi JANGAN berlebihan
5. Jangan terlihat seperti bot. Jangan formal. Jangan pakai hashtag.

Output hanya komentar saja, tanpa penjelasan apapun."""
        else:
            template = """\
Kamu adalah seorang social media manager yang sangat ahli memancing engagement di Indonesia. \
Berikut adalah transkrip singkat dari sebuah video pendek tentang topik {topic}:

Transkrip: {transcript}

Tugasmu: Buat SATU komentar pertama (maksimal 2 kalimat) dalam bahasa Indonesia gaul/kasual yang:
1. Mengambil sikap provokatif terhadap isi video.
2. WAJIB diakhiri dengan kalimat yang membocorkan bahwa kamu akan membahas hal yang LEBIH GILA di video selanjutnya, dan menyuruh mereka untuk Follow/Subscribe.
Contoh akhiran: "Di video besok gue bakal bongkar rahasia yang lebih parah. Follow biar nggak ketinggalan!"
Jangan gunakan hashtag. Jangan terlihat seperti bot."""

        prompt = PromptTemplate(
            template=template, input_variables=["topic", "transcript"]
        )
        chain = prompt | llm | StrOutputParser()

        # Potong transkrip agar tidak melebihi konteks batas atas (meskipun Llama 3 punya 131k context window)
        short_transcript = (
            transcript_text[:1000] if len(transcript_text) > 1000 else transcript_text
        )

        comment = chain.invoke({"topic": topic, "transcript": short_transcript})
        comment = comment.strip()

        logger.info(
            f"✅ Komentar [{mode_label}] berhasil digenerate: {comment[:80]}..."
        )
        return comment

    except Exception as e:
        logger.error(f"❌ Gagal menghasilkan komentar via LangChain ({model_id}): {e}")
        return get_fallback_comment(topic, is_aggressive)
