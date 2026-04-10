import os
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from dotenv import load_dotenv
from fastapi import Request
from data.mongodb_client import db
from logger import logger

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_fallback_secret_key_change_this")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# Konfigurasi passlib untuk hashing password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Mengecek apakah password input sama dengan password di database."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Mengenkripsi password sebelum disimpan ke database."""
    return pwd_context.hash(password)


def create_access_token(data: dict):
    """Membuat JWT Token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependency FastAPI: Memvalidasi token dan mengambil data user dari DB.
    Sekaligus mengecek apakah langganan (subscription) masih aktif.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah kedaluwarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        # Cari user di MongoDB
        user = db.users.find_one({"username": username})
        if user is None:
            raise credentials_exception

        # Cek apakah akun aktif
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=403, detail="Akun Anda telah dinonaktifkan."
            )

        # Cek masa aktif langganan via subscription_id
        sub_id = user.get("subscription_id")
        if sub_id:
            sub = db.subscriptions.find_one({"_id": sub_id})
            if sub and sub.get("expiry_date") < datetime.utcnow():
                raise HTTPException(
                    status_code=403,
                    detail="Masa berlangganan Anda telah habis. Silakan perpanjang.",
                )

        return user  # Mengembalikan dictionary user yang utuh

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail="Token kedaluwarsa. Silakan login lagi."
        )
    except jwt.PyJWTError:
        raise credentials_exception


def require_owner_role(current_user: dict = Depends(get_current_user)):
    """Memastikan hanya role 'owner' yang bisa akses."""
    if current_user.get("role") != "owner":
        raise HTTPException(
            status_code=403, detail="Akses Ditolak! Endpoint ini khusus untuk Owner."
        )
    return current_user

def log_security_audit(user: dict, action: str, target: str, request: Request):
    """
    Mencatat aksi kritis ke database untuk keperluan forensik keamanan.
    """
    try:
        client_ip = request.headers.get("CF-Connecting-IP") or request.client.host
        device_id = request.headers.get("X-Device-ID", "unknown")

        audit_doc = {
            "timestamp": datetime.utcnow(),
            "username": user["username"],
            "role": user.get("role", "staff"),
            "action": action,
            "target_data": target,
            "ip_address": client_ip,
            "device_id": device_id
        }
        db.security_audit_logs.insert_one(audit_doc)
    except Exception as e:
        logger.error(f"Gagal mencatat audit log: {e}")
