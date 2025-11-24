#!/usr/bin/env python3
import argparse
import pathlib
import sys
from pathlib import Path

# Ensure repo root is on sys.path so 'models' can be imported when running as a script
# Project root is the parent of 'tests'
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.features_ref import run

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="LOBSTER messages CSV")
    ap.add_argument("--outdir", required=True, help="Directory to write vectors")
    ap.add_argument("--price-tick", type=float, default=0.01)
    args = ap.parse_args()

    out_dir = pathlib.Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "features.bin"
    count = 0
    with open(out_path, "wb") as f:
        for _, feat in run(args.src, price_tick=args.price_tick):
            f.write(feat); count += 1
    print(f"Wrote {out_path} ({count} snapshots, {count*16} bytes)")

if __name__ == "__main__":
    main()


