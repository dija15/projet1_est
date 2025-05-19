from flask import Flask, jsonify, request, send_file
from cassandra_client import get_session
from minio_client      import upload_file, generate_url, client
from flask_cors import CORS
import os
from io import BytesIO
from datetime import timedelta
from minio.error import S3Error
import uuid
import logging

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000"])

# Configuration MinIO
MINIO_CLIENT = client  # Using the imported client from minio_client
MINIO_BUCKET = "cours"

try:
    print(client.list_buckets())
    print("Connexion MinIO OK")
except Exception as e:
    print(f"Échec connexion MinIO: {str(e)}")

# Lister tous les fichiers dans le bucket
objects = client.list_objects("cours")
for obj in objects:
    print(obj.object_name)  # Vérifiez que votre fichier apparaît

# Configurer le logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




@app.route('/', methods=["GET"])
def index():
    try:
        session = get_session()

        # Get teachers
        query = session.execute("SELECT id, nom FROM utilisateurs WHERE role = 'enseignant' ALLOW FILTERING;")
        enseignant_map = {row.id: row.nom for row in query}

        # Get courses
        query = session.execute("SELECT id, titre, enseignant_id FROM cours")
        cours_map = {
            row.id: {"titre": row.titre, "enseignant_id": row.enseignant_id}
            for row in query
        }

        # Get files
        query = session.execute("SELECT * FROM fichiers")
        results = []

        # Combine data
        for i in query:
            cours_info = cours_map.get(i.cours_id, {})
            cours_titre = cours_info.get("titre", "Cours Inconnu")
            enseignant_id = cours_info.get("enseignant_id")
            enseignant_nom = enseignant_map.get(enseignant_id, "Enseignant Inconnu")

            results.append({
                "id": str(i.id),
                "nom": i.nom,
                "url": i.url,
                "cours_titre": cours_titre,
                "enseignant_nom": enseignant_nom,
                "date_upload": str(i.date_upload.date()) if i.date_upload else None
            })

        return jsonify(results)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/fichier/add', methods=['POST'])
def upload_data():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        filename = file.filename
        
        # Create temp directory
        os.makedirs('./tmp', exist_ok=True)
        file_path = os.path.join('./tmp', filename)
        
        # Save file temporarily
        file.save(file_path)

        # Upload to MinIO
        response = upload_file(MINIO_BUCKET, file_path, filename)

        # Generate URL
        url = generate_url(MINIO_BUCKET, filename)

        # Store in Cassandra
        session = get_session()
        session.execute("""
            INSERT INTO fichiers (id, cours_id, date_upload, nom, url)
            VALUES (uuid(), 28f47e89-97a1-4e45-8221-978cd1977ad1, toTimestamp(now()), %s, %s)
        """, (filename, url))

        # Clean up temp file
        if os.path.exists(file_path):
            os.remove(file_path)

        return jsonify({
            "message": "File uploaded successfully",
            "filename": filename,
            "url": url
        }), 200
    except Exception as e:
        logger.error(f"Error in upload_data route: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route("/api/files", methods=["GET"])
def list_files():
    try:
        objects = MINIO_CLIENT.list_objects(MINIO_BUCKET, recursive=True)
        
        files_list = []
        for obj in objects:
            if not obj.is_dir:
                try:
                    download_url = MINIO_CLIENT.presigned_get_object(
                        MINIO_BUCKET,
                        obj.object_name,
                        expires=timedelta(hours=1)
                    )
                    
                    files_list.append({
                        "id": str(uuid.uuid4()),
                        "name": obj.object_name.split('/')[-1],
                        "path": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat(),
                        "download_url": download_url
                    })
                except S3Error as e:
                    logger.error(f"Error generating URL for {obj.object_name}: {e}")
                    continue
                
        return jsonify(files_list), 200
    except S3Error as e:
        logger.error(f"MinIO list objects error: {e}")
        return jsonify({"error": "Error communicating with storage"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in list_files: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/files/download/<path:filename>", methods=["GET"])
def download(filename):
    try:
        # Décodage du nom de fichier
        from urllib.parse import unquote
        filename = unquote(filename)
        
        print(f"\n[DEBUG] Tentative de téléchargement: {filename}")

        # Validation du nom de fichier
        if not filename:
            return jsonify({"error": "Nom de fichier manquant"}), 400

        # Vérification que le fichier existe dans MinIO
        try:
            MINIO_CLIENT.stat_object(MINIO_BUCKET, filename)
        except Exception as e:
            print(f"[ERREUR] Fichier non trouvé dans MinIO: {str(e)}")
            return jsonify({"error": "Fichier non trouvé"}), 404

        # Récupération du fichier depuis MinIO
        try:
            response = MINIO_CLIENT.get_object(MINIO_BUCKET, filename)
            file_data = BytesIO(response.read())
            
            # Détermination du type MIME
            from mimetypes import guess_type
            mimetype, _ = guess_type(filename)
            mimetype = mimetype or 'application/octet-stream'
            
            print(f"[DEBUG] Envoi du fichier {filename} ({mimetype})")
            
            return send_file(
                file_data,
                as_attachment=True,
                download_name=filename.split('/')[-1],
                mimetype=mimetype
            )
            
        except Exception as e:
            print(f"[ERREUR] Échec du téléchargement: {str(e)}")
            return jsonify({"error": "Échec du téléchargement"}), 500
            
        finally:
            response.close()
            response.release_conn()

    except Exception as e:
        print(f"[ERREUR CRITIQUE] {str(e)}")
        return jsonify({"error": "Erreur serveur"}), 500
    
if __name__ == '__main__':
    app.run(debug=True)