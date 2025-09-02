from __future__ import annotations
import argparse
import json
import os
from typing import Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception as e:
    raise SystemExit(
        "PyTorch is required for training. Please install it in the backend container (CPU is fine).\n"
        "Example inside container: pip install torch --index-url https://download.pytorch.org/whl/cpu"
    )

from .data import prepare_dataset
from .models.transformer import Seq2SeqTransformer, TransformerConfig


def load_npz(path: str) -> dict:
    data = np.load(path)
    return {k: data[k] for k in data.files}


def make_dataloader(pack: dict, batch_size: int, shuffle: bool = True) -> DataLoader:
    src = torch.from_numpy(pack["src"]).long()
    src_mask = torch.from_numpy(pack["src_mask"]).float()
    dec_inp = torch.from_numpy(pack["dec_inp"]).long()
    dec_mask = torch.from_numpy(pack["dec_mask"]).float()
    tgt = torch.from_numpy(pack["tgt"]).long()
    ds = TensorDataset(src, src_mask, dec_inp, dec_mask, tgt)
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle)


def train_one_epoch(model, loader, optim, criterion, device, pad_id: int) -> Tuple[float, float]:
    model.train()
    total_loss = 0.0
    total_tokens = 0
    for src, src_mask, dec_inp, dec_mask, tgt in loader:
        src = src.to(device)
        dec_inp = dec_inp.to(device)
        tgt = tgt.to(device)
        # key padding masks are 1.0 for valid, 0.0 for pad in our npz; pass masks as is
        logits = model(src, dec_inp, src_key_padding_mask=src_mask.to(device), tgt_key_padding_mask=dec_mask.to(device))
        # shift targets to align with decoder outputs
        # logits: (B, T, V), tgt: (B, T)
        B, T, V = logits.shape
        loss = criterion(logits.reshape(B*T, V), tgt.reshape(B*T))
        optim.zero_grad()
        loss.backward()
        optim.step()
        with torch.no_grad():
            mask = (tgt != pad_id)
            n_tokens = int(mask.sum().item())
            total_tokens += n_tokens
            total_loss += loss.item() * n_tokens
    ppl = np.exp(total_loss / max(1, total_tokens)) if total_tokens > 0 else float('inf')
    return total_loss / max(1, total_tokens), ppl


def evaluate(model, loader, criterion, device, pad_id: int) -> Tuple[float, float]:
    model.eval()
    total_loss = 0.0
    total_tokens = 0
    with torch.no_grad():
        for src, src_mask, dec_inp, dec_mask, tgt in loader:
            src = src.to(device)
            dec_inp = dec_inp.to(device)
            tgt = tgt.to(device)
            logits = model(src, dec_inp, src_key_padding_mask=src_mask.to(device), tgt_key_padding_mask=dec_mask.to(device))
            B, T, V = logits.shape
            loss = criterion(logits.reshape(B*T, V), tgt.reshape(B*T))
            mask = (tgt != pad_id)
            n_tokens = int(mask.sum().item())
            total_tokens += n_tokens
            total_loss += loss.item() * n_tokens
    ppl = np.exp(total_loss / max(1, total_tokens)) if total_tokens > 0 else float('inf')
    return total_loss / max(1, total_tokens), ppl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=str, default="/app/scripts/transformer_training_data.csv", help="CSV path")
    ap.add_argument("--out", type=str, default="/app/ml/artifacts", help="Artifacts dir")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--d-model", type=int, default=256)
    ap.add_argument("--nhead", type=int, default=8)
    ap.add_argument("--enc-layers", type=int, default=2)
    ap.add_argument("--dec-layers", type=int, default=2)
    ap.add_argument("--ff", type=int, default=512)
    ap.add_argument("--dropout", type=float, default=0.1)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Prepare dataset and save artifacts (vocab/config/train.npz/val.npz)
    cfg = prepare_dataset(args.data, args.out)

    # Load packs
    train_pack = load_npz(os.path.join(args.out, "train.npz"))
    val_pack = load_npz(os.path.join(args.out, "val.npz"))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model_cfg = TransformerConfig(
        vocab_size=cfg["vocab_size"],
        d_model=args.d_model,
        nhead=args.nhead,
        num_encoder_layers=args.enc_layers,
        num_decoder_layers=args.dec_layers,
        dim_feedforward=args.ff,
        dropout=args.dropout,
    )

    model = Seq2SeqTransformer(model_cfg, pad_id=cfg["pad_id"]).to(device)

    criterion = nn.CrossEntropyLoss(ignore_index=cfg["pad_id"]).to(device)
    optim = torch.optim.Adam(model.parameters(), lr=args.lr)

    train_loader = make_dataloader(train_pack, args.batch_size, shuffle=True)
    val_loader = make_dataloader(val_pack, args.batch_size, shuffle=False)

    history = []
    for epoch in range(1, args.epochs + 1):
        tr_loss, tr_ppl = train_one_epoch(model, train_loader, optim, criterion, device, pad_id=cfg["pad_id"]) 
        va_loss, va_ppl = evaluate(model, val_loader, criterion, device, pad_id=cfg["pad_id"]) 
        msg = {
            "epoch": epoch,
            "train_loss": float(tr_loss),
            "train_ppl": float(tr_ppl),
            "val_loss": float(va_loss),
            "val_ppl": float(va_ppl),
        }
        print(json.dumps(msg))
        history.append(msg)

    # Save model + final config
    torch.save(model.state_dict(), os.path.join(args.out, "model.pt"))
    with open(os.path.join(args.out, "train_history.json"), "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


if __name__ == "__main__":
    main()
