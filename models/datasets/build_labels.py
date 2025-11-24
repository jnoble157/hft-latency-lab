#!/usr/bin/env python3
import argparse
import csv
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Optional, TextIO


@dataclass
class PendingLabel:
    start_ts_s: float
    mid_sum_1e4: int  # (ask1 + bid1) in price*1e4 units
    row_index: int


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build 20 ms midprice movement labels from LOBSTER message/orderbook CSVs.")
    ap.add_argument("--message", required=True, help="Path to LOBSTER message LEVEL CSV (e.g., ..._message_10.csv)")
    ap.add_argument("--orderbook", required=True, help="Path to LOBSTER orderbook LEVEL CSV (e.g., ..._orderbook_10.csv)")
    ap.add_argument("--out", required=True, help="Output CSV path for labels")
    ap.add_argument("--horizon-ms", type=float, default=20.0, help="Prediction horizon in milliseconds")
    ap.add_argument("--tick-size", type=float, default=0.01, help="Tick size in dollars")
    return ap.parse_args()


def _open_csv(path: Path) -> TextIO:
    return path.open("r", newline="")


def build_labels(
    message_csv: Path,
    orderbook_csv: Path,
    out_csv: Path,
    horizon_ms: float = 20.0,
    tick_size: float = 0.01,
) -> None:
    """
    Stream LOBSTER message + orderbook files to produce labels for:
      mid(t + horizon) - mid(t)
    Output only rows with |Δmid| >= 1 tick.

    - Time source: message CSV column 1 (seconds after midnight, float)
    - Midprice: (ask1 + bid1) / 2 using orderbook columns (price * 1e4 units)
    - Threshold: 1 tick = tick_size dollars = tick_size * 1e4 in price*1e4 units
      To avoid fractional division by 2 (mid), compare sums:
        |(ask1 + bid1)_(t+h) - (ask1 + bid1)_t| >= 2 * (tick_size * 1e4)
    """
    horizon_s = horizon_ms / 1000.0
    # 1 tick in price*1e4 units -> compare on sums so multiply by 2
    sum_threshold_1e4 = int(round(2.0 * tick_size * 10_000.0))

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with _open_csv(message_csv) as f_msg, _open_csv(orderbook_csv) as f_ob, out_csv.open("w", newline="") as f_out:
        msg_r = csv.reader(f_msg)
        ob_r = csv.reader(f_ob)
        w = csv.writer(f_out)
        # Header
        w.writerow(["ts_s", "row_index", "mid_sum_1e4_t", "mid_sum_1e4_t_h", "label"])

        pending: Deque[PendingLabel] = deque()
        idx = 0
        for msg_row, ob_row in zip(msg_r, ob_r):
            try:
                ts_s = float(msg_row[0])
            except Exception:
                idx += 1
                continue
            # Orderbook columns format:
            # [ask_p1, ask_q1, bid_p1, bid_q1, ask_p2, ask_q2, bid_p2, bid_q2, ...]
            try:
                ask1_p_1e4 = int(ob_row[0])
                bid1_p_1e4 = int(ob_row[2])
            except Exception:
                idx += 1
                continue
            # Skip invalid sentinel prices
            if ask1_p_1e4 >= 9_999_999_999 or bid1_p_1e4 <= -9_999_999_999:
                idx += 1
                continue
            mid_sum_1e4 = ask1_p_1e4 + bid1_p_1e4

            # Enqueue current row for future labeling
            pending.append(PendingLabel(start_ts_s=ts_s, mid_sum_1e4=mid_sum_1e4, row_index=idx))

            # Finalize any rows whose horizon has passed using current mid
            while pending and (ts_s - pending[0].start_ts_s) >= horizon_s:
                p = pending.popleft()
                delta_sum = mid_sum_1e4 - p.mid_sum_1e4
                if abs(delta_sum) >= sum_threshold_1e4:
                    label = 1 if delta_sum > 0 else -1
                    w.writerow([f"{p.start_ts_s:.9f}", p.row_index, p.mid_sum_1e4, mid_sum_1e4, label])
                # else: ignore tiny/noise moves

            idx += 1
        # Note: tail of 'pending' cannot be labeled due to lack of future horizon; drop them gracefully.


def main():
    args = parse_args()
    build_labels(
        message_csv=Path(args.message),
        orderbook_csv=Path(args.orderbook),
        out_csv=Path(args.out),
        horizon_ms=args.horizon_ms,
        tick_size=args.tick_size,
    )
    print(f"Wrote labels to {args.out}")


if __name__ == "__main__":
    main()


