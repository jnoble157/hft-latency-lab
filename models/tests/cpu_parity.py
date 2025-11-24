#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Tuple

import numpy as np

# Repo-local imports
import sys
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.train.train_baselines import load_labels, load_features_bin, select_rows_by_indices  # noqa: E402


def emulate_logreg_int8(spec: dict, X: np.ndarray) -> np.ndarray:
    in_scale = float(spec["in_scale"])
    w = np.array(spec["w_int8"], dtype=np.int8)  # [1, D]
    b = np.array(spec["b_int32"], dtype=np.int32)  # [1]
    w_scale = float(spec["w_scale"])
    b_scale = float(spec["b_scale"])
    # Quantize inputs
    xi = np.round(X / in_scale).astype(np.int32)
    xi = np.clip(xi, -128, 127)
    # int32 accumulate
    acc = xi @ w.T.astype(np.int32)
    acc = acc + b.astype(np.int32)
    # Dequantize to float logits
    logits = acc.astype(np.float32) * (in_scale * w_scale)  # b already in same scale
    return logits.squeeze(-1)


def emulate_mlp_int8(spec: dict, X: np.ndarray) -> np.ndarray:
    in_scale = float(spec["in_scale"])
    w0 = np.array(spec["w0_int8"], dtype=np.int8)  # [H, D]
    b0 = np.array(spec["b0_int32"], dtype=np.int32)  # [H]
    w0_scale = float(spec["w0_scale"])
    b0_scale = float(spec["b0_scale"])  # equals in_scale*w0_scale
    act0_scale = float(spec["act0_scale"])
    w1 = np.array(spec["w1_int8"], dtype=np.int8)  # [1, H]
    b1 = np.array(spec["b1_int32"], dtype=np.int32)  # [1]
    w1_scale = float(spec["w1_scale"])
    b1_scale = float(spec["b1_scale"])  # equals act0_scale*w1_scale
    # Quantize input
    xi = np.round(X / in_scale).astype(np.int32)
    xi = np.clip(xi, -128, 127)
    # Layer 0 int32 acc
    acc0 = xi @ w0.T.astype(np.int32)
    acc0 = acc0 + b0.astype(np.int32)
    # Dequantize to float, ReLU, then requantize to act0 int8
    y0_f = acc0.astype(np.float32) * (in_scale * w0_scale)
    y0_f = np.maximum(y0_f, 0.0)
    y0_i = np.round(y0_f / act0_scale).astype(np.int32)
    y0_i = np.clip(y0_i, -128, 127)
    # Layer 1
    acc1 = y0_i @ w1.T.astype(np.int32)
    acc1 = acc1 + b1.astype(np.int32)
    # Dequantize final logits
    logits = acc1.astype(np.float32) * (act0_scale * w1_scale)
    return logits.squeeze(-1)


def main():
    ap = argparse.ArgumentParser(description="CPU parity: compare int8 emulation vs fp32 models.")
    ap.add_argument("--int8-json", required=True, help="mlp_int8.json or logreg_int8.json")
    ap.add_argument("--features-bin", required=True, help="features.bin")
    ap.add_argument("--labels-csv", required=True, help="labels CSV")
    ap.add_argument("--max", type=int, default=200000, help="Max samples to test")
    args = ap.parse_args()

    spec = json.loads(Path(args.int8_json).read_text())
    feats = load_features_bin(Path(args.features_bin))
    idxs, ys, ts_s = load_labels(Path(args.labels_csv))
    X, y, t = select_rows_by_indices(feats, idxs, ys, ts_s)
    n = min(args.max, X.shape[0])
    X = X[:n]; y = y[:n]

    if spec["type"] == "logreg":
        logits = emulate_logreg_int8(spec, X)
    else:
        logits = emulate_mlp_int8(spec, X)
    # Simple metric: accuracy at 0 threshold and logit-y correlation
    preds = np.where(logits >= 0.0, 1, -1)
    acc = float(np.mean(preds == y))
    y01 = (y > 0).astype(np.float32)
    std_logits = float(np.std(logits))
    std_y = float(np.std(y01))
    if std_logits < 1e-12 or std_y < 1e-12:
        corr = 0.0
    else:
        corr = float(np.corrcoef(logits, y01)[0, 1])
    print(json.dumps({"samples": int(n), "acc@0": acc, "corr": corr}, indent=2))


if __name__ == "__main__":
    main()


