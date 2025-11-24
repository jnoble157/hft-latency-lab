#!/usr/bin/env python3
import argparse
import csv
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
except Exception as e:  # pragma: no cover
    torch = None
    nn = None
    optim = None


FEATURE_REC_LEN = 16  # bytes, matches models.features_ref packing (>ihHII)


@dataclass
class SplitIdx:
    train: np.ndarray
    val: np.ndarray
    test: np.ndarray


def load_labels(labels_csv: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load labels CSV with header:
      ts_s,row_index,mid_sum_1e4_t,mid_sum_1e4_t_h,label
    Returns arrays: indices, labels, ts_s
    """
    idxs: List[int] = []
    ys: List[int] = []
    ts_list: List[float] = []
    with labels_csv.open("r", newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            try:
                idxs.append(int(row["row_index"]))
                ys.append(int(row["label"]))
                ts_list.append(float(row["ts_s"]))
            except Exception:
                continue
    return np.array(idxs, dtype=np.int64), np.array(ys, dtype=np.int8), np.array(ts_list, dtype=np.float64)


def load_features_bin(features_bin: Path) -> np.ndarray:
    """
    Parse features.bin of packed snapshots (>ihHII) per record, big-endian.
    Returns float32 array shape [N, 4] using fields: [OFI, Imb_q1_15, Burst_q16_16, Vol_q16_16]
    (skips the reserved uint16).
    """
    buf = features_bin.read_bytes()
    if len(buf) % FEATURE_REC_LEN != 0:
        raise ValueError(f"features.bin length {len(buf)} not multiple of {FEATURE_REC_LEN}")
    n = len(buf) // FEATURE_REC_LEN
    feats = np.empty((n, 4), dtype=np.float32)
    off = 0
    for i in range(n):
        ofi, imb_q15, _rsv, burst_q16, vol_q16 = struct.unpack(">ihHII", buf[off : off + FEATURE_REC_LEN])
        off += FEATURE_REC_LEN
        # Keep raw integer magnitudes; scale imbalance back to [-1, 1) for model stability,
        # convert Q16.16 to float.
        feats[i, 0] = float(ofi)
        feats[i, 1] = float(imb_q15) / float(1 << 15)
        feats[i, 2] = float(burst_q16) / float(1 << 16)
        feats[i, 3] = float(vol_q16) / float(1 << 16)
    return feats


def time_splits(ts_s: np.ndarray, train_frac=0.6, val_frac=0.2) -> SplitIdx:
    assert ts_s.ndim == 1
    tmin, tmax = float(np.min(ts_s)), float(np.max(ts_s))
    t1 = tmin + (tmax - tmin) * train_frac
    t2 = tmin + (tmax - tmin) * (train_frac + val_frac)
    train = np.nonzero(ts_s <= t1)[0]
    val = np.nonzero((ts_s > t1) & (ts_s <= t2))[0]
    test = np.nonzero(ts_s > t2)[0]
    return SplitIdx(train=train, val=val, test=test)


def select_rows_by_indices(features: np.ndarray, indices: np.ndarray, labels: np.ndarray, ts_s: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Align features with labels by row_index. Returns X, y, ts aligned to the labels rows.
    """
    X = features[indices, :]
    y = labels
    t = ts_s
    return X, y, t


def standardize(train_X: np.ndarray, X: np.ndarray) -> Tuple[np.ndarray, Dict[str, List[float]]]:
    mean = train_X.mean(axis=0)
    std = train_X.std(axis=0) + 1e-8
    Xn = (X - mean) / std
    meta = {"mean": mean.tolist(), "std": std.tolist()}
    return Xn, meta


class TinyMLP(nn.Module):  # type: ignore[misc]
    def __init__(self, in_dim: int, hidden: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def train_logreg(Xtr: np.ndarray, ytr: np.ndarray, Xva: np.ndarray, yva: np.ndarray, lr=0.1, epochs=10) -> Dict:
    # Logistic regression using simple gradient descent with L2 reg
    n, d = Xtr.shape
    w = np.zeros(d, dtype=np.float64)
    b = 0.0
    lam = 1e-4
    # Map labels {-1, +1} -> {0, 1}
    ytr01 = (ytr > 0).astype(np.float64)
    yva01 = (yva > 0).astype(np.float64)
    for _ in range(epochs):
        z = Xtr.dot(w) + b
        p = 1.0 / (1.0 + np.exp(-z))
        grad_w = (Xtr.T @ (p - ytr01)) / n + lam * w
        grad_b = float(np.mean(p - ytr01))
        w -= lr * grad_w
        b -= lr * grad_b
    def eval_auc(X, y01) -> float:
        try:
            from sklearn.metrics import roc_auc_score  # type: ignore
            return float(roc_auc_score(y01, X.dot(w) + b))
        except Exception:
            # Fallback: compute PR-like score via rank correlation
            scores = X.dot(w) + b
            order = np.argsort(scores)
            ranks = np.empty_like(order)
            ranks[order] = np.arange(len(scores))
            return float(np.corrcoef(ranks, y01)[0, 1])
    auc = eval_auc(Xva, yva01)
    return {"w": w.tolist(), "b": float(b), "val_auc": auc}


def train_mlp(Xtr: np.ndarray, ytr: np.ndarray, Xva: np.ndarray, yva: np.ndarray, hidden=32, epochs=5, batch_size=4096, lr=1e-3) -> Dict:
    if torch is None:
        raise RuntimeError("PyTorch not available; cannot train MLP. Install torch or use logistic regression results.")
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TinyMLP(Xtr.shape[1], hidden=hidden).to(dev)
    opt = optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()
    Xtr_t = torch.from_numpy(Xtr).float().to(dev)
    ytr_t = torch.from_numpy((ytr > 0).astype(np.float32)).to(dev)
    Xva_t = torch.from_numpy(Xva).float().to(dev)
    yva_t = torch.from_numpy((yva > 0).astype(np.float32)).to(dev)
    # Train
    n = Xtr.shape[0]
    for _ in range(epochs):
        model.train()
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            xb = Xtr_t[start:end]
            yb = ytr_t[start:end]
            opt.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
    # Val AUC
    model.eval()
    with torch.no_grad():
        logits = model(Xva_t).cpu().numpy()
    try:
        from sklearn.metrics import roc_auc_score  # type: ignore
        val_auc = float(roc_auc_score((yva > 0).astype(np.float32), logits))
    except Exception:
        # Fallback: accuracy at zero threshold
        preds = (logits >= 0.0).astype(np.float32)
        val_auc = float(np.mean((preds * 2 - 1) == yva))
    # Save state
    out = {"state_dict": model.state_dict(), "val_auc": val_auc, "hidden": hidden}
    return out


def main():
    ap = argparse.ArgumentParser(description="Train baselines (logistic, tiny MLP) on fixed-point features with 20ms labels.")
    ap.add_argument("--labels-csv", required=True, help="Output of build_labels.py")
    ap.add_argument("--features-bin", required=True, help="features.bin from build_features_from_lobster.py")
    ap.add_argument("--outdir", required=True, help="Directory to save models and metadata")
    ap.add_argument("--mlp-hidden", type=int, default=32)
    args = ap.parse_args()

    labels_csv = Path(args.labels_csv)
    feats_bin = Path(args.features_bin)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    idxs, ys, ts_s = load_labels(labels_csv)
    feats = load_features_bin(feats_bin)
    # Align X and y by row_index
    X, y, t = select_rows_by_indices(feats, idxs, ys, ts_s)
    # Standardize
    Xn, norm_meta = standardize(X[::], X)
    # Time splits
    splits = time_splits(t)
    Xtr, ytr = Xn[splits.train], y[splits.train]
    Xva, yva = Xn[splits.val], y[splits.val]
    Xte, yte = Xn[splits.test], y[splits.test]

    # Train logistic regression
    logreg = train_logreg(Xtr, ytr, Xva, yva)
    (outdir / "logreg_fp32.json").write_text(json.dumps({"norm": norm_meta, "w": logreg["w"], "b": logreg["b"], "val_auc": logreg["val_auc"]}, indent=2))

    # Train MLP (if torch available)
    if torch is not None:
        mlp = train_mlp(Xtr, ytr, Xva, yva, hidden=args.mlp_hidden)
        torch.save({"state_dict": mlp["state_dict"], "norm": norm_meta, "val_auc": mlp["val_auc"], "in_dim": Xtr.shape[1], "hidden": args.mlp_hidden}, outdir / "mlp_fp32.pt")
    else:
        print("warning: torch not available; skipped MLP training")

    print(f"Saved models to {outdir}")


if __name__ == "__main__":
    main()


