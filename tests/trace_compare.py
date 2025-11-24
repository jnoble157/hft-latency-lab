#!/usr/bin/env python3
import argparse, csv, struct, sys
from pathlib import Path

FEAT_LEN = 16

def clamp16(x: int) -> int:
    return max(min(int(x),  2**15 - 1), -(2**15))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--rx", required=True, help="features dump with [2B count][16B feat]*")
    ap.add_argument("--batch", type=int, default=128, help="nominal batch (for context only)")
    ap.add_argument("--price-tick", type=float, default=0.01)
    ap.add_argument("--max-mismatches", type=int, default=1)
    args = ap.parse_args()

    rx = Path(args.rx).read_bytes()
    REC_LEN = 2 + FEAT_LEN
    if len(rx) % REC_LEN != 0:
        print(f"error: rx length {len(rx)} not multiple of {REC_LEN}", file=sys.stderr)
        sys.exit(1)
    num_pkts = len(rx) // REC_LEN

    # Book/reference state
    N = 16
    bid = [{'p': 0, 'q': 0} for _ in range(N)]
    ask = [{'p': 0, 'q': 0} for _ in range(N)]
    ofi = 0

    mismatches = 0
    with open(args.csv, newline='') as f:
        rdr = csv.reader(f)
        # Skip headerless; read all rows into memory for indexed access (we walk sequentially)
        rows = list(rdr)

    idx = 0
    for pkt_idx in range(num_pkts):
        rec = rx[pkt_idx*REC_LEN:(pkt_idx+1)*REC_LEN]
        cnt = int.from_bytes(rec[0:2], "big")
        rx_feat = rec[2:2+FEAT_LEN]
        # Step through cnt events
        start_idx = idx
        for _ in range(cnt):
            if idx >= len(rows):
                break
            row = rows[idx]
            try:
                t_s = float(row[0]); typ = int(row[1]); size = int(row[3]); price = float(row[4]); direction = int(row[5])
            except Exception:
                idx += 1
                continue
            side = 0 if direction == 1 else 1  # 0=bid,1=ask
            action = 1
            qty = size
            if   typ == 1: action, qty = 1, size
            elif typ == 2: action, qty = 2, -size
            elif typ == 3: action, qty = 2, -size
            elif typ == 4: action, qty = 3, 0
            elif typ == 5: action, qty = 2, 0
            level = 0

            book = bid if side == 0 else ask
            if action == 0:
                book[level]['q'] = qty
            elif action == 1:
                book[level]['q'] += qty
            elif action == 2:
                book[level]['q'] += qty
            elif action == 3:
                book[level]['q'] = 0
            if book[level]['q'] < 0:
                book[level]['q'] = 0

            if action in (1, 2):
                sgn = +1 if side == 0 else -1
                ofi = max(min(ofi + sgn * qty,  2**31 - 1), -(2**31))
            idx += 1

        bid0_q = bid[0]['q']; ask0_q = ask[0]['q']
        den = bid0_q + ask0_q
        if den != 0:
            imb_q1_15 = clamp16(((bid0_q - ask0_q) << 15) // den)
        else:
            imb_q1_15 = 0
        exp_prefix = (ofi & 0xffffffff).to_bytes(4, "big", signed=False) + (imb_q1_15 & 0xffff).to_bytes(2, "big", signed=False)
        if rx_feat[:6] != exp_prefix:
            print(f"pkt={pkt_idx} events[{start_idx}:{idx}) cnt={cnt} mismatch:")
            print(f"  exp ofi={ofi} imb_q1_15={imb_q1_15} -> {exp_prefix.hex()}")
            print(f"  got {rx_feat[:6].hex()}")
            # Print last up to 8 events context
            ctx_start = max(start_idx, idx - 8)
            for j in range(ctx_start, idx):
                row = rows[j]
                try:
                    typ = int(row[1]); size = int(row[3]); price = float(row[4]); direction = int(row[5])
                except Exception:
                    continue
                print(f"    row[{j}]: type={typ} dir={direction} size={size} price={price}")
            mismatches += 1
            if mismatches >= args.max_mismatches:
                break

    if mismatches == 0:
        print(f"OK: {num_pkts} packets matched OFI+imbalance")
        sys.exit(0)
    else:
        print(f"FAIL: {mismatches} packet mismatches")
        sys.exit(2)

if __name__ == "__main__":
    main()


