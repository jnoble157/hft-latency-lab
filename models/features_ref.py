#!/usr/bin/env python3
import csv
import struct
from typing import Iterator, Tuple

# Feature snapshot matches protocol lob_v1_feat_t (network byte order in wire)
# Here we emit big-endian packing: >iHHiI

Q16 = 16

def clamp32(x: int) -> int:
    return max(min(int(x),  2**31 - 1), -(2**31))

def clamp16(x: int) -> int:
    return max(min(int(x),  2**15 - 1), -(2**15))

def run(csv_path: str,
        price_tick: float = 1.0,
        tau_burst_ns: int = 200_000,
        tau_vol_ns: int = 2_000_000) -> Iterator[Tuple[int, bytes]]:
    """
    Consume a CSV of LOB events and yield (ts_ns, 16B features blob) per event.
    CSV columns expected by host replay mapping:
      time_seconds, type, order_id, size, price, direction
    We map to deltas compatibly with the host replayer's simplified logic.
    """
    # Top-N levels
    N = 16
    bid = [{'p': 0, 'q': 0} for _ in range(N)]
    ask = [{'p': 0, 'q': 0} for _ in range(N)]
    ofi = 0
    burst = 0  # Q16.16
    vol = 0    # Q16.16
    last_t = None
    mid_prev = 0

    with open(csv_path, newline='') as f:
        rdr = csv.reader(f)
        first_ts_s = None
        for row in rdr:
            # Parse LOBSTER-like row: t_s, type, order_id, size, price, dir
            try:
                t_s = float(row[0]); typ = int(row[1]); size = int(row[3]); price = float(row[4]); direction = int(row[5])
            except Exception:
                continue
            if first_ts_s is None:
                first_ts_s = t_s
            ts_ns = int(round((t_s - first_ts_s) * 1e9))

            side = 0 if direction == 1 else 1  # 0=bid,1=ask
            action = 1  # default add
            qty = size
            if   typ == 1: action, qty = 1, size      # submit => add
            elif typ == 2: action, qty = 2, -size     # cancel => update (-)
            elif typ == 3: action, qty = 2, -size     # execute => update (-)
            elif typ == 4: action, qty = 3, 0         # delete => remove
            elif typ == 5: action, qty = 2, 0         # replace => update (no-op qty)
            else:
                continue

            price_ticks = int(round(price / price_tick))
            level = 0  # simplified level mapping as in host replayer

            book = bid if side == 0 else ask
            if action == 0:
                book[level]['p'] = price_ticks
                book[level]['q'] = qty
            elif action == 1:
                book[level]['q'] += qty
            elif action == 2:
                # host encodes update qty as delta (can be negative)
                book[level]['q'] += qty
            elif action == 3:
                # Remove => clear level (host sends qty=0 for delete)
                book[level]['q'] = 0
            # Clamp non-negative
            if book[level]['q'] < 0:
                book[level]['q'] = 0

            # OFI accumulator
            sgn = +1 if side == 0 else -1
            # Count only add/update; set/remove not included
            amt = qty if action in (1, 2) else 0
            ofi = clamp32(ofi + sgn * amt)

            bid0_q = bid[0]['q']; ask0_q = ask[0]['q']
            den = bid0_q + ask0_q
            if den != 0:
                num_scaled = (bid0_q - ask0_q) << 15
                if num_scaled >= 0:
                    imb_q1_15 = clamp16(num_scaled // den)
                else:
                    imb_q1_15 = clamp16(-((-num_scaled) // den))
            else:
                imb_q1_15 = 0

            dt = 0 if last_t is None else max(0, ts_ns - last_t)
            last_t = ts_ns

            # Burst: v = v - v*dt/tau + 1
            burst = burst - (burst * dt // tau_burst_ns) + (1 << Q16)
            burst = max(0, min(burst, 0xFFFFFFFF))

            # Micro-volatility on mid changes
            mid_now = (bid[0]['p'] + ask[0]['p']) // 2
            dp = abs(mid_now - mid_prev)
            mid_prev = mid_now
            vol = vol + (((dp << Q16) - vol) * dt // tau_vol_ns)
            vol = max(0, min(vol, 0xFFFFFFFF))

            # Pack as: int32 (ofi), int16 (imb), uint16 (rsv0), uint32 (burst), uint32 (vol)
            feat = struct.pack(">ihHII", ofi, imb_q1_15, 0, burst & 0xFFFFFFFF, vol & 0xFFFFFFFF)
            yield ts_ns, feat

if __name__ == "__main__":
    import argparse, pathlib
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="LOBSTER messages CSV")
    ap.add_argument("--out", required=True, help="Output features.bin")
    ap.add_argument("--price-tick", type=float, default=0.01)
    args = ap.parse_args()
    outp = pathlib.Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "wb") as f:
        for _, feat in run(args.src, price_tick=args.price_tick):
            f.write(feat)
    print(f"Wrote {outp}")


