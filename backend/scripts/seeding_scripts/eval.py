import argparse
import csv
import json
import os
import sys
import time
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# Optional heavy deps are imported lazily where needed

# Now that eval.py lives in backend/, resolve all paths relative to backend/
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
BACKEND_DIR = BASE_DIR


# ---------- IO helpers ----------
def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ---------- Metrics ----------
def precision_at_k(rank: Sequence[str], rel_set: set, k: int) -> float:
    if k <= 0:
        return 0.0
    hits = sum(1 for x in rank[:k] if x in rel_set)
    return hits / float(k)


def average_precision_at_k(rank: Sequence[str], rel_set: set, k: int) -> float:
    if not rank or k <= 0:
        return 0.0
    num_hits, ap = 0, 0.0
    topk = rank[:k]
    for i, poi in enumerate(topk, start=1):
        if poi in rel_set:
            num_hits += 1
            ap += num_hits / i
    denom = len(rel_set & set(topk))
    return ap / max(1, denom)


# ---------- Candidate loading ----------
@dataclass
class Candidate:
    id: str
    text: str


def _tokenize(s: str) -> List[str]:
    import re
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return [t for t in s.split() if t]


def load_candidates() -> List[Candidate]:
    """Load candidate POIs as a list of Candidate(id, text).
    Preferred order:
    1) data/candidates.json (fast, cached)
    2) Query DB via backend models if available
    3) If neither available, raise with instructions
    """
    cached = DATA_DIR / "candidates.json"
    if cached.exists():
        items = load_json(cached)
        return [Candidate(id=x["id"], text=x.get("text", "")) for x in items]

    # Try DB fetch from backend if available
    try:
        sys.path.append(str(BACKEND_DIR))
        # Import inside to keep eval.py import-light
        from app.db.session import db_manager
        from app.db.models import Activity  # focusing on activities as POIs
        import asyncio
        from sqlmodel import select

        async def fetch():
            if not db_manager.engine:
                await db_manager.initialize()
            items: List[Candidate] = []
            async with db_manager.get_session() as session:
                result = await session.exec(select(Activity))
                rows = result.all()
                for a in rows:
                    parts = [a.name or "", a.description or "", ", ".join(a.tags or [])]
                    items.append(Candidate(id=str(a.id), text=" \n".join(p for p in parts if p)))
            return items

        items = asyncio.run(fetch())
        # Save cache for next time
        save_json(cached, [{"id": c.id, "text": c.text} for c in items])
        return items
    except Exception:
        # Fallback: build from CSV catalog if available
        try:
            csv_path = BACKEND_DIR / "scripts" / "activities.csv"
            items: List[Candidate] = []
            if not csv_path.exists():
                raise FileNotFoundError(str(csv_path))
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pid = row.get("id") or row.get("uuid") or row.get("ID")
                    name = row.get("name", "")
                    desc = row.get("description", "")
                    tags = row.get("tags", "")
                    text = " \n".join(x for x in [name, desc, tags] if x)
                    if pid:
                        items.append(Candidate(id=str(pid), text=text))
            if items:
                save_json(cached, [{"id": c.id, "text": c.text} for c in items])
                return items
        except Exception as e2:
            raise RuntimeError(
                "Could not load candidates. Either: "
                f"1) Create {cached} as a list of objects with 'id' and 'text'; "
                f"2) Ensure DB is configured; or 3) Provide a CSV at {BACKEND_DIR / 'scripts' / 'activities.csv'}. "
                f"Last error: {e2}"
            )


# ---------- Rankers ----------
class BaseRanker:
    name: str = "base"

    def rank(self, prompt_text: str, candidates: List[Candidate]) -> List[str]:
        raise NotImplementedError


class TFIDFRanker(BaseRanker):
    name = "tfidf"

    def __init__(self, domain: str = "act"):
        import pickle
        try:
            import scipy.sparse as sp
        except Exception as e:
            raise RuntimeError("TF-IDF ranker requires SciPy (scipy.sparse). Please install scipy.") from e
        domain_map = {
            "dest": ("tfidf_vectorizer_dest.pkl", "tfidf_matrix_dest.npz", "item_index_map_dest.pkl"),
            "act": ("tfidf_vectorizer_act.pkl", "tfidf_matrix_act.npz", "item_index_map_act.pkl"),
            "acc": ("tfidf_vectorizer_acc.pkl", "tfidf_matrix_acc.npz", "item_index_map_acc.pkl"),
            "trans": ("tfidf_vectorizer_trans.pkl", "tfidf_matrix_trans.npz", "item_index_map_trans.pkl"),
        }
        vec_file, mat_file, map_file = domain_map[domain]
        self.vectorizer = pickle.load(open(MODELS_DIR / vec_file, "rb"))
        self.M = sp.load_npz(MODELS_DIR / mat_file)  # CSR [num_items, num_terms]
        self.id_map = pickle.load(open(MODELS_DIR / map_file, "rb"))

    def _idx_to_id(self, i: int) -> str:
        i = int(i)
        if isinstance(self.id_map, dict):
            return str(self.id_map.get(i, i))
        if isinstance(self.id_map, list):
            try:
                return str(self.id_map[i])
            except Exception:
                return str(i)
        return str(i)

    def rank(self, prompt_text: str, candidates: List[Candidate]) -> List[str]:
        # The TF-IDF artifacts are already item-level; ignore candidates' text and return IDs from the model space
        import numpy as np
        q = self.vectorizer.transform([prompt_text])
        scores = self.M.dot(q.T).toarray().ravel()
        # argsort descending
        idx = np.argsort(-scores)
        return [self._idx_to_id(i) for i in idx]


