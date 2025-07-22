from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import scipy.sparse

from app.db.session import get_session
from app.db.models import Destination

router = APIRouter()

# Load artifacts
VEC_PATH = "/app/models/tfidf_vectorizer_dest.pkl"
MAT_PATH = "/app/models/tfidf_matrix_dest.npz"

try:
    vectorizer = pickle.load(open(VEC_PATH, "rb"))
    item_matrix = scipy.sparse.load_npz(MAT_PATH)
except Exception as e:
    raise RuntimeError(f"Failed to load TF-IDF artifacts: {e}")

# Need a mapping from matrix rows → DB IDs
# (retrain script can also dump a pickle of id_map)
ID_MAP   = pickle.load(open("/app/models/item_index_map_dest.pkl", "rb"))

@router.post("/recommend")
async def recommend(
    prefs: dict,
    session: AsyncSession = Depends(get_session),
):
    # Build a query string
    interests = prefs.get("interests", [])
    budget    = prefs.get("budget", 0)
    query     = " ".join(interests) + f" budget {budget}"
    q_vec     = vectorizer.transform([query])

    # Compute similarities
    scores    = cosine_similarity(q_vec, item_matrix).flatten()
    top_idxs  = scores.argsort()[::-1][:10]
    top_ids   = [ID_MAP[i] for i in top_idxs]

    # Fetch Destinations
    stmt      = select(Destination).where(Destination.id.in_(top_ids))
    results   = await session.scalars(stmt)
    items     = results.all()
    if not items:
        raise HTTPException(404, "No recommendations found")
    return items
