#!/usr/bin/env python3
"""
Quality Gates Runner — parser accuracy, ranking quality (P@K/R@K),
feasibility checks, and performance sampling.

Usage:
  python run_quality_gates.py \
    --prompts prompts.json \
    --labels labels.json \
    --candidates candidates.json \
    --parser_eval parser_eval_set.json \
    --k 10 \
    --runs 30 \
    [--itineraries_glob "out/itins/*.json"] \
    [--daily_budget 150]

Outputs:
  - quality_report.json
  - ranking_diagnostics.csv
  - parser_eval_report.json
  - feasibility_report.json
  - perf_samples.json

Notes:
  - Requires scikit-learn installed.
  - If --itineraries_glob is provided, feasibility is computed on those itineraries;
    otherwise synthetic demo days are used.
"""
import argparse, time, json, math, statistics, sys, glob
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# ---------------- Utilities ----------------

def p50(nums: List[float]) -> float:
    return float(statistics.median(nums)) if nums else 0.0

def p95(nums: List[float]) -> float:
    if not nums: return 0.0
    s = sorted(nums)
    idx = int(math.ceil(0.95 * len(s))) - 1
    return float(s[max(0, min(idx, len(s)-1))])

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
# ---------------- Ranking (TF-IDF baseline) ----------------