class BM25Ranker(BaseRanker):
    name = "bm25"

    def __init__(self, candidates: List[Candidate], k1: float = 1.5, b: float = 0.75):
        # Build BM25 corpus
        self.k1 = k1
        self.b = b
        self.docs = [c.id for c in candidates]
        self.tokens = [_tokenize(c.text) for c in candidates]
        self.doc_lens = [len(t) for t in self.tokens]
        self.N = len(self.tokens)
        self.avgdl = (sum(self.doc_lens) / self.N) if self.N else 0.0
        # DF
        from collections import Counter
        df = Counter()
        for toks in self.tokens:
            for term in set(toks):
                df[term] += 1
        # IDF with +1 smoothing to avoid negatives for very frequent terms
        import math
        self.idf = {t: math.log((self.N - df_t + 0.5) / (df_t + 0.5) + 1.0) for t, df_t in df.items()}
        self.term_freqs = []
        for toks in self.tokens:
            tf = Counter(toks)
            self.term_freqs.append(tf)

    def score(self, q_tokens: List[str], i: int) -> float:
        import math
        score = 0.0
        dl = self.doc_lens[i] or 1
        tf = self.term_freqs[i]
        for term in q_tokens:
            if term not in self.idf:
                continue
            f = tf.get(term, 0)
            if f == 0:
                continue
            num = f * (self.k1 + 1)
            den = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
            score += self.idf[term] * (num / (den or 1))
        return score

    def rank(self, prompt_text: str, candidates: List[Candidate]) -> List[str]:
        q = _tokenize(prompt_text)
        if not q:
            return [c.id for c in candidates]
        # Standard-library sort to avoid NumPy dependency
        scored = [(i, self.score(q, i)) for i in range(len(candidates))]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [candidates[i].id for i, _ in scored]


