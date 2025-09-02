# scripts/offline_topk.py
import pickle, numpy as np
import scipy.sparse as sp

VEC = "models/tfidf_vectorizer_dest.pkl"
MAT = "models/tfidf_matrix_dest.npz"
IDM = "models/item_index_map_dest.pkl"

query = "Paris sightseeing and local cuisine"
limit = 10


vectorizer = pickle.load(open(VEC, "rb"))
M = sp.load_npz(MAT)           # shape: [num_items, num_terms], CSR
id_map = pickle.load(open(IDM, "rb"))  # dict or list: row_index -> item_id

# map matrix row index to item id robustly (supports dict or list)
def idx_to_item(i: int):
    i = int(i)
    if isinstance(id_map, dict):
        return id_map.get(i, i)
    if isinstance(id_map, list):
        try:
            return id_map[i]
        except Exception:
            return i
    # fallback
    return i

q = vectorizer.transform([query])  # shape: [1, num_terms], CSR
# cosine on L2-normalized TF-IDF  normalized dot product; if not normalized, do so or use sklearn cosine_similarity
scores = M.dot(q.T).toarray().ravel()  # sparse dot

# top-k
if limit >= len(scores): top_idx = np.argsort(-scores)
else:
    part = np.argpartition(-scores, limit)[:limit]
    top_idx = part[np.argsort(-scores[part])]

result = [{"item_id": idx_to_item(i), "score": float(scores[i])} for i in top_idx]
print(result)

{
    "original_text":"Plan a 5-day family trip to Tokyo in December with a $5000 budget. Include museums and sushi.",
    "parsed_data":{
        "locations":["Tokyo"],
        "dates":["2025-12-26T00:00:00Z"],
        "interests":["family","trip","budget","museum","sushi"],
        "budget":5000.0,
        "duration_days":1,
        "group_size":4,
        "travel_style":"budget",
        "confidence_score":100.0,
        "parsing_time_ms":9931.592226028442,
        "warnings":[]},
        "processing_time":9.933320045471191,
        "confidence_score":0.95,
        "errors":[]
    }