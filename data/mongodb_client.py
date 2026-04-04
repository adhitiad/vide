import os
from pymongo import MongoClient
from logger import logger

class MongoDBClient:
    _instance = None
    client: MongoClient
    db: any

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBClient, cls).__new__(cls)
            
            # Konfigurasi MongoDB (Local default)
            mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
            db_name = os.getenv("MONGO_DB_NAME", "vide_db")
            
            try:
                cls._instance.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
                # Cek koneksi dengan ping
                cls._instance.client.admin.command('ping')
                cls._instance.db = cls._instance.client[db_name]
                logger.info(f"✅ Berhasil terhubung ke MongoDB: {db_name}")
            except Exception as e:
                logger.error(f"❌ Gagal terhubung ke MongoDB: {e}")
                raise e
        
        return cls._instance

# Singleton Instance
mongo_client = MongoDBClient()
db = mongo_client.db
