import os
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from logger import logger
from data.database import SessionLocal
from data.models import TopicMemory
import random

def get_fallback_comment(topic: str) -> str:
    """Mengambil komentar fallback. Idealnya dari database statis, tapi karena
    tabel komentar statis belum ada, kita ambil topik dari DB jika memungkinkan,
    atau gunakan fallback default."""
    session = SessionLocal()
    try:
        # Pura-pura kita ambil data statis dari DB (misalnya mencari apakah topik ada di DB)
        topic_data = session.query(TopicMemory).filter(TopicMemory.name == topic).first()
        topic_name = topic_data.name if topic_data else topic

        fallbacks = [
            f"Teori sih gampang, tapi di lapangan soal {topic_name} gak seindah itu ngab. Ada pendapat lain? 👇",
            f"Menurut gue sih {topic_name} ini agak overated ya. Kalian ada yang pro gak sama video ini? Coba komen!",
            f"Setuju gak sih sama statement soal {topic_name} di video ini? Atau malah sebaliknya? Tulis dong opini kalian!"
        ]
        return random.choice(fallbacks)
    except Exception as e:
        logger.error(f"❌ Gagal mengambil fallback dari database: {e}")
        return f"Gimana pendapat kalian soal {topic}? Komen di bawah ya! 👇"
    finally:
        session.close()

def generate_provocative_comment(transcript_text: str, topic: str) -> str:
    """Menghasilkan komentar provokatif menggunakan LangChain dan OpenAI."""
    logger.info(f"🧠 Memulai generasi komentar provokatif LangChain untuk topik: {topic}")

    # Ambil API key dari environment atau gunakan dummy jika belum diset
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        logger.warning("⚠️ OPENAI_API_KEY tidak ditemukan. Menggunakan fallback dari database.")
        return get_fallback_comment(topic)

    try:
        llm = ChatOpenAI(temperature=0.7, model_name="gpt-3.5-turbo", max_retries=2, request_timeout=15)

        template = """Kamu adalah seorang social media manager yang sangat ahli memancing engagement di Indonesia. Berikut adalah transkrip singkat dari sebuah video pendek tentang topik {topic}:

Transkrip: {transcript}

Tugasmu: Buat SATU komentar pertama (maksimal 2 kalimat) dalam bahasa Indonesia gaul/kasual yang bersifat provokatif, mengambil sikap (bisa setuju atau sedikit meragukan isi video), dan WAJIB diakhiri dengan pertanyaan menantang yang memaksa penonton lain untuk membalas/berdebat.
Jangan gunakan hashtag. Jangan terlihat seperti bot."""

        prompt = PromptTemplate(
            template=template,
            input_variables=["topic", "transcript"]
        )

        chain = prompt | llm | StrOutputParser()

        # Potong transkrip agar tidak terlalu panjang (menghindari token berlebih)
        short_transcript = transcript_text[:1000] if len(transcript_text) > 1000 else transcript_text

        comment = chain.invoke({"topic": topic, "transcript": short_transcript})

        logger.info(f"✅ Komentar provokatif berhasil digenerate: {comment}")
        return comment

    except Exception as e:
        logger.error(f"❌ Gagal menghasilkan komentar via LangChain: {e}")
        return get_fallback_comment(topic)
