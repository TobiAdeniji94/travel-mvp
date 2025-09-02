import pickle
import psycopg2
import os

ML_PATH = os.path.join('..', 'models', 'item_index_map_act.pkl')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'travel')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASS = os.environ.get('DB_PASS', 'password')


def load_ml_ids(path):
    with open(path, 'rb') as f:
        id_map = pickle.load(f)
    # If it's a list, just return the set of stringified IDs
    if isinstance(id_map, list):
        return set(str(v) for v in id_map)
    # If it's a dict, use the values
    elif isinstance(id_map, dict):
        return set(str(v) for v in id_map.values())
    else:
        raise TypeError(f"Unexpected type for ML mapping: {type(id_map)}")

def load_db_ids():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cur = conn.cursor()
    cur.execute("SELECT id FROM activities")
    db_ids = set(str(row[0]) for row in cur.fetchall())
    cur.close()
    conn.close()
    return db_ids


def main():
    print(f"Loading ML mapping from {ML_PATH}")
    ml_ids = load_ml_ids(ML_PATH)
    print(f"ML model has {len(ml_ids)} activity IDs")
    db_ids = load_db_ids()
    print(f"Database has {len(db_ids)} activity IDs")
    in_both = ml_ids & db_ids
    ml_only = ml_ids - db_ids
    db_only = db_ids - ml_ids
    print(f"IDs in both ML and DB: {len(in_both)}")
    print(f"IDs only in ML (missing in DB): {len(ml_only)}")
    print(f"IDs only in DB (missing in ML): {len(db_only)}")
    if ml_only:
        print("Sample IDs only in ML:", list(ml_only)[:10])
    if db_only:
        print("Sample IDs only in DB:", list(db_only)[:10])

if __name__ == "__main__":
    main()
