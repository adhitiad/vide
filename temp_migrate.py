import sqlite3
import os

db_path = r"f:\code\vide\data\ai_memory.db"

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Cek apakah kolom platform sudah ada
        cursor.execute("PRAGMA table_info(published_video)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "platform" not in columns:
            cursor.execute("ALTER TABLE published_video ADD COLUMN platform VARCHAR(50) DEFAULT 'youtube'")
            conn.commit()
            print("✅ Kolom 'platform' berhasil ditambahkan ke tabel published_video.")
        else:
            print("ℹ️ Kolom 'platform' sudah ada, tidak perlu migrasi.")
            
        conn.close()
    except Exception as e:
        print(f"❌ Error saat migrasi: {e}")
else:
    print("⚠️ Database belum dibuat, SQLAlchemy akan membuatnya secara otomatis nanti.")
