import spacy
import re
from dateparser.search import search_dates
from datetime import datetime, timezone
import dateparser

nlp = spacy.load("en_core_web_lg")

def extract_date_range(text: str):
    """Extracts a date range or single date from the text."""
    # find a date range with "from" and "to"
    m = re.search(
        r'from\s+(.+?)\s+(?:to|until)\s+(.+?)(?:[.,]|$)',
        text, flags=re.IGNORECASE
    )
    if m:
        d1 = dateparser.parse(
            m.group(1),
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "TIMEZONE": "UTC",
            }
        )
        d2 = dateparser.parse(
            m.group(2),
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "TIMEZONE": "UTC",
            }
        )
        if d1 and d2:
            return (min(d1, d2), max(d1, d2))

    # try to find a single date
    raw = search_dates(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": "UTC",
        }
    )
    if not raw:
        return None, None

    # filter out money / pure digits
    filtered = [
        (frag, dt) for frag, dt in raw
        if "$" not in frag and not frag.strip().isdigit()
    ]
    if not filtered:
        return None, None

    dts = [dt for _, dt in filtered]
    return (min(dts), max(dts))


def parse_travel_request(text: str) -> dict:
    """Extract locations, dates, interests, budget from free-text."""
    doc = nlp(text)
    result = {
        "locations": [], 
        "dates": [], 
        "interests": [], 
        "budget": None,
    }

    # Locations (GPE, LOC)
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC"):
            result["locations"].append(ent.text)
    
    # Date range via dateparser
    start, end = extract_date_range(text)
    if start and end:
        if start.date() == end.date():
            result["dates"] = [start]
        else:
            result["dates"] = [start, end]
    
    # Budget (MONEY)
    for ent in doc.ents:
        if ent.label_ == "MONEY":
            amt = dateparser.parse(
                ent.text,
                settings={"RETURN_AS_TIMEZONE_AWARE": False}
            )
            if amt and hasattr(amt, "amount"):
                result["budget"] = float(amt.amount)
            else:
                # crude numeric fallback
                cleaned = ent.text.replace("$", "").replace(",", "")
                if cleaned.replace(".", "", 1).isdigit():
                    result["budget"] = float(cleaned)

    # Build a set of all tokens that were part of spaCy DATE ents
    date_tokens = {
        tok.text.lower()
        for ent in doc.ents
        if ent.label_ == "DATE"
        for tok in ent
        if tok.is_alpha
    }

    # Interests: all NOUN/PROPN minus locations & date words
    seen = set()
    for tok in doc:
        lemma = tok.lemma_.lower()
        if (
            tok.pos_ in ("NOUN", "PROPN")
            and tok.is_alpha
            and lemma not in seen
            and tok.text not in result["locations"]
            and tok.text.lower() not in date_tokens
        ):
            seen.add(lemma)
            result["interests"].append(lemma)

    print(f"Parsed request: {result}")
    return result
