import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "ai_memory.db"))

print(f"Applying migration to {DB_PATH}")

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    columns_to_add = [
        ("platform_video_id", "VARCHAR"),
        ("views", "INTEGER DEFAULT 0"),
        ("likes", "INTEGER DEFAULT 0"),
        ("comments", "INTEGER DEFAULT 0"),
        ("performance_status", "VARCHAR DEFAULT 'PENDING'"),
        ("last_checked", "DATETIME")
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE published_video ADD COLUMN {col_name} {col_type}")
            print(f"[{col_name}] ADDED!")
        except Exception as e:
            print(f"[{col_name}] SKIPPED (already exists or error: {e})")

    conn.commit()
    conn.close()
    print("Migration finished completely.")
except Exception as e:
    print(f"Fatal error during migration: {e}")
