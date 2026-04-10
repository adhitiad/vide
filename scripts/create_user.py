"""
create_user.py (SaaS Billing Version)
=====================================
Skrip untuk mendaftarkan Owner/Agensi baru ke dalam sistem.
"""

import sys
import os
import datetime
import uuid

# Menambahkan path ke root proyek agar bisa import module lain
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.mongodb_client import db
from core.security import get_password_hash

def create_new_subscription():
    print("=== PENDAFTARAN KLIEN SAAS BARU ===")
    username = input("Masukkan Username Klien: ")
    
    if db.users.find_one({"username": username}):
        print("❌ Username sudah ada!")
        return

    password = input("Masukkan Password sementara: ")
    no_hp = input("Masukkan No HP Klien (Untuk Bot WA): ")
    
    print("\n--- Pilih Paket Langganan ---")
    print("1. Individual - 1 Bulan (25 Video)")
    print("2. Individual - 6 Bulan (170 Video / 28 per bulan)")
    print("3. Individual - 1 Tahun (380 Video / 32 per bulan)")
    print("4. Bisnis - 6 Bulan (330 Video Bulk)")
    print("5. Bisnis - 1 Tahun (721 Video Bulk)")
    
    pilihan = input("Pilih paket (1/2/3/4/5): ")
    
    now = datetime.datetime.utcnow()
    sub_id = f"SUB_{uuid.uuid4().hex[:8].upper()}"
    
    # Setup Default Values
    plan_type = "individual"
    max_acc = 4
    is_monthly = True
    expiry = now
    
    # Logika Harga & Kuota
    if pilihan == "1":
        expiry = now + datetime.timedelta(days=30)
        sub_data = {"monthly_quota": 25, "pay_as_you_go_price": 9900}
    elif pilihan == "2":
        expiry = now + datetime.timedelta(days=180)
        sub_data = {"monthly_quota": 28, "pay_as_you_go_price": 8399}
    elif pilihan == "3":
        expiry = now + datetime.timedelta(days=365)
        sub_data = {"monthly_quota": 32, "pay_as_you_go_price": 4689}
    elif pilihan == "4":
        plan_type = "business"
        max_acc = 8
        is_monthly = False
        expiry = now + datetime.timedelta(days=180)
        sub_data = {"total_bulk_quota": 330, "used_total": 0, "pay_as_you_go_price": 3500}
    elif pilihan == "5":
        plan_type = "business"
        max_acc = 8
        is_monthly = False
        expiry = now + datetime.timedelta(days=365)
        sub_data = {"total_bulk_quota": 721, "used_total": 0, "pay_as_you_go_price": 2199}
    else:
        print("Pilihan tidak valid.")
        return

    # 1. Simpan Data Langganan (Subscription)
    subscription_doc = {
        "_id": sub_id,
        "owner_username": username,
        "plan_type": plan_type,
        "max_accounts": max_acc,
        "is_monthly_refresh": is_monthly,
        "extra_videos_count": 0,
        "expiry_date": expiry,
        "created_at": now
    }
    
    if is_monthly:
        subscription_doc["used_this_month"] = 0
        subscription_doc["next_reset_date"] = now + datetime.timedelta(days=30)
        
    subscription_doc.update(sub_data)
    db.subscriptions.insert_one(subscription_doc)

    # 2. Simpan Akun Utama (Owner Klien)
    user_doc = {
        "username": username,
        "password": get_password_hash(password),
        "role": "owner", # Owner dari paket langganan ini
        "subscription_id": sub_id,
        "no_hp_owner": no_hp,
        "staff_delegation": [],
        "is_active": True,
        "created_at": now,
        "niche_keywords": ["bisnis", "motivasi"], # Default niche
        "auto_trend_jacking": True
    }
    db.users.insert_one(user_doc)
    
    print(f"\n✅ SUKSES! Langganan & Akun '{username}' berhasil dibuat.")
    print(f"🔑 Subscription ID: {sub_id}")
    print(f"📅 Berakhir pada: {expiry.strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    create_new_subscription()
