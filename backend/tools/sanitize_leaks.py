#!/usr/bin/env python3
"""Sanitize repository files by replacing known leaked API key occurrences.

Run in repo root: python backend/tools/sanitize_leaks.py
"""
import os
from pathlib import Path

LEAKED_KEY = "REDACTED"
REPLACEMENT = "REDACTED"

TEXT_FILE_EXTS = {".py", ".csv", ".json", ".md", ".txt", ".yaml", ".yml", ".env"}

root = Path(__file__).resolve().parents[2]
print(f"Scanning {root} for leaked key...")

for p in root.rglob("*"):
    if p.is_file():
        try:
            if p.suffix.lower() in TEXT_FILE_EXTS or p.match("*.csv") or p.match("*.json"):
                text = p.read_text(encoding="utf-8")
                if LEAKED_KEY in text:
                    new = text.replace(LEAKED_KEY, REPLACEMENT)
                    p.write_text(new, encoding="utf-8")
                    print(f"Replaced key in: {p}")
        except Exception as e:
            print(f"Skipped {p}: {e}")

print("Sanitization complete. Review changes and commit.")
