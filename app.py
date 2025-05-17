# ──────────────── service_fichiers.py (Cassandra + MinIO + JWT) ────────────────
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from minio import Minio, error as minio_err
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
import os, uuid, shutil
from datetime import timedelta
from uuid import UUID
from io import BytesIO
# ───────────── CONFIG GLOBALE
app = Flask(__name__)
CORS(app, origins=["http://localhost:3000"])
app.config["JWT_SECRET_KEY"] = "your-secret-key"        # ← change en prod
jwt = JWTManager(app)

# MinIO
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET", "cours")

minio_client = Minio(
    MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY, secure=False
)
if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)

# Cassandra
CASSANDRA_HOSTS    = os.getenv("CASSANDRA_HOSTS", "localhost").split(",")
CASSANDRA_PORT     = int(os.getenv("CASSANDRA_PORT", 9042))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "projet_est")
CASSANDRA_USER     = os.getenv("CASSANDRA_USER", "cassandra")
CASSANDRA_PASS     = os.getenv("CASSANDRA_PASS", "cassandra")

auth = PlainTextAuthProvider(CASSANDRA_USER, CASSANDRA_PASS)
cluster = Cluster(CASSANDRA_HOSTS, port=CASSANDRA_PORT,
                  auth_provider=auth, protocol_version=4)
session = cluster.connect()
session.execute(f"""
  CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE}
  WITH replication = {{'class':'SimpleStrategy','replication_factor':1}};
""")
session.set_keyspace(CASSANDRA_KEYSPACE)
session.execute("""
CREATE TABLE IF NOT EXISTS utilisateurs (
    id UUID PRIMARY KEY,
    email TEXT,
    mot_de_pass TEXT,
    nom TEXT,
    role TEXT,
    date_inscription TIMESTAMP
);
""")
session.execute("""
CREATE TABLE IF NOT EXISTS cours (
    id UUID PRIMARY KEY,
    titre TEXT,
    description TEXT,
    enseignant_id UUID,
    date_creation TIMESTAMP,
    minio_path TEXT,
    nom_original TEXT,
    taille INT,
    type TEXT
);
""")

# ─────────── HELPERS
def save_tmp(file_storage):
    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    path = os.path.join(tmp_dir, f"{uuid.uuid4()}_{file_storage.filename}")
    file_storage.save(path)
    return path

def auth_required(roles=None):
    def decorator(fn):
        @jwt_required()
        def wrapper(*args, **kwargs):
            ide = get_jwt_identity()
            if roles and ide["role"] not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            request.user = ide
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator

# ─────────── ROUTE LOGIN (BDD)
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email    = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "email / password manquants"}), 400

    row = session.execute(
        "SELECT id, mot_de_pass, nom, role FROM utilisateurs "
        "WHERE email=%s ALLOW FILTERING", [email]
    ).one()

    if not row or row.mot_de_pass != password:
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_access_token(identity={
        "user_id": str(row.id),
        "email"  : email,
        "role"   : row.role,
        "name"   : row.nom
    })
    return jsonify({
        "access_token": token,
        "user": {"id": str(row.id), "email": email, "name": row.nom, "role": row.role}
    }), 200

# ─────────── ROUTE UPLOAD
@app.route("/api/upload", methods=["POST"])
@auth_required(roles=["enseignant", "admin"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "no file part"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "filename empty"}), 400

    titre       = request.form.get("title", f.filename)
    description = request.form.get("description", "")
    enseignant_id = UUID(request.user["user_id"])

    file_id  = uuid.uuid4()
    obj_name = f"{file_id}-{f.filename}"
    tmp_path = save_tmp(f)
    size     = os.path.getsize(tmp_path)
    f_type   = f.filename.rsplit(".", 1)[-1].lower()

    minio_client.fput_object(MINIO_BUCKET, obj_name, tmp_path)
    shutil.os.remove(tmp_path)

    session.execute("""
        INSERT INTO cours (id,titre,description,enseignant_id,date_creation,
                           minio_path,nom_original,taille,type)
        VALUES (%s,%s,%s,%s,toTimestamp(now()),%s,%s,%s,%s)
    """, (file_id,titre,description,enseignant_id,
          obj_name,f.filename,size,f_type))

    url = minio_client.presigned_get_object(
        MINIO_BUCKET, obj_name, expires=timedelta(hours=1)
    )
    return jsonify({"id": str(file_id), "download_url": url}), 201

# ─────────── ROUTE LIST
@app.route("/api/files", methods=["GET"])
@auth_required()
def list_files():
    rows = session.execute("SELECT * FROM cours")
    out  = []
    for r in rows:
        try:
            url = minio_client.presigned_get_object(MINIO_BUCKET, r.minio_path,
                                                    expires=timedelta(hours=1))
        except minio_err.S3Error:
            url = None
        out.append({
            "id": str(r.id), "title": r.titre, "author": str(r.enseignant_id),
            "description": r.description, "download_url": url
        })
    return jsonify(out), 200

# ─────────── ROUTE LINK


@app.route("/api/files/download/<uuid:file_id>", methods=["GET"])
@auth_required()                   # ← n'importe quel utilisateur authentifié
def download_or_link(file_id):
    # 1) récupérer métadonnées
    row = session.execute(
        "SELECT minio_path, nom_original FROM cours WHERE id=%s", [file_id]
    ).one()
    if not row:
        return jsonify({"error": "File not found"}), 404

    # 2) lien pré‑signé (utile dans les deux cas)
    url_signed = minio_client.presigned_get_object(
        MINIO_BUCKET, row.minio_path, expires=timedelta(hours=1)
    )

    # 3) si le client veut du JSON (ex. front ou Postman header Accept: application/json)
    wants_json = request.accept_mimetypes.best == "application/json"
    if wants_json:
        return jsonify({
            "download_url": url_signed,
            "filename": row.nom_original
        }), 200

    # 4) sinon → on stream directement le fichier
    try:
        obj = minio_client.get_object(MINIO_BUCKET, row.minio_path)
        data = BytesIO(obj.read())
        obj.close(); obj.release_conn()

        return send_file(
            data,
            download_name=row.nom_original or "fichier",
            as_attachment=True
        )
    except minio_err.S3Error as e:
        return jsonify({"error": f"MinIO error : {str(e)}"}), 500

# ─────────── MAIN
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
