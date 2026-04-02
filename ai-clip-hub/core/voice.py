import os
import uuid
from logger import logger
from elevenlabs.client import ElevenLabs

# ==============================================================================
# ⚠️ PENTING UNTUK USER ⚠️
# Anda WAJIB menaruh ElevenLabs API Key sebagai environment variable
# `ELEVENLABS_API_KEY` agar fitur Voice-Over AI berfungsi.
# ==============================================================================

class VoiceEngine:
    def __init__(self, output_dir="data/output/audio"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        # Akan otomatis mencoba baca dari env var ELEVENLABS_API_KEY
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            logger.warning("⚠️ ELEVENLABS_API_KEY tidak ditemukan! Voice-Over AI tidak akan berbunyi.")

    def generate_hook_audio(self, text: str) -> str:
        """
        Merender Voice-Over menggunakan ElevenLabs API untuk ~3 detik pertama.
        Mengembalikan path file .mp3 jika berhasil, None jika gagal.
        """
        if not self.api_key:
            return None

        logger.info(f"🎙️ Merender Voice-Over AI Hook: '{text}'")
        output_filename = f"hook_{uuid.uuid4().hex[:6]}.mp3"
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            # Gunakan Voice ID Adam (atau suara populer lain)
            # Default ID Adam: pNInz6obpgDQGcFmaJcg
            audio = generate(
                api_key=self.api_key,
                text=text,
                voice=Voice(
                    voice_id='pNInz6obpgDQGcFmaJcg',
                    settings=VoiceSettings(stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=True)
                ),
                model="eleven_multilingual_v2" # Multibahasa termasuk Indonesia (v2)
            )

            save(audio, output_path)
            logger.info(f"✅ Voice-Over AI berhasil di-render: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"❌ Gagal merender Voice-Over ElevenLabs: {e}")
            return None

voice_engine = VoiceEngine()
