# ───────────────────────── service_fichiers.py ──────────────────────────
"""
Micro‑service « fichiers » :
• Authentification JWT (table `utilisateurs`)
• Upload de fichiers vers MinIO + insertion métadonnées dans Cassandra
• Liste des fichiers
• Téléchargement
• Génération dURL présignées (1h) ou téléchargement direct
"""

# ----------------------- IMPORTS STANDARD & LIBS ------------------------
from flask import Flask, request, jsonify, send_file      # serveur + JSON + download
from flask_cors import CORS                               # CORS pour le front React
from flask_jwt_extended import (                          # JWT (login + décorateurs)
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)

# MinIO client + alias d’erreurs (on les renomme minio_err)
from minio import Minio, error as minio_err

# Cassandra driver (connexion et auth basique)
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

# Bibliothèque standard
import os, uuid, shutil
from datetime import timedelta
from uuid import UUID
from io import BytesIO

# ─────────────────────────── INITIALISATION APP ─────────────────────────
app = Flask(__name__)
CORS(app, origins=["http://localhost:3000"])  # Autorise les requêtes du front

# Clé JWT (⚠️ change‑la en production)
app.config["JWT_SECRET_KEY"] = "your-secret-key"
jwt = JWTManager(app)

# ───────────────────────── MINIO (stockage S3) ──────────────────────────
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET", "cours")  # bucket unique

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False                # HTTP (pas HTTPS) ; suffisant en LAN / dev
)
# Crée le bucket s’il n’existe pas (idempotent)
if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)

# ────────────────────────── CASSANDRA (BDD) ─────────────────────────────
CASSANDRA_HOSTS    = os.getenv("CASSANDRA_HOSTS", "localhost").split(",")
CASSANDRA_PORT     = int(os.getenv("CASSANDRA_PORT", 9042))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "projet_est")
CASSANDRA_USER     = os.getenv("CASSANDRA_USER", "cassandra")
CASSANDRA_PASS     = os.getenv("CASSANDRA_PASS", "cassandra")

auth = PlainTextAuthProvider(CASSANDRA_USER, CASSANDRA_PASS)
cluster = Cluster(
    CASSANDRA_HOSTS,
    port=CASSANDRA_PORT,
    auth_provider=auth,
    protocol_version=4
)
session = cluster.connect()

# Keyspace + tables si absentes
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

# ───────────────────────────── HELPERS ──────────────────────────────────
def save_tmp(file_storage):
    """
    Enregistre le fichier reçu (werkzeug FileStorage) dans /tmp
    et renvoie le chemin temporaire.
    """
    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    path = os.path.join(tmp_dir, f"{uuid.uuid4()}_{file_storage.filename}")
    file_storage.save(path)
    return path

def auth_required(roles=None):
    """
    Décorateur maison : vérifie JWT + rôle.
    • roles = None  → simple authentification
    • roles = ["enseignant"] → rôle obligatoire
    """
    def decorator(fn):
        @jwt_required()
        def wrapper(*args, **kwargs):
            identity = get_jwt_identity()
            if roles and identity["role"] not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            request.user = identity      # stocke l’identité pour la route
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__   # évite les warnings Flask
        return wrapper
    return decorator

# ───────────────────────── ROUTE LOGIN (JWT) ────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    """ Authentifie l’utilisateur via Cassandra et retourne un JWT """
    data = request.get_json(silent=True) or {}
    email    = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "email / password manquants"}), 400

    row = session.execute(
        "SELECT id, mot_de_pass, nom, role FROM utilisateurs "
        "WHERE email=%s ALLOW FILTERING",
        [email]
    ).one()

    if not row or row.mot_de_pass != password:
        return jsonify({"error": "Invalid credentials"}), 401

    # Génération token
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

# ───────────────────────── ROUTE UPLOAD ─────────────────────────────────
@app.route("/api/upload", methods=["POST"])
@auth_required(roles=["enseignant", "admin"])
def upload_file():
    """ Upload du fichier vers MinIO + insertion en base """
    # 1) validation
    if "file" not in request.files:
        return jsonify({"error": "no file part"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "filename empty"}), 400

    # 2) extraction métadonnées
    titre        = request.form.get("title", f.filename)
    description  = request.form.get("description", "")
    enseignant_id = UUID(request.user["user_id"])   # ↩ issu du JWT

    # 3) préparation fichier
    file_id  = uuid.uuid4()
    obj_name = f"{file_id}-{f.filename}"           # chemin objet S3
    tmp_path = save_tmp(f)                         # save dans /tmp
    size     = os.path.getsize(tmp_path)
    f_type   = f.filename.rsplit(".", 1)[-1].lower()

    # 4) upload MinIO
    minio_client.fput_object(MINIO_BUCKET, obj_name, tmp_path)
    shutil.os.remove(tmp_path)                     # nettoyage

    # 5) insert Cassandra
    session.execute("""
        INSERT INTO cours (id,titre,description,enseignant_id,date_creation,
                           minio_path,nom_original,taille,type)
        VALUES (%s,%s,%s,%s,toTimestamp(now()),%s,%s,%s,%s)
    """, (file_id, titre, description, enseignant_id,
          obj_name, f.filename, size, f_type))

    # 6) URL pré‑signée (durée : 1 h)
    url = minio_client.presigned_get_object(
        MINIO_BUCKET, obj_name, expires=timedelta(hours=1)
    )

    return jsonify({"id": str(file_id), "download_url": url}), 201

# ───────────────────────── ROUTE LISTE ──────────────────────────────────
@app.route("/api/files", methods=["GET"])
@auth_required()
def list_files():
    """ Liste les fichiers (avec URL signée 1 h) """
    rows = session.execute("SELECT * FROM cours")
    resp = []
    for r in rows:
        try:
            url = minio_client.presigned_get_object(
                MINIO_BUCKET, r.minio_path, expires=timedelta(hours=1)
            )
        except minio_err.S3Error:
            url = None
        resp.append({
            "id"          : str(r.id),
            "title"       : r.titre,
            "description" : r.description,
            "author"      : str(r.enseignant_id),
            "download_url": url
        })
    return jsonify(resp), 200

# ───────────────────────── ROUTE DOWNLOAD / LINK ───────────────────────
@app.route("/api/files/download/<uuid:file_id>", methods=["GET"])
@auth_required()            # tout utilisateur connecté
def download_or_link(file_id):
    """
    • Si le client demande JSON (Accept: application/json) → renvoie l’URL signée
    • Sinon                                                 → stream direct du fichier
    """
    # A) métadonnées
    row = session.execute(
        "SELECT minio_path, nom_original FROM cours WHERE id=%s", [file_id]
    ).one()
    if not row:
        return jsonify({"error": "File not found"}), 404

    # B) URL signée
    url_signed = minio_client.presigned_get_object(
        MINIO_BUCKET, row.minio_path, expires=timedelta(hours=1)
    )

    # C) Choix du mode de réponse
    if request.accept_mimetypes.best == "application/json":
        # → JSON (front ou Postman)
        return jsonify({
            "download_url": url_signed,
            "filename"    : row.nom_original
        }), 200

    # D) Téléchargement direct
    try:
        obj  = minio_client.get_object(MINIO_BUCKET, row.minio_path)
        data = BytesIO(obj.read())
        obj.close(); obj.release_conn()

        return send_file(
            data,
            download_name=row.nom_original or "fichier",
            as_attachment=True
        )
    except minio_err.S3Error as e:
        return jsonify({"error": f"MinIO error : {e}"}), 500

# ───────────────────────── Lancement serveur ────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
