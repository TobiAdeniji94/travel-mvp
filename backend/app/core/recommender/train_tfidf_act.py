#!/usr/bin/env python3
import re
import asyncio
import pickle
from pathlib import Path

from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlmodel import select

from app.db.session import async_session
from app.db.models import Activity

# output dir inside container
OUT = Path("/app/models")
OUT.mkdir(exist_ok=True)

VEC_PKL   = OUT / "tfidf_vectorizer_act.pkl"
MAT_NPZ   = OUT / "tfidf_matrix_act.npz"
IDMAP_PKL = OUT / "item_index_map_act.pkl"

def clean(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

async def fetch_activities():
    """Return (ids, cleaned_descriptions) for all Activities."""
    ids, texts = [], []
    async with async_session() as session:
        result = await session.execute(select(Activity.id, Activity.description))
        for _id, desc in result.all():
            ids.append(_id)
            texts.append(clean(desc))
    return ids, texts

async def main():
    print("⏳ Fetching activity corpus…")
    ids, corpus = await fetch_activities()
    if not corpus:
        print("⚠️  No activity documents found!")
        return

    print(f"⚙️  Fitting TF-IDF on {len(corpus)} activity docs…")
    vec = TfidfVectorizer(max_features=5000, stop_words="english")
    mat = vec.fit_transform(corpus)

    print(f"💾 Saving vectorizer → {VEC_PKL}")
    with open(VEC_PKL, "wb") as f:
        pickle.dump(vec, f)

    print(f"💾 Saving matrix → {MAT_NPZ}")
    sparse.save_npz(str(MAT_NPZ), mat)

    print(f"💾 Saving ID map → {IDMAP_PKL}")
    with open(IDMAP_PKL, "wb") as f:
        pickle.dump(ids, f)

    print("✅ Activity TF-IDF artifacts written to /app/models")

if __name__ == "__main__":
    asyncio.run(main())
