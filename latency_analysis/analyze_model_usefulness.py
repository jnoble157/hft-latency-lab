#!/usr/bin/env python3
"""
Simple "model usefulness" analysis for Phase 4 LOBSTER replays.

This does NOT try to be a full P&L backtest. It answers a narrower question:

  - When the arbiter (Reflex + MLP score) decides to BUY/SELL,
    how often is that direction consistent with a short-horizon price move?

Inputs:
  1) A CSV produced by host/strategy/replay_runner.py (default path in that
     script is docs/experiments/exp_phase4_two_lane_brain/data/replay.csv).
     Required columns:
        seq, lob_time, t_send, t_reflex, t_fpga, latency_gap_ns,
        reflex_act, fpga_score, final_dec

  2) The original LOBSTER message CSV used for that replay, with the standard
     columns parsed by host/strategy/lobster_loader.parse_lobster_message:
        Time(sec), EventType, OrderID, Size, Price, Direction

For each row i we:
  - Map seq -> the i-th message in the LOBSTER file.
  - Define current_price = msg[i].price
  - Define future_price = msg[i + horizon].price (if it exists)
  - Label the outcome as:
        price_delta = future_price - current_price
        label = sign(price_delta)  (+1 up, -1 down, 0 flat)
  - Consider only rows where final_dec in {BUY, SELL}.
  - Compute whether the decision's direction matches the label sign.

Outputs:
  - Printed summary with:
      - trade_count, hit_rate, fraction_up/down/flat.
  - Optional plot at latency_analysis/plots/model_usefulness_accuracy.png
    comparing hit_rate vs a naive "coin-flip" baseline.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np


@dataclass
class ReplayRow:
    seq: int
    lob_time: float
    reflex_act: str
    fpga_score: float
    final_dec: str


@dataclass
class LobsterMsg:
    time: float
    event_type: int
    order_id: int
    size: int
    price: int
    side: int


def load_replay_csv(path: Path) -> List[ReplayRow]:
    rows: List[ReplayRow] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                seq = int(r["seq"])
                lob_time = float(r["lob_time"])
                reflex_act = (r.get("reflex_act") or "").strip()
                final_dec = (r.get("final_dec") or "").strip()
                fpga_score = float(r.get("fpga_score") or 0.0)
            except (KeyError, ValueError):
                continue
            rows.append(
                ReplayRow(
                    seq=seq,
                    lob_time=lob_time,
                    reflex_act=reflex_act,
                    fpga_score=fpga_score,
                    final_dec=final_dec,
                )
            )
    return rows


def load_lobster_csv(path: Path) -> List[LobsterMsg]:
    msgs: List[LobsterMsg] = []
    with path.open("r") as f:
        reader = csv.reader(f)
        for parts in reader:
            if len(parts) < 6:
                continue
            try:
                msgs.append(
                    LobsterMsg(
                        time=float(parts[0]),
                        event_type=int(parts[1]),
                        order_id=int(parts[2]),
                        size=int(parts[3]),
                        price=int(parts[4]),
                        side=int(parts[5]),
                    )
                )
            except ValueError:
                continue
    return msgs


def direction_from_dec(dec: str) -> int:
    """
    Map final_dec strings into directional intents:
      BUY  -> +1
      SELL -> -1
      other -> 0 (no trade)
    """
    d = dec.upper()
    if d == "BUY":
        return 1
    if d == "SELL":
        return -1
    return 0


def sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def compute_hit_rate(
    replay_rows: List[ReplayRow],
    msgs: List[LobsterMsg],
    horizon: int,
) -> Tuple[float, int, int, int]:
    """
    Return (hit_rate, trade_count, num_up, num_down).
    """
    assert len(replay_rows) <= len(msgs), "Replay rows cannot exceed LOBSTER messages"

    hits = 0
    trades = 0
    num_up = 0
    num_down = 0

    for r in replay_rows:
        if r.seq < 0 or r.seq >= len(msgs):
            continue
        future_idx = r.seq + horizon
        if future_idx >= len(msgs):
            continue

        direction = direction_from_dec(r.final_dec)
        if direction == 0:
            # We only care about explicit buy/sell decisions
            continue

        current_price = msgs[r.seq].price
        future_price = msgs[future_idx].price
        price_delta = future_price - current_price
        label = sign(price_delta)

        if label > 0:
            num_up += 1
        elif label < 0:
            num_down += 1

        trades += 1
        if direction == label:
            hits += 1

    hit_rate = hits / trades if trades > 0 else 0.0
    return hit_rate, trades, num_up, num_down


def plot_model_usefulness(hit_rate: float, out_path: Path) -> None:
    """
    Compare the arbiter's hit rate against a naive 50/50 baseline.
    """
    fig, ax = plt.subplots(figsize=(4, 4))
    names = ["Coin-flip baseline", "Arbiter (Reflex + MLP)"]
    vals = [0.5, hit_rate]
    x = np.arange(len(names))
    bars = ax.bar(x, vals, color=["tab:gray", "tab:blue"])
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15, ha="right")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Directional hit rate")
    ax.set_title("Directional accuracy of arbiter vs naive baseline")
    ax.grid(True, axis="y", alpha=0.3)

    for bar, v in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            v,
            f"{v*100:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--replay_csv",
        type=str,
        required=True,
        help="CSV from host/strategy/replay_runner.py",
    )
    ap.add_argument(
        "--lobster_csv",
        type=str,
        required=True,
        help="LOBSTER message CSV used for that replay",
    )
    ap.add_argument(
        "--horizon",
        type=int,
        default=50,
        help="Look-ahead horizon in messages for price direction label",
    )
    args = ap.parse_args()

    replay_path = Path(args.replay_csv)
    lobster_path = Path(args.lobster_csv)

    if not replay_path.exists():
        raise SystemExit(f"replay_csv not found: {replay_path}")
    if not lobster_path.exists():
        raise SystemExit(f"lobster_csv not found: {lobster_path}")

    replay_rows = load_replay_csv(replay_path)
    msgs = load_lobster_csv(lobster_path)
    print(f"loaded {len(replay_rows)} replay rows and {len(msgs)} LOBSTER messages")

    hit_rate, trades, num_up, num_down = compute_hit_rate(
        replay_rows,
        msgs,
        horizon=args.horizon,
    )

    print("\nModel usefulness (directional):")
    print(f"  Horizon (messages): {args.horizon}")
    print(f"  Trades evaluated   : {trades}")
    print(f"  Up-moves           : {num_up}")
    print(f"  Down-moves         : {num_down}")
    print(f"  Hit rate           : {hit_rate*100:.2f}%")

    out_plot = (
        Path(__file__).resolve().parent
        / "plots"
        / f"model_usefulness_h{args.horizon}.png"
    )
    plot_model_usefulness(hit_rate, out_plot)


if __name__ == "__main__":
    main()


