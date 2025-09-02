from pathlib import Path
import json
import hashlib
from typing import Tuple, List, Dict, Any


def sha256(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def load_slice(root: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load a frozen evaluation slice and verify checksums.

    Returns: (manifest, catalog_subset, prompts, labels)
    """
    root = Path(root)
    man_path = root / "manifest.json"
    if not man_path.exists():
        raise FileNotFoundError(f"Missing manifest: {man_path}")
    man = json.loads(man_path.read_text(encoding="utf-8"))

    checks = man.get("checksums", {})
    for fname, declared in checks.items():
        path = root / fname
        if not path.exists():
            raise FileNotFoundError(f"Missing artifact file: {path}")
        actual = sha256(path)
        assert actual == declared, f"Checksum mismatch for {fname}: {actual} != {declared}"

    catalog = json.loads((root / "catalog_subset.json").read_text(encoding="utf-8"))
    prompts = json.loads((root / "prompts.json").read_text(encoding="utf-8"))
    labels  = json.loads((root / "labels.json").read_text(encoding="utf-8"))
    return man, catalog, prompts, labels