def ranking_eval(prompts_path: str, labels_path: str, candidates_path: str, k: int = 10) -> Dict[str, Any]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts = json.load(f)
    with open(labels_path, "r", encoding="utf-8") as f:
        labels = json.load(f)
    with open(candidates_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    cand_ids = [c["id"] for c in candidates]
    cand_texts = [c.get("text", "") for c in candidates]

    vec = TfidfVectorizer(stop_words="english", ngram_range=(1,2), min_df=1)
    X = vec.fit_transform(cand_texts)

    gold: Dict[str, set] = {row["prompt_id"]: set(row["relevant"]) for row in labels}

    rows = []
    hits, total_rels, total_pred = 0, 0, 0

    for p in prompts:
        pid, text = p["id"], p["text"]
        qv = vec.transform([text])
        scores = cosine_similarity(qv, X).ravel()
        order = scores.argsort()[::-1][:k]
        topk_ids = [cand_ids[i] for i in order]

        rel = gold.get(pid, set())
        hit_count = sum(1 for _id in topk_ids if _id in rel)
        hits += hit_count
        total_rels += len(rel)
        total_pred += k

        for rank, idx in enumerate(order, start=1):
            rows.append({
                "prompt_id": pid,
                "rank": rank,
                "candidate_id": cand_ids[idx],
                "is_relevant": int(cand_ids[idx] in rel),
                "score": float(scores[idx])
            })

    P_at_k = (hits / total_pred) if total_pred else 0.0
    R_at_k = (hits / total_rels) if total_rels else 0.0

    import csv
    with open("ranking_diagnostics.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["prompt_id","rank","candidate_id","is_relevant","score"])
        w.writeheader()
        w.writerows(rows)

    return {
        "k": k,
        "prompts": len(prompts),
        "candidates": len(candidates),
        "micro_P_at_k": round(P_at_k, 4),
        "micro_R_at_k": round(R_at_k, 4),
        "hits": hits,
        "total_pred": total_pred,
        "total_relevant": total_rels,
        "diagnostics_csv": "ranking_diagnostics.csv"
    }

# ---------------- Parser slot accuracy ----------------

def try_import_parser():
    # Local parser.py
    try:
        import importlib
        mod = importlib.import_module("parser")
        if hasattr(mod, "parse_travel_request"):
            return getattr(mod, "parse_travel_request")
    except Exception:
        pass
    # App-style path
    try:
        import importlib
        mod = importlib.import_module("app.core.nlp.parser")
        if hasattr(mod, "parse_travel_request"):
            return getattr(mod, "parse_travel_request")
    except Exception:
        pass
    return None

def norm_money(x):
    if x is None: return None
    try:
        return float(x)
    except Exception:
        try:
            import decimal
            return float(decimal.Decimal(str(x)))
        except Exception:
            return None

def str_set(xs):
    return set([str(x).strip().lower() for x in xs if x is not None])

def parser_eval(eval_path: str) -> Dict[str, Any]:
    parse_fn = try_import_parser()

    with open(eval_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if parse_fn is None:
        return {
            "ran": False,
            "error": "parse_travel_request() not found",
            "hint": "Expose parse_travel_request(text: str) -> dict with keys: locations, dates, interests, budget.",
            "cases": len(cases)
        }

    def score_case(case):
        text = case["text"]
        expect = case["expected"]
        out = parse_fn(text)

        exp_locs = str_set(expect.get("locations", []))
        exp_interests = str_set(expect.get("interests", []))
        exp_budget = norm_money(expect.get("budget"))
        exp_dates = expect.get("dates", [])

        got_locs = str_set(out.get("locations", []))
        got_interests = str_set(out.get("interests", []))
        got_budget = norm_money(out.get("budget"))
        got_dates = out.get("dates", [])

        loc_ok  = (len(exp_locs)==0) or (len(got_locs & exp_locs) >= min(1, len(exp_locs)))
        int_ok  = (len(exp_interests)==0) or (len(got_interests & exp_interests) >= min(1, len(exp_interests)))
        bud_ok  = (exp_budget is None) or (got_budget is not None and abs(got_budget - exp_budget) <= 0.05 * exp_budget)
        date_ok = (len(exp_dates)==0) or (len(got_dates) >= 1)

        return {"text": text, "loc_ok": int(loc_ok), "int_ok": int(int_ok), "bud_ok": int(bud_ok), "date_ok": int(date_ok)}

    scored = [score_case(c) for c in cases]

    loc_acc  = sum(s["loc_ok"] for s in scored) / len(scored) if scored else 0.0
    int_acc  = sum(s["int_ok"] for s in scored) / len(scored) if scored else 0.0
    bud_acc  = sum(s["bud_ok"] for s in scored) / len(scored) if scored else 0.0
    date_acc = sum(s["date_ok"] for s in scored) / len(scored) if scored else 0.0

    report = {
        "ran": True,
        "cases": len(scored),
        "slot_accuracy": {
            "locations": round(loc_acc, 4),
            "interests": round(int_acc, 4),
            "budget": round(bud_acc, 4),
            "dates": round(date_acc, 4)
        },
        "per_case": scored
    }
    with open("parser_eval_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report

# ---------------- Feasibility checks ----------------

_TIME_KEYS = {
    "opens":  ["opens","open","open_time","opening","opening_time","openAt"],
    "closes": ["closes","close","close_time","closing","closing_time","closeAt"],
    "start":  ["start","start_time","startAt","begin","from"],
    "end":    ["end","end_time","endAt","finish","to"],
}
_PRICE_KEYS = ["price","cost","fee","amount","ticket","entry_price","ticket_price"]

def _parse_ts(x):
    import datetime as _dt
    if isinstance(x, (int, float)):  return _dt.datetime.utcfromtimestamp(x)
    if isinstance(x, str):
        try: return _dt.datetime.fromisoformat(x.replace("Z","").replace("+00:00",""))
        except Exception: pass
    raise ValueError(f"Bad timestamp: {x}")

def _first_key(d: Dict[str, Any], names: List[str]):
    for n in names:
        if n in d: return n
    return None

def _normalize_item(it: Dict[str, Any]) -> Dict[str, Any]:
    o = {}
    for k, keys in _TIME_KEYS.items():
        found = _first_key(it, keys)
        if found is None: raise KeyError(f"Missing time field for '{k}' in item: {list(it.keys())}")
        o[k] = it[found]
    pk = _first_key(it, _PRICE_KEYS)
    o["price"] = float(it.get(pk, 0.0)) if pk else 0.0
    return o

def feasibility_checks(day_plan: List[Dict[str, Any]], daily_budget: Optional[float]=None) -> Dict[str, Any]:
    items = sorted([_normalize_item(x) for x in day_plan], key=lambda d: _parse_ts(d["start"]))

    open_pass = True
    overlap_pass = True
    for i, it in enumerate(items):
        s, e = _parse_ts(it["start"]), _parse_ts(it["end"])
        o, c = _parse_ts(it["opens"]), _parse_ts(it["closes"])
        if s < o or e > c:
            open_pass = False
        if i > 0 and s < _parse_ts(items[i-1]["end"]):
            overlap_pass = False

    budget_pass = True
    if daily_budget is not None:
        total_price = sum(float(it.get("price", 0.0)) for it in items)
        budget_pass = (total_price <= float(daily_budget))

    return {"open_hours_pass": int(open_pass), "overlap_pass": int(overlap_pass), "budget_pass": int(budget_pass)}

def feasibility_eval(sample_days: List[List[Dict[str, Any]]], daily_budget: Optional[float]) -> Dict[str, Any]:
    results = [feasibility_checks(day, daily_budget) for day in sample_days]
    if not results:
        report = {"days": 0, "feasible_days": 0, "feasible_rate": 0.0, "per_day": []}
        with open("feasibility_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return report
    ok = sum(1 for r in results if r["open_hours_pass"] and r["overlap_pass"] and r["budget_pass"])
    rate = ok / len(results)
    report = {"days": len(results), "feasible_days": ok, "feasible_rate": round(rate, 4), "per_day": results}
    with open("feasibility_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report

def _looks_like_day_list(obj) -> bool:
    if not isinstance(obj, list): return False
    return bool(obj) and isinstance(obj[0], dict) and any(k in obj[0] for ks in _TIME_KEYS.values() for k in ks)

def _extract_days_from_obj(obj):
    if isinstance(obj, list) and obj and isinstance(obj[0], list):
        if all(_looks_like_day_list(day) for day in obj): return obj
    if _looks_like_day_list(obj): return [obj]
    if isinstance(obj, dict):
        for key in ["days","itinerary","plan","schedule","itinerary_days"]:
            if key in obj: return _extract_days_from_obj(obj[key])
    return None

def load_itineraries_from_glob(pattern: str) -> Dict[str, Any]:
    files = sorted(glob.glob(pattern))
    all_days = []
    inferred_daily_budget = None

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[feasibility] WARN: failed to read {fp}: {e}", file=sys.stderr)
            continue

        days = _extract_days_from_obj(data)
        if not days:
            print(f"[feasibility] WARN: no days found in {fp}", file=sys.stderr)
            continue
        all_days.extend(days)

        try:
            if isinstance(data, dict):
                if "daily_budget" in data and isinstance(data["daily_budget"], (int,float)):
                    inferred_daily_budget = float(data["daily_budget"])
                elif "budget_per_day" in data and isinstance(data["budget_per_day"], (int,float)):
                    inferred_daily_budget = float(data["budget_per_day"])
                elif "budget" in data and isinstance(data["budget"], (int,float)) and len(days) > 0:
                    inferred_daily_budget = float(data["budget"]) / float(len(days))
        except Exception:
            pass

    return {"files": files, "days": all_days, "inferred_daily_budget": inferred_daily_budget}

# ---------------- Performance sampler ----------------

def performance_sampler(prompts_path: str, candidates_path: str, runs: int = 30) -> Dict[str, Any]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    try:
        parse_fn = try_import_parser()
    except Exception:
        parse_fn = None

    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts = json.load(f)
    with open(candidates_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    cand_texts = [c.get("text","") for c in candidates]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1,2), min_df=1)
    X = vec.fit_transform(cand_texts)

    t_parse, t_rank, t_sched, t_total = [], [], [], []

    for i in range(min(runs, len(prompts))):
        text = prompts[i]["text"]

        t0 = time.perf_counter()

        t_p0 = time.perf_counter()
        if parse_fn is not None:
            try: _ = parse_fn(text)
            except Exception: pass
        t_p1 = time.perf_counter()

        t_r0 = time.perf_counter()
        qv = vec.transform([text])
        _ = cosine_similarity(qv, X).ravel().argsort()[::-1][:10]
        t_r1 = time.perf_counter()

        t_s0 = time.perf_counter()
        sample_day = [
            {"opens": "2025-01-01T09:00:00","closes": "2025-01-01T17:00:00","start": "2025-01-01T10:00:00","end": "2025-01-01T11:00:00","price": 25.0},
            {"opens": "2025-01-01T11:10:00","closes": "2025-01-01T18:00:00","start": "2025-01-01T11:30:00","end": "2025-01-01T12:10:00","price": 0.0},
            {"opens": "2025-01-01T12:00:00","closes": "2025-01-01T21:00:00","start": "2025-01-01T12:25:00","end": "2025-01-01T13:10:00","price": 18.0}
        ]
        _ = feasibility_checks(sample_day, daily_budget=100.0)
        t_s1 = time.perf_counter()

        t1 = time.perf_counter()

        t_parse.append((t_p1 - t_p0) * 1000.0)
        t_rank.append((t_r1 - t_r0) * 1000.0)
        t_sched.append((t_s1 - t_s0) * 1000.0)
        t_total.append((t1 - t0) * 1000.0)

    report = {
        "runs": len(t_total),
        "parse_ms": {"p50": round(p50(t_parse),2), "p95": round(p95(t_parse),2)},
        "rank_ms":  {"p50": round(p50(t_rank),2),  "p95": round(p95(t_rank),2)},
        "sched_ms": {"p50": round(p50(t_sched),2), "p95": round(p95(t_sched),2)},
        "total_ms": {"p50": round(p50(t_total),2), "p95": round(p95(t_total),2)},
        "samples": {
            "parse_ms": [round(x,2) for x in t_parse],
            "rank_ms":  [round(x,2) for x in t_rank],
            "sched_ms": [round(x,2) for x in t_sched],
            "total_ms": [round(x,2) for x in t_total],
        }
    }
    with open("perf_samples.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report

# ---------------- Main glue ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default="prompts.json")
    ap.add_argument("--labels", default="labels.json")
    ap.add_argument("--candidates", default="candidates.json")
    ap.add_argument("--parser_eval", default="parser_eval_set.json")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--daily_budget", type=float, default=150.0, help="Fallback daily budget if not inferred from itineraries.")
    ap.add_argument("--itineraries_glob", default=None, help="Glob for itinerary JSONs (e.g., out/itins/*.json).")
    args = ap.parse_args()

    report = {"generated_at": now_iso(), "gates": {}}

    # Ranking
    try:
        r = ranking_eval(args.prompts, args.labels, args.candidates, args.k)
        report["gates"]["ranking_quality"] = r
        print(f"[ranking] P@{args.k}={r['micro_P_at_k']:.4f}  R@{args.k}={r['micro_R_at_k']:.4f}")
    except Exception as e:
        report["gates"]["ranking_quality"] = {"error": str(e)}
        print(f"[ranking] ERROR: {e}", file=sys.stderr)

    # Parser
    try:
        p = parser_eval(args.parser_eval)
        report["gates"]["parser_accuracy"] = p
        if p.get("ran"):
            slots = p.get("slot_accuracy",{})
            print(f"[parser] slots -> locations={slots.get('locations',0):.2f}, interests={slots.get('interests',0):.2f}, budget={slots.get('budget',0):.2f}, dates={slots.get('dates',0):.2f}")
        else:
            print(f"[parser] SKIPPED: {p.get('error')}")
    except Exception as e:
        report["gates"]["parser_accuracy"] = {"error": str(e)}
        print(f"[parser] ERROR: {e}", file=sys.stderr)

    # Feasibility
    try:
        used_glob = False
        if args.itineraries_glob:
            loaded = load_itineraries_from_glob(args.itineraries_glob)
            days = loaded["days"]
            inferred = loaded["inferred_daily_budget"]
            budget_used = inferred if (inferred is not None) else args.daily_budget
            used_glob = True
        else:
            days = [[
                {"opens":"2025-01-01T09:00:00","closes":"2025-01-01T17:00:00","start":"2025-01-01T09:10:00","end":"2025-01-01T10:00:00","price":10.0},
                {"opens":"2025-01-01T10:10:00","closes":"2025-01-01T18:00:00","start":"2025-01-01T10:20:00","end":"2025-01-01T11:00:00","price":0.0},
                {"opens":"2025-01-01T11:10:00","closes":"2025-01-01T20:00:00","start":"2025-01-01T11:20:00","end":"2025-01-01T12:15:00","price":20.0}
            ],[
                {"opens":"2025-01-02T09:00:00","closes":"2025-01-02T10:00:00","start":"2025-01-02T08:50:00","end":"2025-01-02T09:30:00","price":5.0},
                {"opens":"2025-01-02T09:40:00","closes":"2025-01-02T18:00:00","start":"2025-01-02T09:35:00","end":"2025-01-02T09:50:00","price":5.0}
            ]]
            budget_used = args.daily_budget

        fz = feasibility_eval(days, daily_budget=budget_used)
        report["gates"]["feasibility_rate"] = {**fz, "source": "itineraries_glob" if used_glob else "synthetic", "budget_used": budget_used}
        print(f"[feasibility] feasible_days={fz['feasible_days']}/{fz['days']}  rate={fz['feasible_rate']:.2f}  (budget_used={budget_used})")
    except Exception as e:
        report["gates"]["feasibility_rate"] = {"error": str(e)}
        print(f"[feasibility] ERROR: {e}", file=sys.stderr)

    # Performance
    try:
        perf = performance_sampler(args.prompts, args.candidates, args.runs)
        report["gates"]["performance"] = perf
        print(f"[perf] total_ms p50={perf['total_ms']['p50']:.2f}  p95={perf['total_ms']['p95']:.2f}")
    except Exception as e:
        report["gates"]["performance"] = {"error": str(e)}
        print(f"[perf] ERROR: {e}", file=sys.stderr)

    with open("quality_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    main()
