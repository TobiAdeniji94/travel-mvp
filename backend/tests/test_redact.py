import json
from app.main import redact_api_keys


def test_redact_simple_key():
    event = {"url": "https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference=ABC123&key=AIzaSECRET"}
    out = redact_api_keys(None, None, event.copy())
    assert "key=REDACTED" in out["url"] or "REDACTED" in out["url"]


def test_redact_token_in_list():
    event = {"images": ["https://maps.googleapis.com/maps/api/place/photo?photoreference=XYZ&key=AIzaSECRET"]}
    out = redact_api_keys(None, None, event.copy())
    assert any("REDACTED" in s for s in out["images"]) or all(not s.endswith("AIzaSECRET") for s in out["images"])


def test_redact_nested():
    event = {"a": {"b": ["foo", "https://...&key=AIzaSECRET"]}}
    out = redact_api_keys(None, None, event.copy())
    assert any("REDACTED" in x for x in out["a"]["b"]) or all("AIzaSECRET" not in x for x in out["a"]["b"]) 
