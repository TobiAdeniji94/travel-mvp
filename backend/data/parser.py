# parser.py — tiny demo shim; replace with your real parser and mapping
import re

def parse_travel_request(text: str) -> dict:
    t = text.lower()
    out = {"locations": [], "interests": [], "budget": None, "dates": []}

    # toy location pick-up
    for city in ["paris","tokyo","lagos","rome","zurich","new york"]:
        if city in t:
            out["locations"].append(city.title())

    # toy interests
    if "museum" in t: out["interests"].append("museum")
    if "kid" in t or "family" in t: out["interests"].append("family")
    if "nightlife" in t: out["interests"].append("nightlife")
    if "ski" in t: out["interests"].append("skiing")

    # toy budget extraction
    m = re.search(r'(\d+[.,]?\d*)\s*(usd|\$|eur|€|chf)?', t)
    if m: out["budget"] = float(m.group(1).replace(',', ''))

    # toy dates presence
    if any(w in t for w in ["today","tomorrow","weekend","month","january","december","spring","next week"]):
        out["dates"] = ["*"]

    return out
