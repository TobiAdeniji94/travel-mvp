import spacy
import dateparser
nlp = spacy.load("en_core_web_lg")

def parse_travel_request(text: str) -> dict:
    """Extract locations, dates, interests, budget from free-text."""
    doc = nlp(text)
    result = {"locations": [], "dates": [], "interests": [], "budget": None}
    for ent in doc.ents:
        if ent.label_ == "GPE":
            result["locations"].append(ent.text)
        elif ent.label_ == "DATE":
            dt = dateparser.parse(ent.text)
            if dt:
                result["dates"].append(dt)
        elif ent.label_ == "MONEY":
            result["budget"] = ent.text
    result["interests"] = [tok.lemma_ for tok in doc if tok.pos_ in ("NOUN", "PROPN") and tok.is_alpha]
    return result
