#!/usr/bin/env python3
import argparse
import pathlib
import sys
from pathlib import Path

# Ensure repo root import for models.features_ref
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.features_ref import run as ref_run  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate fixed-point feature snapshots from LOBSTER messages.")
    ap.add_argument("--message", required=True, help="Path to LOBSTER message LEVEL CSV (e.g., ..._message_10.csv)")
    ap.add_argument("--out", required=True, help="Output path (features.bin)")
    ap.add_argument(
        "--price-tick",
        type=float,
        default=100.0,
        help="Tick size for the input 'price' column units. For raw LOBSTER (price=$*1e4), use 100.0.",
    )
    return ap.parse_args()


def main():
    args = parse_args()
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(outp, "wb") as f:
        for _, feat in ref_run(args.message, price_tick=args.price_tick):
            f.write(feat)
            count += 1
    print(f"Wrote {outp} ({count} snapshots, {count*16} bytes)")


if __name__ == "__main__":
    main()


