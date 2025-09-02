from __future__ import annotations
import os
import json
from typing import List
import logging

import torch

from app.core.settings import Settings
from ml.vocab import Vocab, BOS, EOS
from ml.models.transformer import Seq2SeqTransformer, TransformerConfig

logger = logging.getLogger(__name__)


class TransformerReorderer:
    def __init__(self, artifacts_dir: str):
        self.artifacts_dir = artifacts_dir
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        vocab_path = os.path.join(artifacts_dir, "vocab.json")
        cfg_path = os.path.join(artifacts_dir, "config.json")
        model_path = os.path.join(artifacts_dir, "model.pt")

        if not (os.path.exists(vocab_path) and os.path.exists(cfg_path) and os.path.exists(model_path)):
            raise FileNotFoundError("Transformer artifacts not found. Ensure training artifacts exist in artifacts dir.")

        self.vocab = Vocab.load(vocab_path)
        with open(cfg_path, "r", encoding="utf-8") as f:
            data_cfg = json.load(f)
        # minimal model config; data_cfg has vocab_size/pad_id/bos_id/max lengths
        model_cfg = TransformerConfig(vocab_size=data_cfg["vocab_size"])  # use defaults for others
        self.pad_id = data_cfg["pad_id"]
        self.bos_id = data_cfg["bos_id"]
        self.eos_id = self.vocab.stoi[EOS]

        self.model = Seq2SeqTransformer(model_cfg, pad_id=self.pad_id).to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

    @torch.no_grad()
    def reorder(self, poi_ids: List[str], max_len: int | None = None) -> List[str]:
        # Encode source as ids
        src_ids = [self.vocab.stoi.get(pid, self.vocab.stoi.get("<unk>")) for pid in poi_ids]
        src = torch.tensor(src_ids, dtype=torch.long, device=self.device).unsqueeze(0)  # (1, S)
        # Decode greedily
        if max_len is None:
            max_len = len(poi_ids) + 2
        decoded = self.model.greedy_decode(src, max_len=max_len, bos_id=self.bos_id, eos_id=self.eos_id)  # (1, T)
        out_ids = decoded.squeeze(0).tolist()
        # Remove BOS and stop at EOS
        cleaned: List[str] = []
        for tid in out_ids:
            if tid == self.bos_id:
                continue
            if tid == self.eos_id:
                break
            tok = self.vocab.itos[tid]
            cleaned.append(tok)
        # Keep only POIs from input and preserve decoded order
        input_set = set(poi_ids)
        filtered = [t for t in cleaned if t in input_set]
        # If decode missed some, append remaining to keep full permutation
        remaining = [t for t in poi_ids if t not in filtered]
        return filtered + remaining


_reorderer: TransformerReorderer | None = None


def get_reorderer() -> TransformerReorderer | None:
    global _reorderer
    settings = Settings()
    if not settings.ENABLE_TRANSFORMER:
        return None
    if _reorderer is None:
        try:
            _reorderer = TransformerReorderer(settings.TRANSFORMER_ARTIFACTS)
            logger.info("TransformerReorderer loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load TransformerReorderer: {e}")
            _reorderer = None
    return _reorderer


def reorder_pois(poi_ids: List[str]) -> List[str]:
    """Reorder a list of POI UUID strings using the trained Transformer.
    Returns the input order unchanged if transformer is disabled or not available.
    """
    r = get_reorderer()
    if r is None:
        return poi_ids
    try:
        return r.reorder(poi_ids)
    except Exception as e:
        logger.error(f"Transformer reorder failed, falling back: {e}")
        return poi_ids
