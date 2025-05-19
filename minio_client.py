from minio import Minio
from datetime import timedelta
import os, uuid

# Paramètres MinIO
ENDPOINT   = os.getenv("MINIO_ENDPOINT", "localhost:9000")
ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
BUCKET     = os.getenv("MINIO_BUCKET", "cours")

# Client unique
client = Minio(ENDPOINT, ACCESS_KEY, SECRET_KEY, secure=False)

# S’assurer que le bucket existe
if not client.bucket_exists(BUCKET):
    client.make_bucket(BUCKET)

def upload_file(bucket: str, file_path: str, object_name: str):
    """Téléverse un fichier et renvoie les infos MinIO."""
    client.fput_object(bucket, object_name, file_path)
    return {"bucket": bucket, "object_name": object_name}

def generate_url(bucket: str, object_name: str, hours: int = 1):
    """Génère une URL pré‑signée valable X heures."""
    return client.presigned_get_object(bucket, object_name,
                                       expires=timedelta(hours=hours))