class EmbeddingRanker(BaseRanker):
    name = "embed"

    def __init__(self, candidates: List[Candidate], model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self._ok = False
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            self.np = np
            self.model = SentenceTransformer(model_name)
            self.ids = [c.id for c in candidates]
            self.texts = [c.text for c in candidates]
            # Precompute embeddings
            self.mat = self.model.encode(self.texts, convert_to_numpy=True, normalize_embeddings=True)
            self._ok = True
        except Exception as e:
            # Fallback: simple TF-IDF as pseudo-embedding to allow script to run
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                import numpy as np
                self.np = np
                self.vec = TfidfVectorizer(min_df=1, ngram_range=(1, 2))
                self.ids = [c.id for c in candidates]
                self.texts = [c.text for c in candidates]
                self.mat = self.vec.fit_transform(self.texts)  # L2 normalization later
                self._ok = False
                print("[embed] sentence-transformers not available; using TF-IDF fallback for embedding baseline.")
            except Exception as e2:
                raise RuntimeError(f"Embedding ranker unavailable: {e} / {e2}")

    def rank(self, prompt_text: str, candidates: List[Candidate]) -> List[str]:
        if hasattr(self, "model") and self._ok:
            q = self.model.encode([prompt_text], convert_to_numpy=True, normalize_embeddings=True)[0]
            sims = (self.mat @ q).astype(float)
            idx = self.np.argsort(-sims)
            return [self.ids[i] for i in idx]
        else:
            # TF-IDF fallback cosine
            from sklearn.preprocessing import normalize
            q = self.vec.transform([prompt_text])
            M = normalize(self.mat)
            qn = normalize(q)
            sims = (M @ qn.T).toarray().ravel()
            idx = self.np.argsort(-sims)
            return [self.ids[i] for i in idx]


# ---------- Evaluation ----------
def run_ranker(ranker: BaseRanker, prompt_text: str, candidates: List[Candidate]) -> List[str]:
    return ranker.rank(prompt_text, candidates)


def evaluate(ranker: BaseRanker, prompts: List[Dict], labels: List[Dict], candidates: List[Candidate], ks: Sequence[int]) -> Dict[str, float]:
    rel_map = {x["prompt_id"]: set(x.get("relevant", [])) for x in labels}
    sums: Dict[str, float] = {f"P@{k}": 0.0 for k in ks}
    maxk = max(ks)
    sums[f"MAP@{maxk}"] = 0.0
    t0 = time.time()
    for p in prompts:
        rank = run_ranker(ranker, p["text"], candidates)
        rel = rel_map.get(p["id"], set())
        for k in ks:
            sums[f"P@{k}"] += precision_at_k(rank, rel, k)
        sums[f"MAP@{maxk}"] += average_precision_at_k(rank, rel, maxk)
    n = max(1, len(prompts))
    out = {m: round(v / n, 3) for m, v in sums.items()}
    out["latency_ms"] = round((time.time() - t0) * 1000 / n, 1)
    return out


# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Evaluate rankers on fixed prompt set.")
    parser.add_argument("--k", nargs="+", type=int, default=[3, 5], help="k values, e.g. --k 3 5")
    parser.add_argument("--rankers", nargs="+", default=["tfidf", "bm25", "embed"], help="rankers to run: tfidf bm25 embed")
    parser.add_argument("--domain", default="act", choices=["dest", "act", "acc", "trans"], help="TF-IDF domain to use")
    parser.add_argument("--slice", type=str, default=None, help="Path to artifacts slice (e.g., backend/artifacts/slice_v1)")
    args = parser.parse_args()

    # Determinism
    random.seed(42)
    try:
        import numpy as _np
        _np.random.seed(42)
    except Exception:
        pass

    # Load data either from slice or default data/ + candidates
    use_slice = args.slice is not None
    if use_slice:
        from pathlib import Path as _P
        from data_utils import load_slice
        slice_root = _P(args.slice)
        man, catalog, prompts, labels = load_slice(slice_root)
        # Build candidates from catalog subset
        def _as_text(x: dict) -> str:
            parts = [x.get("text") or "", x.get("name") or "", ", ".join(x.get("tags", []) or [])]
            return " \n".join(p for p in parts if p)
        candidates = [Candidate(id=str(x.get("id")), text=_as_text(x)) for x in catalog]
        # If the slice has prebuilt models, point MODELS_DIR to it
        global MODELS_DIR
        models_in_slice = slice_root / "models"
        if models_in_slice.exists():
            MODELS_DIR = models_in_slice
        out_dir = slice_root
    else:
        prompts_path = DATA_DIR / "prompts.json"
        labels_path = DATA_DIR / "labels.json"
        if not prompts_path.exists():
            raise SystemExit(f"Missing {prompts_path}. Create it with a list of prompts.")
        if not labels_path.exists():
            print(f"[warn] Missing {labels_path}. Creating a blank template matching prompts.")
            prompts = load_json(prompts_path)
            tpl = [{"prompt_id": p["id"], "relevant": []} for p in prompts]
            save_json(labels_path, tpl)
        prompts = load_json(prompts_path)
        labels = load_json(labels_path)
        candidates = load_candidates()
        out_dir = DATA_DIR

    # Build rankers
    ranker_objs: List[BaseRanker] = []
    rset = set(args.rankers)
    if "tfidf" in rset:
        try:
            ranker_objs.append(TFIDFRanker(domain=args.domain))
        except Exception as e:
            print(f"[warn] Skipping TF-IDF ranker: {e}")
    if "bm25" in rset:
        try:
            ranker_objs.append(BM25Ranker(candidates))
        except Exception as e:
            print(f"[warn] Skipping BM25 ranker: {e}")
    if "embed" in rset:
        try:
            ranker_objs.append(EmbeddingRanker(candidates))
        except Exception as e:
            print(f"[warn] Skipping Embedding ranker: {e}")

    ks = sorted(set(args.k))

    # Evaluate
    rows = []
    for r in ranker_objs:
        res = evaluate(r, prompts, labels, candidates, ks)
        row = {"ranker": r.name}
        row.update({f"P@{k}": res.get(f"P@{k}") for k in ks})
        row[f"MAP@{max(ks)}"] = res.get(f"MAP@{max(ks)}")
        row["latency_ms"] = res.get("latency_ms")
        rows.append(row)
        print(f"{r.name}: ", row)

    # Output CSV
    csv_path = out_dir / "eval_results.csv"
    csv_cols = ["Ranker"] + [f"P@{k}" for k in ks] + [f"MAP@{max(ks)}", "Avg latency (ms)"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(csv_cols)
        for row in rows:
            w.writerow([
                row["ranker"],
                *[row.get(f"P@{k}", "") for k in ks],
                row.get(f"MAP@{max(ks)}", ""),
                row.get("latency_ms", ""),
            ])

    # Output Markdown table
    md_path = out_dir / "eval_results.md"
    header = "| Ranker | " + " | ".join([f"P@{k}" for k in ks] + [f"MAP@{max(ks)}", "Avg latency (ms)"]) + " |\n"
    sep = "|" + " --- |" * (len(ks) + 3) + "\n"
    lines = [header, sep]
    for row in rows:
        vals = [row["ranker"], *[row.get(f"P@{k}", 0.0) for k in ks], row.get(f"MAP@{max(ks)}", 0.0), row.get("latency_ms", 0.0)]
        lines.append("| " + " | ".join(str(v) for v in vals) + " |\n")
    md_path.write_text("".join(lines), encoding="utf-8")

    print(f"\nSaved results to:\n- {csv_path}\n- {md_path}")


if __name__ == "__main__":
    main()
