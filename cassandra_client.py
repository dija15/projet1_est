from cassandra.cluster import Cluster
from cassandra.auth   import PlainTextAuthProvider
import os

# Paramètres (lire les variables d’environnement si dispo)
HOSTS    = os.getenv("CASSANDRA_HOSTS", "localhost").split(",")
PORT     = int(os.getenv("CASSANDRA_PORT", 9042))
KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "projet_est")
USER     = os.getenv("CASSANDRA_USER", "cassandra")
PASS     = os.getenv("CASSANDRA_PASS", "cassandra")

# Connection unique (singleton basique)
_session = None

def get_session():
    """Retourne une session Cassandra connectée au keyspace."""
    global _session
    if _session is None:
        auth = PlainTextAuthProvider(USER, PASS)
        cluster = Cluster(HOSTS, port=PORT, auth_provider=auth, protocol_version=4)
        _session = cluster.connect()
        _session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {KEYSPACE}
            WITH replication = {{'class':'SimpleStrategy','replication_factor':1}};
        """)
        _session.set_keyspace(KEYSPACE)
    return _session
