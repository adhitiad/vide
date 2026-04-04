import sqlite3
import os

db_path = "vide.db"

def migrate():
    if not os.path.exists(db_path):
        print(f"❌ Database {db_path} tidak ditemukan. Abaikan migrasi.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🚀 Memulai migrasi database...")

    try:
        # 1. Tambah kolom platform
        try:
            cursor.execute("ALTER TABLE upload_queue ADD COLUMN platform VARCHAR(50) DEFAULT 'youtube'")
            print("✅ Kolom 'platform' ditambahkan.")
        except sqlite3.OperationalError:
            print("ℹ️ Kolom 'platform' sudah ada.")

        # 2. Tambah kolom scheduled_at
        try:
            cursor.execute("ALTER TABLE upload_queue ADD COLUMN scheduled_at DATETIME")
            cursor.execute("UPDATE upload_queue SET scheduled_at = created_at WHERE scheduled_at IS NULL")
            print("✅ Kolom 'scheduled_at' ditambahkan.")
        except sqlite3.OperationalError:
            print("ℹ️ Kolom 'scheduled_at' sudah ada.")

        conn.commit()
        print("🎉 Migrasi SELESAI!")
    except Exception as e:
        print(f"❌ Migrasi Gagal: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
