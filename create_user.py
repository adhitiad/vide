"""
create_user.py
==============
Skrip CLI untuk membuat akun baru di database SaaS AI-Clip-Hub.
Jalankan skrip ini melalui terminal server/lokal Anda.
"""

from data.mongodb_client import db
from core.security import get_password_hash
from datetime import datetime, timedelta

def create_new_account():
    print("=== PENDAFTARAN KLIEN / USER BARU ===")
    username = input("Masukkan Username: ")
    
    # Cek apakah username sudah ada
    if db.users.find_one({"username": username}):
        print("❌ Username sudah terdaftar!")
        return

    password = input("Masukkan Password: ")
    role = input("Masukkan Role (owner/admin/staff): ")
    no_hp = input("Masukkan No HP (opsional): ")
    
    print("\n--- Paket Langganan ---")
    print("1. 1 Bulan\n2. 6 Bulan\n3. 1 Tahun\n4. Seumur Hidup (Lifetime)")
    paket = input("Pilih paket (1/2/3/4): ")
    
    now = datetime.utcnow()
    if paket == "1":
        expiry = now + timedelta(days=30)
        plan = "1_month"
    elif paket == "2":
        expiry = now + timedelta(days=180)
        plan = "6_months"
    elif paket == "3":
        expiry = now + timedelta(days=365)
        plan = "1_year"
    else:
        expiry = now + timedelta(days=36500) # 100 tahun
        plan = "lifetime"

    new_user = {
        "username": username,
        "password": get_password_hash(password),
        "avatar": f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}",
        "role": role,
        "no_hp_owner": no_hp,
        "subscription_plan": plan,
        "subscription_expiry": expiry,
        "is_active": True,
        "created_at": now,
        "staff_delegation": [],
        "auto_trend_jacking": False
    }

    db.users.insert_one(new_user)
    print(f"\n✅ Sukses! Akun '{username}' berhasil dibuat.")
    print(f"📅 Masa aktif berlaku sampai: {expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC")

if __name__ == "__main__":
    create_new_account()
