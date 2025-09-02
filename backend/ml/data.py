from __future__ import annotations
import csv
import json
import os
from dataclasses import dataclass
from typing import List, Tuple, Dict
import numpy as np
from .vocab import Vocab, PAD, BOS, EOS

@dataclass
class Sample:
    src: List[str]
    tgt: List[str]


def read_csv(path: str) -> List[Sample]:
    samples: List[Sample] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = row["input_pois"].strip().split()
            tgt = row["target_sequence"].strip().split()
            samples.append(Sample(src=src, tgt=tgt))
    return samples


def build_vocab(samples: List[Sample]) -> Vocab:
    token_sequences = [s.src for s in samples] + [s.tgt for s in samples]
    return Vocab.build(token_sequences)


def encode_samples(samples: List[Sample], vocab: Vocab) -> Tuple[List[List[int]], List[List[int]]]:
    src_ids: List[List[int]] = []
    tgt_ids: List[List[int]] = []
    for s in samples:
        # encoder: no BOS/EOS; decoder input: BOS + tgt; decoder target: tgt + EOS (handled in train)
        src_ids.append(vocab.encode(s.src, add_bos=False, add_eos=False))
        tgt_ids.append(vocab.encode(s.tgt, add_bos=False, add_eos=True))
    return src_ids, tgt_ids


def pad_sequences(seqs: List[List[int]], pad_id: int, max_len: int | None = None) -> Tuple[np.ndarray, np.ndarray]:
    if max_len is None:
        max_len = max(len(s) for s in seqs) if seqs else 0
    batch = len(seqs)
    arr = np.full((batch, max_len), pad_id, dtype=np.int64)
    mask = np.zeros((batch, max_len), dtype=np.float32)
    for i, s in enumerate(seqs):
        ln = min(len(s), max_len)
        arr[i, :ln] = np.array(s[:ln], dtype=np.int64)
        mask[i, :ln] = 1.0
    return arr, mask


def train_val_split(samples: List[Sample], val_ratio: float = 0.2, seed: int = 42) -> Tuple[List[Sample], List[Sample]]:
    rng = np.random.default_rng(seed)
    idx = np.arange(len(samples))
    rng.shuffle(idx)
    n_val = max(1, int(len(samples) * val_ratio)) if len(samples) > 1 else 0
    val_idx = set(idx[:n_val])
    train, val = [], []
    for i, s in enumerate(samples):
        (val if i in val_idx else train).append(s)
    return train, val


def save_artifacts(out_dir: str, vocab: Vocab, train_enc, val_enc, config: Dict):
    os.makedirs(out_dir, exist_ok=True)
    vocab.save(os.path.join(out_dir, "vocab.json"))
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    # train_enc/val_enc: dict with src, src_mask, dec_inp, tgt
    np.savez_compressed(os.path.join(out_dir, "train.npz"), **train_enc)
    np.savez_compressed(os.path.join(out_dir, "val.npz"), **val_enc)


def prepare_dataset(csv_path: str, out_dir: str, max_src_len: int | None = None, max_tgt_len: int | None = None) -> Dict:
    samples = read_csv(csv_path)
    vocab = build_vocab(samples)
    src_ids, tgt_ids = encode_samples(samples, vocab)

    # decoder input = BOS + tgt[:-1]; teacher forcing target = tgt
    bos_id = vocab.stoi[BOS]
    pad_id = vocab.stoi[PAD]

    # split
    train_samples, val_samples = train_val_split(samples)

    # re-encode split to keep consistent lengths
    def subset(seqs, indices):
        return [seqs[i] for i in indices]

    train_idx = list(range(len(train_samples)))
    val_idx = list(range(len(train_samples), len(samples)))

    # For simplicity, re-map using the original arrays by scanning membership
    train_mask = [s in train_samples for s in samples]
    val_mask = [s in val_samples for s in samples]

    train_src = [src for src, m in zip(src_ids, train_mask) if m]
    train_tgt = [tgt for tgt, m in zip(tgt_ids, train_mask) if m]
    val_src = [src for src, m in zip(src_ids, val_mask) if m]
    val_tgt = [tgt for tgt, m in zip(tgt_ids, val_mask) if m]

    if max_src_len is None:
        max_src_len = max(len(s) for s in src_ids)
    if max_tgt_len is None:
        max_tgt_len = max(len(s) for s in tgt_ids)

    # build decoder inputs (shifted right with BOS)
    def build_dec_inputs(tgts: List[List[int]]) -> List[List[int]]:
        dec_inp: List[List[int]] = []
        for t in tgts:
            inp = [bos_id] + t[:-1] if len(t) > 0 else [bos_id]
            dec_inp.append(inp)
        return dec_inp

    train_dec_inp = build_dec_inputs(train_tgt)
    val_dec_inp = build_dec_inputs(val_tgt)

    train_src_arr, train_src_mask = pad_sequences(train_src, pad_id, max_src_len)
    train_dec_inp_arr, train_dec_mask = pad_sequences(train_dec_inp, pad_id, max_tgt_len)
    train_tgt_arr, _ = pad_sequences(train_tgt, pad_id, max_tgt_len)

    val_src_arr, val_src_mask = pad_sequences(val_src, pad_id, max_src_len)
    val_dec_inp_arr, val_dec_mask = pad_sequences(val_dec_inp, pad_id, max_tgt_len)
    val_tgt_arr, _ = pad_sequences(val_tgt, pad_id, max_tgt_len)

    train_pack = {
        "src": train_src_arr,
        "src_mask": train_src_mask,
        "dec_inp": train_dec_inp_arr,
        "dec_mask": train_dec_mask,
        "tgt": train_tgt_arr,
    }

    val_pack = {
        "src": val_src_arr,
        "src_mask": val_src_mask,
        "dec_inp": val_dec_inp_arr,
        "dec_mask": val_dec_mask,
        "tgt": val_tgt_arr,
    }

    config = {
        "vocab_size": len(vocab.itos),
        "pad_id": pad_id,
        "bos_id": bos_id,
        "max_src_len": int(max_src_len),
        "max_tgt_len": int(max_tgt_len),
        "num_samples": len(samples),
    }

    save_artifacts(out_dir, vocab, train_pack, val_pack, config)
    return config
