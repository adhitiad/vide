import random
import time
import os
from playwright.sync_api import sync_playwright
from logger import logger

class FacebookUploader:
    """
    Facebook Reels Uploader menggunakan Playwright (Browser Automation).
    Strategi non-resmi yang dipoles dengan mekanisme retry dan anti-bot.
    """

    def __init__(self):
        self.user_data_dir = os.path.join(os.getcwd(), "data", "fb_session")
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.upload_url = "https://www.facebook.com/reels/create/"
        
        # List of modern User Agents for rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]

    def upload_to_facebook(self, video_path: str, caption: str, max_retries: int = 3) -> bool:
        """
        Upload video ke Facebook Reels dengan mekanisme retry otomatis.
        """
        for attempt in range(1, max_retries + 1):
            logger.info(f"💙 Memulai upload Facebook (Percobaan {attempt}/{max_retries}): {os.path.basename(video_path)}")
            
            try:
                if self._execute_upload(video_path, caption):
                    return True
            except Exception as e:
                logger.error(f"⚠️ Percobaan {attempt} gagal: {e}")
            
            if attempt < max_retries:
                wait_time = attempt * 10
                logger.warning(f"🔄 Menunggu {wait_time} detik sebelum mencoba lagi...")
                time.sleep(wait_time)
        
        logger.error(f"❌ Facebook Upload gagal total setelah {max_retries} percobaan.")
        return False

    def _execute_upload(self, video_path: str, caption: str) -> bool:
        if not os.path.exists(video_path):
            logger.error(f"❌ File tidak ditemukan: {video_path}")
            return False

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=True, # Dapat diubah menjadi False jika butuh intervensi manual
                user_agent=random.choice(self.user_agents),
                viewport={'width': 1280, 'height': 800},
                ignore_https_errors=True
            )

            page = browser.new_page()
            
            try:
                # 1. Navigasi
                page.goto(self.upload_url, wait_until="networkidle", timeout=60000)
                
                # Cek Deteksi Login
                if "login" in page.url or page.locator("input[name='email']").count() > 0:
                    # Jika headless, kita tidak bisa login manual. Gagal saja.
                    logger.error("🚨 Sesi Facebook berakhir. Harap jalankan manual (headless=False) untuk login ulang.")
                    return False
                
                # 2. Input File
                logger.info("📁 Mengunggah file...")
                page.set_input_files('input[type="file"]', video_path)

                # 3. Tunggu Tombol Next (Upload selesai)
                # Facebook butuh waktu untuk processing video sebelum tombol aktif
                next_selector = "div[aria-label='Next'], span:has-text('Next')"
                page.wait_for_selector(next_selector, state="visible", timeout=120000)
                
                # Klik Next bertahap (biasanya ada 2-3 langkah)
                for _ in range(2):
                    btn = page.locator(next_selector).first
                    if btn.is_visible():
                        btn.click()
                        time.sleep(random.uniform(2, 3))

                # 4. Teks Deskripsi
                logger.info("✍️ Menambahkan caption...")
                caption_box = page.locator("div[role='textbox']").first
                if caption_box.is_visible():
                    caption_box.click()
                    page.keyboard.type(caption, delay=random.randint(50, 100))
                
                time.sleep(random.uniform(2, 4))

                # 5. Publikasi Final
                logger.info("🚀 Mengklik tombol Publish...")
                publish_btn = page.locator("div[aria-label='Publish'], span:has-text('Publish')").first
                if publish_btn.is_visible() and publish_btn.is_enabled():
                    publish_btn.click()
                    
                    # Verifikasi Sukses: Biasanya di arahkan ke feed atau muncul toast
                    logger.info("⏳ Memverifikasi publikasi...")
                    # Tunggu hingga halaman berubah atau muncul indikator 'Your reel has been published'
                    page.wait_for_timeout(20000) # Tunggu 20 detik untuk proses akhir
                    
                    logger.info("✅ Facebook Reels BERHASIL dipublikasikan!")
                    return True
                else:
                    logger.error("❌ Tombol 'Publish' tidak dapat diklik atau tidak ditemukan.")
                    return False

            except Exception as e:
                shot_path = f"data/output/fb_err_{int(time.time())}.png"
                page.screenshot(path=shot_path)
                raise e # Lemparkan ke loop retry
            finally:
                browser.close()

fb_uploader = FacebookUploader()
