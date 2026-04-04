import random
import time
import os
from playwright.sync_api import sync_playwright
from logger import logger

class TikTokUploader:
    """
    TikTok Uploader menggunakan Playwright (Browser Automation).
    Refined dengan mekanisme retry dan anti-bot.
    """

    def __init__(self):
        self.user_data_dir = os.path.join(os.getcwd(), "data", "tt_session")
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.upload_url = "https://www.tiktok.com/creator-center/upload"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]

    def upload_to_tiktok(self, video_path: str, description: str, max_retries: int = 3) -> bool:
        """
        Upload video ke TikTok dengan opsi retry.
        """
        for attempt in range(1, max_retries + 1):
            logger.info(f"🎵 Memulai upload TikTok (Percobaan {attempt}/{max_retries}): {os.path.basename(video_path)}")
            try:
                if self._execute_upload(video_path, description):
                    return True
            except Exception as e:
                logger.error(f"⚠️ Percobaan {attempt} gagal: {e}")
            
            if attempt < max_retries:
                time.sleep(attempt * 10)
        
        return False

    def _execute_upload(self, video_path: str, description: str) -> bool:
        if not os.path.exists(video_path):
            logger.error(f"❌ Video tidak ditemukan: {video_path}")
            return False

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=True,
                user_agent=random.choice(self.user_agents),
                slow_mo=100,
                viewport={'width': 1280, 'height': 720}
            )

            page = browser.new_page()
            
            try:
                logger.info(f"🔗 Menuju halaman: {self.upload_url}")
                page.goto(self.upload_url, wait_until="networkidle", timeout=60000)
                
                # Cek Login
                if page.locator("button:has-text('Log in')").count() > 0:
                    logger.error("🚨 Sesi TikTok berakhir. Harap login manual.")
                    return False
                
                # Input Video
                logger.info("📁 Memilih file video...")
                page.set_input_files('input[type="file"]', video_path)

                # Tunggu Upload
                logger.info("⏳ Menunggu upload selesai...")
                page.wait_for_selector('button:has-text("Post")', state="visible", timeout=180000)

                # Deskripsi
                logger.info("✍️ Menulis deskripsi...")
                caption_box = page.locator('div[role="textbox"]').first
                if caption_box.is_visible():
                    caption_box.click()
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    page.keyboard.type(description, delay=70)
                
                time.sleep(random.uniform(3, 5))

                # Post
                logger.info("🚀 Mengklik Post...")
                post_btn = page.locator('button:has-text("Post")').first
                if post_btn.is_enabled():
                    post_btn.click()
                    # Tunggu hingga muncul indikator sukses atau modal tertutup
                    page.wait_for_timeout(15000)
                    logger.info("✅ Video TikTok berhasil diposting!")
                    return True
                else:
                    logger.error("❌ Tombol Post tidak aktif.")
                    return False

            except Exception as e:
                page.screenshot(path=f"data/output/tt_err_{int(time.time())}.png")
                raise e
            finally:
                browser.close()

tiktok_uploader = TikTokUploader()
