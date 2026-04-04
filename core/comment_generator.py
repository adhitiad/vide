"""
core/comment_generator.py
==========================
Generator komentar provokatif menggunakan LangChain + Groq.

Mode:
  - Normal         → Komentar provokatif standar, memancing debat halus
  - is_aggressive  → Mode Self-Correction: prompt ultra-konfrontatif, menyerang opini umum,
                     diaktifkan otomatis oleh RL environment saat video sebelumnya LOW_VIEWS
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
    """Komentar cadangan dari template lokal jika LLM tidak tersedia."""
    try:
        topic_data = db["topics"].find_one({"name": topic})
        topic_name = topic_data.get("name", topic) if topic_data else topic

        if is_aggressive:
            # Template agresif: langsung menyerang, memancing emosi kuat
            fallbacks = [
                f"⚠️ Jujur aja, orang yang percaya sama {topic_name} itu biasanya belum baca data aslinya. "
                f"Coba kasih gue satu bukti konkret yang gak bisa gue bantah? 👇",

                f"🔥 Konten soal {topic_name} ini terlalu diperhalus. "
                f"Kenyataannya jauh lebih brutal. Kalian berani dengerin versi yang sebenarnya nggak?",

                f"Teori soal {topic_name} ini kedengarannya bagus di atas kertas. "
                f"Tapi siapa di sini yang udah buktiin sendiri dan hasilnya beda 180 derajat? Gue tunggu. 👇",
            ]
        else:
            # Template normal: provokatif tapi sopan
            fallbacks = [
                f"Teori sih gampang, tapi di lapangan soal {topic_name} gak seindah itu ngab. "
                f"Ada pendapat lain? 👇",

                f"Menurut gue sih {topic_name} ini agak overated ya. "
                f"Kalian ada yang pro gak sama video ini? Coba komen!",

                f"Setuju gak sih sama statement soal {topic_name} di video ini? "
                f"Atau malah sebaliknya? Tulis dong opini kalian!",
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
    Menghasilkan komentar provokatif menggunakan LangChain dan Groq.

    Args:
        transcript_text : Transkrip video (dipotong ke 1000 karakter)
        topic           : Topik utama video
        is_aggressive   : Jika True, gunakan prompt ultra-konfrontatif (Self-Correction Mode)
                          Diaktifkan oleh clipper_env.py saat video sebelumnya LOW_VIEWS.

    Returns:
        String komentar yang siap di-post sebagai first comment di YouTube/IG.
    """
    mode_label = "🔥 AGGRESSIVE" if is_aggressive else "💬 Normal"
    logger.info(
        f"🧠 [{mode_label}] Generasi komentar LangChain untuk topik: '{topic}'"
    )

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        logger.warning("⚠️ GROQ_API_KEY tidak ditemukan. Menggunakan fallback.")
        return get_fallback_comment(topic, is_aggressive)

    try:
        # Temperature lebih tinggi untuk mode agresif agar output lebih tidak terduga
        temperature = 0.95 if is_aggressive else 0.8

        llm = ChatGroq(
            temperature=temperature,
            model="llama-3.3-70b-versatile",
            max_retries=2,
            timeout=15,
            api_key=SecretStr(api_key),
        )

        if is_aggressive:
            # ── PROMPT MODE AGRESIF ──────────────────────────────────────────────
            # Instruksi keras: komentar yang langsung menyerang opini umum,
            # menantang penonton secara personal, dan memaksa mereka membalas.
            # Tujuan: spike engagement di jam pertama agar algoritma memberikan boost.
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
            # ── PROMPT MODE NORMAL ───────────────────────────────────────────────
            template = """\
Kamu adalah seorang social media manager yang sangat ahli memancing engagement di Indonesia. \
Berikut adalah transkrip singkat dari sebuah video pendek tentang topik {topic}:

Transkrip: {transcript}

Tugasmu: Buat SATU komentar pertama (maksimal 2 kalimat) dalam bahasa Indonesia gaul/kasual \
yang bersifat provokatif, mengambil sikap (bisa setuju atau sedikit meragukan isi video), \
dan WAJIB diakhiri dengan pertanyaan menantang yang memaksa penonton lain untuk membalas/berdebat.
Jangan gunakan hashtag. Jangan terlihat seperti bot."""

        prompt = PromptTemplate(
            template=template, input_variables=["topic", "transcript"]
        )
        chain = prompt | llm | StrOutputParser()

        # Potong transkrip agar tidak melebihi token limit
        short_transcript = (
            transcript_text[:1000] if len(transcript_text) > 1000 else transcript_text
        )

        comment = chain.invoke({"topic": topic, "transcript": short_transcript})
        comment = comment.strip()

        logger.info(f"✅ Komentar [{mode_label}] berhasil digenerate: {comment[:80]}...")
        return comment

    except Exception as e:
        logger.error(f"❌ Gagal menghasilkan komentar via LangChain: {e}")
        return get_fallback_comment(topic, is_aggressive)
