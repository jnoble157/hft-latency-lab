#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

# Repo-local imports
import sys
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.train.train_baselines import load_labels, load_features_bin, select_rows_by_indices, time_splits  # noqa: E402
from models.quant.fxp import QuantTensor, linear_int8_emulate, make_int8_linear_from_fp32, quantize_symmetric, quantize_bias  # noqa: E402

try:
    import torch  # type: ignore
except Exception:
    torch = None


def fold_norm_into_first_layer(w0: np.ndarray, b0: np.ndarray, mean: np.ndarray, std: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Fold feature normalization (x - mean)/std into first linear layer:
      y0 = w0 * ((x - mean)/std) + b0 = (w0/std) * x + (b0 - w0*(mean/std))
    Shapes:
      w0: [hidden, in_dim], b0: [hidden], mean/std: [in_dim]
    """
    inv_std = 1.0 / (std + 1e-8)
    w0_new = w0 * inv_std[None, :]
    b0_new = b0 - (w0 * (mean[None, :] * inv_std[None, :])).sum(axis=1)
    return w0_new, b0_new


def quantize_logreg(logreg_json: Path, norm_meta: Dict, feats_bin: Path, labels_csv: Path, outdir: Path) -> None:
    meta = json.loads(logreg_json.read_text())
    w = np.array(meta["w"], dtype=np.float32)
    b = float(meta["b"])
    mean = np.array(norm_meta["mean"], dtype=np.float32)
    std = np.array(norm_meta["std"], dtype=np.float32)
    # Fold norm into single linear layer
    w0, b0 = fold_norm_into_first_layer(w[None, :], np.array([b], dtype=np.float32), mean, std)
    w0 = w0.astype(np.float32)  # [1, in_dim]
    b0 = b0.astype(np.float32)  # [1]
    # Calibration inputs: small slice of raw features
    feats = load_features_bin(feats_bin)
    idxs, ys, ts_s = load_labels(labels_csv)
    X, y, t = select_rows_by_indices(feats, idxs, ys, ts_s)
    # Use first 100k for calibration if available
    Xcal = X[: min(100000, X.shape[0]), :]
    # Quantize
    x_q, w_q, b_q, bias_scale = make_int8_linear_from_fp32(Xcal, w0, b0)
    # Save
    out = {
        "type": "logreg",
        "w_int8": w_q.data.astype(np.int8).tolist(),
        "w_scale": w_q.scale,
        "b_int32": b_q.astype(np.int32).tolist(),
        "b_scale": bias_scale,
        "in_scale": x_q.scale,
        "norm": norm_meta,
    }
    (outdir / "logreg_int8.json").write_text(json.dumps(out, indent=2))


def quantize_mlp(mlp_pt: Path, feats_bin: Path, labels_csv: Path, outdir: Path) -> None:
    if torch is None:
        raise RuntimeError("PyTorch not available; cannot quantize MLP.")
    ckpt = torch.load(mlp_pt, map_location="cpu")
    state = ckpt["state_dict"]
    norm_meta = ckpt["norm"]
    mean = np.array(norm_meta["mean"], dtype=np.float32)
    std = np.array(norm_meta["std"], dtype=np.float32)
    # Extract layers
    w0 = state["net.0.weight"].cpu().numpy().astype(np.float32)
    b0 = state["net.0.bias"].cpu().numpy().astype(np.float32)
    w1 = state["net.2.weight"].cpu().numpy().astype(np.float32)
    b1 = state["net.2.bias"].cpu().numpy().astype(np.float32)
    # Fold normalization into first layer
    w0_f, b0_f = fold_norm_into_first_layer(w0, b0, mean, std)
    # Calibration set
    feats = load_features_bin(feats_bin)
    idxs, ys, ts_s = load_labels(labels_csv)
    X, y, t = select_rows_by_indices(feats, idxs, ys, ts_s)
    Xcal = X[: min(100000, X.shape[0]), :]
    # Quantize input and first layer
    x_q = quantize_symmetric(Xcal, num_bits=8)
    w0_q = quantize_symmetric(w0_f, num_bits=8)
    # Bias0 in combined scale (robust to tiny scales)
    s_in0 = max(float(x_q.scale), 1e-12)
    s_w0 = max(float(w0_q.scale), 1e-12)
    b0_q, b0_scale = quantize_bias(b0_f, s_in0, s_w0)
    # Emulate layer0 to calibrate activation scale
    acc0 = (x_q.data.astype(np.int32) @ w0_q.data.T.astype(np.int32)).astype(np.int64) + b0_q.astype(np.int64)
    y0_f = acc0.astype(np.float64) * (x_q.scale * w0_q.scale)
    # ReLU and sanitize any nans/infs that could arise numerically
    y0_f = np.maximum(y0_f, 0.0)
    y0_f = np.nan_to_num(y0_f, copy=False, nan=0.0, posinf=np.finfo(np.float32).max/2, neginf=0.0)
    act0_q = quantize_symmetric(y0_f.astype(np.float32), num_bits=8)
    # Quantize layer1 weights and bias using act0 scale
    w1_q = quantize_symmetric(w1, num_bits=8)
    s_in1 = max(float(act0_q.scale), 1e-12)
    s_w1 = max(float(w1_q.scale), 1e-12)
    b1_q, b1_scale = quantize_bias(b1, s_in1, s_w1)
    # Save
    out = {
        "type": "mlp",
        "in_scale": x_q.scale,
        "w0_int8": w0_q.data.astype(np.int8).tolist(),
        "w0_scale": w0_q.scale,
        "b0_int32": b0_q.astype(np.int32).tolist(),
        "b0_scale": float(b0_scale),
        "act0_scale": act0_q.scale,
        "w1_int8": w1_q.data.astype(np.int8).tolist(),
        "w1_scale": w1_q.scale,
        "b1_int32": b1_q.astype(np.int32).tolist(),
        "b1_scale": float(b1_scale),
        "norm": norm_meta,
    }
    (outdir / "mlp_int8.json").write_text(json.dumps(out, indent=2))


def main():
    ap = argparse.ArgumentParser(description="PTQ quantization for logistic and tiny MLP; exports int8 weights/scales.")
    ap.add_argument("--models-dir", required=True, help="Directory with logreg_fp32.json and/or mlp_fp32.pt")
    ap.add_argument("--features-bin", required=True, help="features.bin for calibration")
    ap.add_argument("--labels-csv", required=True, help="labels CSV for alignment/calibration")
    ap.add_argument("--outdir", required=True, help="Output directory for int8 exports")
    args = ap.parse_args()
    mdir = Path(args.models_dir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Logistic
    logreg_json = mdir / "logreg_fp32.json"
    if logreg_json.exists():
        norm_meta = json.loads(logreg_json.read_text())["norm"]
        quantize_logreg(logreg_json, norm_meta, Path(args.features_bin), Path(args.labels_csv), outdir)
    # MLP
    mlp_pt = mdir / "mlp_fp32.pt"
    if mlp_pt.exists():
        quantize_mlp(mlp_pt, Path(args.features_bin), Path(args.labels_csv), outdir)

    print(f"Wrote int8 exports to {outdir}")


if __name__ == "__main__":
    main()


