#!/usr/bin/env python3
import argparse, struct, sys
from pathlib import Path

# Import repo-local models (project root is the parent of 'tests')
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from models.features_ref import run as ref_run

FEAT_LEN = 16

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--rx", required=True, help="Path to features dump from replayer (--dump-features)")
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--price-tick", type=float, default=0.01)
    args = ap.parse_args()

    rx = Path(args.rx).read_bytes()
    REC_LEN = 2 + FEAT_LEN  # 2 bytes count (be) + 16 bytes features
    if len(rx) % REC_LEN != 0:
        print(f"error: rx length {len(rx)} not multiple of {REC_LEN}", file=sys.stderr)
        sys.exit(1)
    num_pkts = len(rx) // REC_LEN

    # Generate expected packet-level snapshots: take the snapshot after every batch events
    idx = 0
    pkt_idx = 0
    mismatches = 0
    # Iterate packets from rx dump; for each, advance reference by reported count and compare last snapshot
    gen = ref_run(args.csv, price_tick=args.price_tick)
    for pkt_idx in range(num_pkts):
        rec = rx[pkt_idx*REC_LEN:(pkt_idx+1)*REC_LEN]
        cnt = int.from_bytes(rec[0:2], "big")
        rx_feat = rec[2:2+FEAT_LEN]
        last_feat = None
        for _ in range(cnt):
            try:
                _, last_feat = next(gen)
            except StopIteration:
                print(f"reference exhausted at packet {pkt_idx}", file=sys.stderr)
                mismatches += 1
                break
        if last_feat is None:
            break
        # Compare only OFI (4B) and Imbalance (2B); burst/vol use packet-level dt on echo
        if rx_feat[:6] != last_feat[:6]:
            if mismatches == 0:
                print(f"mismatch at packet {pkt_idx}: expected {last_feat[:6].hex()}, got {rx_feat[:6].hex()}")
            mismatches += 1

    if pkt_idx != num_pkts:
        print(f"warning: compared {pkt_idx} packets, rx has {num_pkts}", file=sys.stderr)

    if mismatches == 0:
        print(f"OK: matched {pkt_idx} packet snapshots")
        sys.exit(0)
    else:
        print(f"FAIL: {mismatches} mismatches out of {pkt_idx} compared")
        sys.exit(2)

if __name__ == "__main__":
    main()


