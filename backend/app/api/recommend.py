from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import scipy.sparse

from app.db.session import get_session
from app.db.models import Destination, Activity

router = APIRouter(prefix="/recommend", tags=["recommendations"])

# Load destination-TFIDF artifacts
DEST_VEC_PATH = "/app/models/tfidf_vectorizer_dest.pkl"
DEST_MAT_PATH = "/app/models/tfidf_matrix_dest.npz"
DEST_IDMAP_PATH = "/app/models/item_index_map_dest.pkl"

try:
    dest_vectorizer = pickle.load(open(DEST_VEC_PATH, "rb"))
    dest_matrix = scipy.sparse.load_npz(DEST_MAT_PATH)
    DEST_ID_MAP   = pickle.load(open(DEST_IDMAP_PATH, "rb"))
except Exception as e:
    raise RuntimeError(f"Failed to load TF-IDF artifacts: {e}")

# Load activity‐TFIDF artifacts
ACT_VEC_PATH   = "/app/models/tfidf_vectorizer_act.pkl"
ACT_MAT_PATH   = "/app/models/tfidf_matrix_act.npz"
ACT_IDMAP_PATH = "/app/models/item_index_map_act.pkl"

try:
    act_vectorizer = pickle.load(open(ACT_VEC_PATH,   "rb"))
    act_matrix     = scipy.sparse.load_npz(ACT_MAT_PATH)
    ACT_ID_MAP     = pickle.load(open(ACT_IDMAP_PATH, "rb"))
except Exception as e:
    raise RuntimeError(f"Failed to load activity TF-IDF artifacts: {e}")

@router.post("/destinations")
async def recommend_destinations(
    prefs: dict,
    session: AsyncSession = Depends(get_session),
):
    # Build a query string
    interests = prefs.get("interests", [])
    budget    = prefs.get("budget", 0)
    query     = " ".join(interests) + f" budget {budget}"
    q_vec     = dest_vectorizer.transform([query])

    # Compute similarities
    scores    = cosine_similarity(q_vec, dest_matrix).flatten()
    top_idxs  = scores.argsort()[::-1][:10]
    top_ids   = [DEST_ID_MAP[i] for i in top_idxs]

    # Fetch Destinations
    stmt      = select(Destination).where(Destination.id.in_(top_ids))
    results   = await session.scalars(stmt)
    items     = results.all()
    if not items:
        raise HTTPException(404, "No destination recommendations found")
    return items

@router.post("/activities")
async def recommend_activities(
    prefs: dict,
    session: AsyncSession = Depends(get_session),
):
    # build same “interests + budget” query
    interests = prefs.get("interests", [])
    budget    = prefs.get("budget", 0)
    query     = " ".join(interests) + f" budget {budget}"
    q_vec     = act_vectorizer.transform([query])

    # cosine‐similarity → top 10 indexes → map to IDs
    scores   = cosine_similarity(q_vec, act_matrix).flatten()
    top_idxs = scores.argsort()[::-1][:10]
    top_ids  = [ACT_ID_MAP[i] for i in top_idxs]

    # fetch from DB
    stmt    = select(Activity).where(Activity.id.in_(top_ids))
    results = await session.scalars(stmt)
    items   = results.all()
    if not items:
        raise HTTPException(404, "No activity recommendations found")
    return items
