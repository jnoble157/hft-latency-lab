#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np


def emulate_from_spec(spec: dict, ofi: int, imb: int, burst: int, vol: int) -> float:
    X = np.array([float(ofi), float(imb) / (1 << 15), float(burst) / (1 << 16), float(vol) / (1 << 16)], dtype=np.float32)
    if spec["type"] == "logreg":
        in_scale = float(spec["in_scale"])
        w = np.array(spec["w_int8"], dtype=np.int8)
        b = np.array(spec["b_int32"], dtype=np.int32)
        w_scale = float(spec["w_scale"])
        xi = np.clip(np.round(X / in_scale), -128, 127).astype(np.int32)
        acc = int(xi @ w.T.astype(np.int32)) + int(b[0])
        return float(acc) * (in_scale * w_scale)
    else:
        in_scale = float(spec["in_scale"])
        w0 = np.array(spec["w0_int8"], dtype=np.int8)
        b0 = np.array(spec["b0_int32"], dtype=np.int32)
        w0_scale = float(spec["w0_scale"])
        act0_scale = float(spec["act0_scale"])
        w1 = np.array(spec["w1_int8"], dtype=np.int8)
        b1 = np.array(spec["b1_int32"], dtype=np.int32)
        w1_scale = float(spec["w1_scale"])
        xi = np.clip(np.round(X / in_scale), -128, 127).astype(np.int32)
        acc0 = xi @ w0.T.astype(np.int32) + b0.astype(np.int32)
        y0 = np.maximum(acc0.astype(np.float32) * (in_scale * w0_scale), 0.0)
        y0i = np.clip(np.round(y0 / act0_scale), -128, 127).astype(np.int32)
        acc1 = int(y0i @ w1.T.astype(np.int32)) + int(b1[0])
        return float(acc1) * (act0_scale * w1_scale)


def main():
    ap = argparse.ArgumentParser(description="Validate hardware score vs int8 emulation over RX dump.")
    ap.add_argument("--rx", required=True, help="RX dump: [seq][flags][t_send_ns][feat+score]")
    ap.add_argument("--int8-json", required=True, help="Quantized model spec (mlp_int8.json/logreg_int8.json)")
    ap.add_argument("--max", type=int, default=200000)
    ap.add_argument("--tol", type=float, default=1e-3, help="Allowed absolute difference in score units")
    args = ap.parse_args()
    spec = json.loads(Path(args.int8_json).read_text())
    data = Path(args.rx).read_bytes()
    FEAT_LEN = 20
    rec_len = 4 + 2 + 8 + FEAT_LEN
    mism = 0
    total = 0
    pos = 0
    while pos + rec_len <= len(data) and total < args.max:
        seq = int.from_bytes(data[pos : pos + 4], "big"); pos += 4
        flags = int.from_bytes(data[pos : pos + 2], "big"); pos += 2
        t_send_ns = int.from_bytes(data[pos : pos + 8], "big"); pos += 8
        feat = data[pos : pos + FEAT_LEN]; pos += FEAT_LEN
        ofi = int.from_bytes(feat[0:4], "big", signed=True)
        imb = int.from_bytes(feat[4:6], "big", signed=True)
        burst = int.from_bytes(feat[8:12], "big", signed=False)
        vol = int.from_bytes(feat[12:16], "big", signed=False)
        score_hw_q = int.from_bytes(feat[16:20], "big", signed=True)
        score_hw = float(score_hw_q) / float(1 << 16)  # interpret as Q16.16 for comparison scale
        score_sw = emulate_from_spec(spec, ofi, imb, burst, vol)
        diff = abs(score_hw - score_sw)
        if diff > args.tol:
            mism += 1
        total += 1
    ok = (mism == 0)
    print(("OK" if ok else "FAIL") + f": compared {total}, mismatches {mism}, tol {args.tol}")


if __name__ == "__main__":
    main()


