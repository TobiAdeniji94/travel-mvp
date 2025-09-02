from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Iterable
import json

# Special tokens
PAD = "<pad>"
BOS = "<bos>"
EOS = "<eos>"
UNK = "<unk>"

SPECIAL_TOKENS = [PAD, BOS, EOS, UNK]

@dataclass
class Vocab:
    stoi: Dict[str, int]
    itos: List[str]

    @classmethod
    def build(cls, token_sequences: Iterable[Iterable[str]]) -> "Vocab":
        stoi: Dict[str, int] = {}
        itos: List[str] = []

        # reserve special tokens
        for tok in SPECIAL_TOKENS:
            if tok not in stoi:
                stoi[tok] = len(itos)
                itos.append(tok)

        # add tokens from data
        for seq in token_sequences:
            for tok in seq:
                if tok not in stoi:
                    stoi[tok] = len(itos)
                    itos.append(tok)
        return cls(stoi=stoi, itos=itos)

    def encode(self, tokens: List[str], add_bos: bool = False, add_eos: bool = False) -> List[int]:
        ids: List[int] = []
        if add_bos:
            ids.append(self.stoi[BOS])
        for t in tokens:
            ids.append(self.stoi.get(t, self.stoi[UNK]))
        if add_eos:
            ids.append(self.stoi[EOS])
        return ids

    def decode(self, ids: List[int]) -> List[str]:
        return [self.itos[i] for i in ids]

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"itos": self.itos}, f)

    @classmethod
    def load(cls, path: str) -> "Vocab":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        itos = data["itos"]
        stoi = {tok: i for i, tok in enumerate(itos)}
        return cls(stoi=stoi, itos=itos)
