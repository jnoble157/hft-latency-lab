#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import List

import numpy as np


def write_mem_bytes(path: Path, data_bytes: bytes) -> None:
    """
    Write a .mem file with one byte per line in hex (Vivado compatible for BRAM init).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for b in data_bytes:
            f.write(f"{b:02x}\n")


def write_mem_int32(path: Path, data: np.ndarray, endian: str = "big") -> None:
    """
    Write 32-bit integers as 4 bytes per line (hex), big-endian by default.
    """
    assert data.dtype == np.int32
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for v in data:
            u = np.uint32(v).item()
            if endian == "big":
                f.write(f"{(u >> 24) & 0xFF:02x}\n{(u >> 16) & 0xFF:02x}\n{(u >> 8) & 0xFF:02x}\n{u & 0xFF:02x}\n")
            else:
                f.write(f"{u & 0xFF:02x}\n{(u >> 8) & 0xFF:02x}\n{(u >> 16) & 0xFF:02x}\n{(u >> 24) & 0xFF:02x}\n")


def write_mem_int8_matrix(path: Path, mat: np.ndarray) -> None:
    """
    Write int8 weight matrix (row-major) as bytes (one per line, hex).
    """
    assert mat.dtype == np.int8
    write_mem_bytes(path, mat.astype(np.uint8).tobytes(order="C"))


def main():
    ap = argparse.ArgumentParser(description="Emit BRAM .mem and manifest.json for int8 models (logreg/MLP).")
    ap.add_argument("--int8-json", required=True, help="Path to int8 export (logreg_int8.json or mlp_int8.json)")
    ap.add_argument("--outdir", required=True, help="Directory to write mem files and manifest")
    ap.add_argument("--endian", default="big", choices=["big", "little"], help="Endianness for int32 bias mem")
    args = ap.parse_args()

    spec = json.loads(Path(args.int8_json).read_text())
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = {"type": spec["type"], "files": {}, "scales": {}, "topology": {}}

    if spec["type"] == "logreg":
        w = np.array(spec["w_int8"], dtype=np.int8)  # [1, in_dim]
        b = np.array(spec["b_int32"], dtype=np.int32)
        w_path = outdir / "w0.mem"
        b_path = outdir / "b0.mem"
        write_mem_int8_matrix(w_path, w)
        write_mem_int32(b_path, b, endian=args.endian)
        manifest["files"] = {"w0": str(w_path), "b0": str(b_path)}
        manifest["scales"] = {
            "in_scale": spec["in_scale"],
            "w0_scale": spec["w_scale"],
            "b0_scale": spec["b_scale"],
        }
        manifest["topology"] = {"in_dim": int(w.shape[1]), "out_dim": 1}
    elif spec["type"] == "mlp":
        w0 = np.array(spec["w0_int8"], dtype=np.int8)
        b0 = np.array(spec["b0_int32"], dtype=np.int32)
        w1 = np.array(spec["w1_int8"], dtype=np.int8)
        b1 = np.array(spec["b1_int32"], dtype=np.int32)
        w0_path = outdir / "w0.mem"
        b0_path = outdir / "b0.mem"
        w1_path = outdir / "w1.mem"
        b1_path = outdir / "b1.mem"
        write_mem_int8_matrix(w0_path, w0)
        write_mem_int32(b0_path, b0, endian=args.endian)
        write_mem_int8_matrix(w1_path, w1)
        write_mem_int32(b1_path, b1, endian=args.endian)
        manifest["files"] = {"w0": str(w0_path), "b0": str(b0_path), "w1": str(w1_path), "b1": str(b1_path)}
        manifest["scales"] = {
            "in_scale": spec["in_scale"],
            "w0_scale": spec["w0_scale"],
            "b0_scale": spec["b0_scale"],
            "act0_scale": spec["act0_scale"],
            "w1_scale": spec["w1_scale"],
            "b1_scale": spec["b1_scale"],
        }
        manifest["topology"] = {"in_dim": int(w0.shape[1]), "hidden": int(w0.shape[0]), "out_dim": int(w1.shape[0])}
    else:
        raise ValueError(f"Unknown model type: {spec['type']}")

    (outdir / "model_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote manifest and mem files to {outdir}")


if __name__ == "__main__":
    main()


