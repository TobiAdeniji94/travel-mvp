from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Tuple
import torch
import torch.nn as nn


def subsequent_mask(size: int) -> torch.Tensor:
    # (size, size) upper-triangular causal mask for decoder (float mask with -inf above diagonal)
    # PyTorch nn.Transformer expects a (T, T) mask or (B*h, T, T). We provide (T, T).
    mask = torch.full((size, size), float('-inf'))
    mask = torch.triu(mask, diagonal=1)  # -inf above the main diagonal, 0.0 elsewhere
    return mask


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, dropout: float = 0.1, max_len: int = 5000):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, C)
        x = x + self.pe[:, :x.size(1)]
        return self.dropout(x)


@dataclass
class TransformerConfig:
    vocab_size: int
    d_model: int = 256
    nhead: int = 8
    num_encoder_layers: int = 2
    num_decoder_layers: int = 2
    dim_feedforward: int = 512
    dropout: float = 0.1


class Seq2SeqTransformer(nn.Module):
    def __init__(self, cfg: TransformerConfig, pad_id: int):
        super().__init__()
        self.cfg = cfg
        self.pad_id = pad_id
        self.src_tok_emb = nn.Embedding(cfg.vocab_size, cfg.d_model, padding_idx=pad_id)
        self.tgt_tok_emb = nn.Embedding(cfg.vocab_size, cfg.d_model, padding_idx=pad_id)
        self.pos_enc = PositionalEncoding(cfg.d_model, cfg.dropout)
        self.transformer = nn.Transformer(
            d_model=cfg.d_model,
            nhead=cfg.nhead,
            num_encoder_layers=cfg.num_encoder_layers,
            num_decoder_layers=cfg.num_decoder_layers,
            dim_feedforward=cfg.dim_feedforward,
            dropout=cfg.dropout,
            batch_first=True,
        )
        self.generator = nn.Linear(cfg.d_model, cfg.vocab_size)

    def forward(
        self,
        src: torch.Tensor,           # (B, S)
        tgt_inp: torch.Tensor,       # (B, T)
        src_key_padding_mask: torch.Tensor | None = None,  # (B, S)
        tgt_key_padding_mask: torch.Tensor | None = None,  # (B, T)
    ) -> torch.Tensor:
        # Build causal mask for decoder
        T = tgt_inp.size(1)
        tgt_mask = subsequent_mask(T).to(tgt_inp.device)

        src_emb = self.pos_enc(self.src_tok_emb(src))
        tgt_emb = self.pos_enc(self.tgt_tok_emb(tgt_inp))
        out = self.transformer(
            src=src_emb,
            tgt=tgt_emb,
            src_key_padding_mask=(src_key_padding_mask == 0) if src_key_padding_mask is not None else None,
            tgt_key_padding_mask=(tgt_key_padding_mask == 0) if tgt_key_padding_mask is not None else None,
            memory_key_padding_mask=(src_key_padding_mask == 0) if src_key_padding_mask is not None else None,
            tgt_mask=tgt_mask,
        )
        logits = self.generator(out)  # (B, T, V)
        return logits

    @torch.no_grad()
    def greedy_decode(self, src: torch.Tensor, max_len: int, bos_id: int, eos_id: int) -> torch.Tensor:
        self.eval()
        B = src.size(0)
        tgt = torch.full((B, 1), bos_id, dtype=torch.long, device=src.device)
        src_mask = None
        src_key_padding_mask = None
        for _ in range(max_len - 1):
            logits = self.forward(src, tgt, src_key_padding_mask, None)  # (B, T, V)
            next_token = logits[:, -1].argmax(dim=-1, keepdim=True)      # (B, 1)
            tgt = torch.cat([tgt, next_token], dim=1)
            if (next_token == eos_id).all():
                break
        return tgt
