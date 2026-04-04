import sqlite3
import os

db_path = r"f:\code\vide\data\ai_memory.db"
print(f"Connecting to {db_path}...")
try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    columns_to_add = [
        ("platform_video_id", "VARCHAR"),
        ("views", "INTEGER DEFAULT 0"),
        ("likes", "INTEGER DEFAULT 0"),
        ("comments", "INTEGER DEFAULT 0"),
        ("performance_status", "VARCHAR DEFAULT 'PENDING'"),
        ("last_checked", "DATETIME")
    ]
    
    for col, col_type in columns_to_add:
        try:
            cur.execute(f"ALTER TABLE published_video ADD COLUMN {col} {col_type}")
        except Exception as e:
            pass

    conn.commit()
    conn.close()
    
    with open(r"f:\code\vide\mig_status.txt", "w") as f:
        f.write("OK")
except Exception as e:
    pass
