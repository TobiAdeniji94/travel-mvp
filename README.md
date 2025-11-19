# Travel-MVP

> Parse free-text trip requests, rank POIs, and assemble time-feasible daily plans.
> **Pipeline:** Parse → Rank → Assemble → Persist

---

## Table of Contents

* [Overview](#overview)
* [Features](#features)
* [System Architecture](#system-architecture)
* [Tech Stack](#tech-stack)
* [Screenshots](#screenshots)
* [Quickstart](#quickstart)
* [Configuration](#configuration)
* [Data & Artifacts](#data--artifacts)
* [API Reference](#api-reference)
* [Evaluation](#evaluation)
* [Project Structure](#project-structure)
* [Roadmap](#roadmap)
* [Contributing](#contributing)
* [License](#license)
* [Acknowledgements](#acknowledgements)
* [Citation](#citation)

---

## Overview

This MVP generates **personalized, feasible itineraries** from a single free-text request. It uses **rule/statistical NLP** for intent parsing, **TF-IDF/BM25** for ranking over a curated catalog, and a **time-aware greedy scheduler** that respects opening hours, pacing, distance, and budget. Deterministic artifacts keep results reproducible.

---

## Features

* **NLP Parse:** Extracts city, dates, budget, interests, and simple constraints from free text.
* **Ranking:** TF-IDF/BM25 over curated POI catalogs (destinations/activities/acc/transport).
* **Scheduling:** Greedy, time-aware day plans with open/close windows, max stops/day, and per-day budget caps.
* **Persistence & UI:** Save/view/delete itineraries via FastAPI + Next.js.
* **Determinism:** Versioned artifacts, reproducible runs, and stable tie-breakers.
* **Observability:** Structured JSON logging with request correlation IDs, Prometheus metrics, component health checks, and performance timers.

---

## System Architecture

```
Next.js (Frontend)
   │
   ├── POST /nlp/parse  ──► NLP Service (spaCy + regex/dateparser)
   │
   └── POST /itineraries/generate ─► Itinerary Service
          ├─ Load artifacts (TF-IDF/BM25 matrices, id maps)
          ├─ Rank candidates (city mask, Top-K)
          ├─ Time-aware scheduler (open hours, budget, pace)
          └─ Persist to PostgreSQL (itineraries + items)
```

---

## Tech Stack

* **Frontend:** Next.js, React, Tailwind (protected routes, builder/viewer pages)
* **Backend:** FastAPI (Python 3.11), spaCy, scikit-learn (TF-IDF), optional BM25
* **DB:** PostgreSQL (optionally PostGIS image in infra)
* **Infra:** Docker Compose, `.env` configuration
* **Testing & Dev:** pre-commit, linting/typing, simple unit tests

---

## Screenshots

* Dashboard
![travel-mvp-dashboard](<misc/Screenshot 2025-08-17 031309.png>)
* Builder (request → parsed summary)
![travel-mvp-builder-request](<misc/Screenshot 2025-08-17 031527.png>)
![travel-mvp-builder-parsed-summary](<misc/Screenshot 2025-08-17 031646.png>)
* Itinerary viewer (per-day stops, times, estimated costs)
![travel-mvp-itinerary-viewer](<misc/Screenshot 2025-08-17 031834.png>)

---

## Quickstart

### 1) Prerequisites

* Docker & Docker Compose
* (Dev only) Python 3.11, Node 18+

### 2) Clone

```bash
git clone https://github.com/<you>/travel-mvp.git
cd travel-mvp
```

### 3) Environment

**Backend:**
```bash
cp .env.example .env
# Edit .env with your database credentials and API keys
```

**Frontend:**
```bash
cd frontend
cp .env.example .env.local
# Default: NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### 4) One-shot run (Docker)

```bash
cd infrastructure
docker compose up --build
```

* API health: `http://localhost:8000/api/v1/security/health`
* Frontend: `http://localhost:3000`

### 5) (First run) Seed catalog & build artifacts

Inside backend container (or your venv):

```bash
# seed curated CSV/JSON into DB
python backend/scripts/seed_catalog.py

# build TF-IDF/BM25 artifacts
python backend/scripts/train_all_models.py
```

Restart the backend (or ensure artifacts are mounted under `/app/models`).

---

## Configuration

Key environment variables (set in `.env`):

| Variable         | Example                              | Purpose                  |
| ---------------- | ------------------------------------ | ------------------------ |
| `DB_URL`         | `postgresql://user:pass@db:5432/app` | Database connection      |
| `JWT_SECRET`     | `change_me`                          | Auth tokens              |
| `TFIDF_PATH`     | `/app/models`                        | Artifacts mount path     |
| `TOPK`           | `50`                                 | Candidate shortlist size |
| `DAILY_STOP_CAP` | `5`                                  | Max activities per day   |
| `DEFAULT_START`  | `10:00`                              | Day start time           |
| `MODEL_NAME`     | `en_core_web_lg`                     | spaCy model              |
| Feature flags    | `ENABLE_RATE_LIMITING=false`         | Toggle optional features |

---

## Data & Artifacts

* **Catalogs:** curated CSV/JSON for destinations, activities (with hours/price/rating), accommodations, transport.
* **Artifacts (generated):**
  `tfidf_vectorizer_{dest|act|acc|trans}.pkl`
  `tfidf_matrix_{dest|act|acc|trans}.npz`
  `item_index_map_{dest|act|acc|trans}.pkl`
* **Reproducibility:** versions and hash digests printed on startup; identical inputs ⇒ identical outputs.

---

## API Reference

### `POST /nlp/parse`

Turns free text into a structured intent.

**Request**

```json
{ "text": "3-day art & food in Lagos in April, ₦300k" }
```

**Response (abridged)**

```json
{
  "parsed": {
    "city": "Lagos",
    "start_date": "2025-04-04",
    "end_date": "2025-04-06",
    "budget_total": 300000,
    "interests": ["art", "food"],
    "pace": "moderate"
  },
  "processing_ms": 120,
  "confidence": 0.92
}
```

### `POST /itineraries/generate`

Parses intent (or accepts structured payload), ranks Top-K POIs, builds a feasible schedule, persists, and returns the itinerary.

**Request (minimal)**

```json
{
  "text": "2 days in Nairobi under $400, museums + street food",
  "save": true
}
```

**Response (abridged)**

```json
{
  "itinerary_id": "uuid",
  "city": "Nairobi",
  "days": [
    {
      "date": "2025-06-12",
      "stops": [
        {"poi_id":"...","name":"National Museum","start":"10:30","end":"12:00","est_cost":10}
      ]
    }
  ],
  "notes": ["All stops within opening hours"]
}
```

> Additional endpoints: list/get/delete itineraries (auth-protected).

---

## Evaluation

* **Parsing:** ≥90% correct extraction (city/dates/budget) on labeled set; ≥95% at least one relevant interest.
* **Ranking:** Precision\@10 ≥ 0.60 on canonical intents; Diversity\@10 ≥ 0.60.
* **Scheduling:** 100% stops within opening windows; 0 overlaps; ≥95% daily-budget compliance.
* **Latency (target):** p50 < 1.0 s, p95 < 2.0 s for parse→rank→schedule on the reference machine.

**Run**

```bash
# example
python eval.py --k 3 5 --rankers tfidf bm25 embed --domain act
```

---

## Project Structure

```
.
├─ frontend/                 # Next.js app (auth, builder, viewer)
├─ backend/
│  ├─ app/                   # FastAPI services (NLP, Itinerary)
│  ├─ models/                # (mounted) TF-IDF/BM25 artifacts
│  ├─ scripts/
│  │  ├─ seed_catalog.py
│  │  └─ train_all_models.py
│  └─ tests/                 # unit tests (parse/rank/schedule)
├─ infra/                    # docker-compose, DB config
├─ docs/                     # diagrams, screenshots, API examples
├─ .env.example
└─ README.md
```

---

## Observability

The application includes comprehensive observability features for monitoring and debugging:

### Structured Logging
- **JSON format** logs for machine-queryable output
- **Request correlation IDs** (`X-Request-ID` header) for tracing multi-stage flows
- **Contextual metadata** including user IDs, processing times, and business metrics
- Logs written to `app.log` and stdout

**Example log entry:**
```json
{
  "event": "nlp_parse_endpoint_success",
  "timestamp": "2025-11-18T18:50:23.456Z",
  "level": "info",
  "request_id": "a3f2c8d1-...",
  "text_length": 145,
  "processing_time_ms": 234.5,
  "confidence_score": 0.87,
  "parsed_fields": ["destination", "dates", "budget"]
}
```

### Metrics Endpoint
- **Prometheus-compatible** metrics at `/metrics`
- Automatic instrumentation of all HTTP endpoints
- Tracks: request rate, latency percentiles, error rate, in-flight requests

**Query logs:**
```bash
# View logs with jq
cat app.log | jq 'select(.event=="user_login_success")'

# Find slow requests
cat app.log | jq 'select(.duration_ms > 1000)'

# Trace a specific request
cat app.log | jq 'select(.request_id=="a3f2c8d1-...")'
```

### Health Checks
- **Basic health:** `GET /` - API liveness
- **Detailed health:** `GET /health` - Component-level status (database, ML models, API)
- Returns structured JSON with component health and timestamp

### Performance Monitoring
- `performance_timer` context manager tracks operation durations
- Logged for: NLP parsing, authentication, itinerary generation, ML model inference

---

## Roadmap

* [ ] Live APIs: maps/hours/events/weather/flights behind feature flags
* [ ] LLM-assisted parsing & re-ranking; A/B BM25 vs embeddings
* [ ] Incremental re-planning with real-time triggers
* [ ] Collaboration (shared itineraries, comments), bookings/payments
* [ ] Explainability ("why this place?") + feedback loops
* [ ] Multilingual catalogs, fairness audits, alerting/dashboards

---

## Contributing

1. Fork & create a feature branch
2. Run `pre-commit install` (lint/type checks)
3. Add tests for new behavior
4. Open a PR with a clear description and screenshots where relevant

---

## License

MIT — see [`LICENSE`](./LICENSE).

---

## Acknowledgements

* spaCy, scikit-learn, FastAPI, Next.js, PostgreSQL
* Faculty advisors and reviewers

---

## Citation

If you use this project in academic work, please cite as:

```
Adeniji, I. (2025). Design and Implementation of a Smart Travel Itinerary Generator. B.Sc. Project, University of Lagos.
```
