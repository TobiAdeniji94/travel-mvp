# gen_nlp_table.py
import json, csv, sys
from pathlib import Path
import requests

SAMPLES = Path("samples.json")
API = "http://127.0.0.1:8000/api/v1/nlp/parse"

def main():
    if not SAMPLES.exists():
        print("samples.json not found", file=sys.stderr)
        sys.exit(1)
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    with open("nlp_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["idx","prompt_len","processing_time_s","parsed_keys"])
        for i, item in enumerate(samples):
            prompt = item["text"]
            try:
                r = requests.post(API, json={"text": prompt}, timeout=60)
                r.raise_for_status()
                data = r.json()
                t = data.get("processing_time", "")
                parsed = data.get("parsed_data") or {}
                keys = list(parsed.keys())
            except Exception as e:
                t, keys = "", []
                print(f"error on {i}: {e}", file=sys.stderr)
            w.writerow([i, len(prompt), t, keys])

if __name__ == "__main__":
    main()