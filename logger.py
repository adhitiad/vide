import logging
import sys
import os

# Pastikan folder logs ada
os.makedirs('logs', exist_ok=True)

# Format log
formatter = logging.Formatter(
    fmt='%(asctime)s | %(levelname)-8s | %(module)-10s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Konfigurasi Logger Utama
logger = logging.getLogger('ai-clip-hub')
logger.setLevel(logging.INFO)

# Handler untuk File
file_handler = logging.FileHandler('logs/app.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Handler untuk Konsol
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Hindari duplikasi log
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
