#!/usr/bin/env python3
import argparse, struct, sys
from pathlib import Path

FEAT_LEN = 16
DELTA_LEN = 16
TAU_BURST_NS = 200_000
TAU_VOL_NS = 2_000_000

def clamp16(x: int) -> int:
    return max(min(int(x),  2**15 - 1), -(2**15))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx", required=True, help="features dump: [2B cnt][16B feat]*")
    ap.add_argument("--tx", required=True, help="packet dump: [2B cnt][16B delta]*")
    ap.add_argument("--max", type=int, default=1)
    args = ap.parse_args()

    rx = Path(args.rx).read_bytes()
    tx = Path(args.tx).read_bytes()
    REC_RX = 4 + 2 + 8 + FEAT_LEN  # seq(4) + flags(2) + t_send_ns(8) + feat(16)
    pos_rx = 0
    pos_tx = 0

    # Book state
    N = 16
    bid = [{'p': 0, 'q': 0} for _ in range(N)]
    ask = [{'p': 0, 'q': 0} for _ in range(N)]
    ofi = 0
    mismatches = 0
    pkt_idx = 0

    # Build index of TX packets by seq
    tx_index = {}
    pos = 0
    while pos + 4 + 2 <= len(tx):
        seq = int.from_bytes(tx[pos:pos+4], 'big'); pos += 4
        cnt = int.from_bytes(tx[pos:pos+2], 'big'); pos += 2
        end = pos + cnt * DELTA_LEN
        if end > len(tx): break
        tx_index[seq] = tx[pos:end]
        pos = end

    compared = 0
    last_ts = None
    while pos_rx + REC_RX <= len(rx):
        seq = int.from_bytes(rx[pos_rx:pos_rx+4], 'big')
        # RX dump stores 16-bit flags from the reply header: bit15=reset, bits[14:0]=delta count
        flags = int.from_bytes(rx[pos_rx+4:pos_rx+6], 'big')
        cnt = flags & 0x7FFF
        t_send_ns = int.from_bytes(rx[pos_rx+6:pos_rx+14], 'big')
        rx_feat = rx[pos_rx+14:pos_rx+14+FEAT_LEN]
        pos_rx += REC_RX

        # Honor RESET bit (bit15) to keep state aligned with echo
        if (flags & 0x8000) != 0:
            bid = [{'p': 0, 'q': 0} for _ in range(N)]
            ask = [{'p': 0, 'q': 0} for _ in range(N)]
            ofi = 0
            last_ts = None
            globals()['burst'] = 0
            globals()['vol'] = 0
            globals()['mid_prev'] = 0

        pkt = tx_index.get(seq)
        if pkt is None:
            # No matching TX packet (dropped early or not dumped) — skip
            continue
        # Re-simulate cnt deltas from this packet
        posp = 0
        for _ in range(cnt):
            if posp + DELTA_LEN > len(pkt): break
            price_ticks, qty, level, side, action, _ = struct.unpack(
                ">iiHBBI", pkt[posp:posp+DELTA_LEN])
            posp += DELTA_LEN
            book = bid if side == 0 else ask
            lvl = level if level < N else 0
            if action == 0:
                book[lvl]['p'] = price_ticks
                book[lvl]['q'] = qty
            elif action == 1:
                book[lvl]['q'] += qty
            elif action == 2:
                book[lvl]['q'] += qty
            elif action == 3:
                book[lvl]['q'] = 0
            if book[lvl]['q'] < 0:
                book[lvl]['q'] = 0
            if action in (1, 2):
                sgn = +1 if side == 0 else -1
                ofi = max(min(ofi + sgn * qty,  2**31 - 1), -(2**31))

        bid0_q = bid[0]['q']; ask0_q = ask[0]['q']
        den = bid0_q + ask0_q
        # HLS uses C-like division semantics (truncate toward zero); Python // floors for negatives.
        # Emulate truncate-toward-zero for consistency with hardware.
        if den != 0:
            num_scaled = (bid0_q - ask0_q) << 15
            if num_scaled >= 0:
                imb_q1_15 = clamp16(num_scaled // den)
            else:
                imb_q1_15 = clamp16(-((-num_scaled) // den))
        else:
            imb_q1_15 = 0
        # Burst/micro-vol with packet-level dt
        if last_ts is None:
            dt = 0
        else:
            dt = max(0, t_send_ns - last_ts)
        last_ts = t_send_ns
        # burst: Q16.16
        # keep variables persistent outside loop; define on first call
        if 'burst' not in globals():
            globals()['burst'] = 0
            globals()['vol'] = 0
            globals()['mid_prev'] = 0
        burst = globals()['burst']
        vol = globals()['vol']
        mid_prev = globals()['mid_prev']
        burst = burst - (burst * dt // TAU_BURST_NS) + (1 << 16)
        if burst < 0: burst = 0
        if burst > 0xFFFFFFFF: burst = 0xFFFFFFFF
        mid_now = (bid[0]['p'] + ask[0]['p']) // 2
        dp = abs(mid_now - mid_prev)
        mid_prev = mid_now
        vol = vol + (((dp << 16) - vol) * dt // TAU_VOL_NS)
        if vol < 0: vol = 0
        if vol > 0xFFFFFFFF: vol = 0xFFFFFFFF
        globals()['burst'] = burst
        globals()['vol'] = vol
        globals()['mid_prev'] = mid_prev

        exp = (ofi & 0xffffffff).to_bytes(4, 'big') + (imb_q1_15 & 0xffff).to_bytes(2, 'big') + b"\x00\x00" + (burst & 0xFFFFFFFF).to_bytes(4, 'big') + (vol & 0xFFFFFFFF).to_bytes(4, 'big')
        if rx_feat != exp:
            print(f"pkt={pkt_idx} cnt={cnt} mismatch: exp {exp.hex()} got {rx_feat.hex()}")
            mismatches += 1
            if mismatches >= args.max:
                break
        pkt_idx += 1
        compared += 1

    if mismatches == 0:
        print(f"OK: {compared} packets matched features (16B)")
        sys.exit(0)
    else:
        print(f"FAIL: {mismatches} packet mismatches of {compared}")
        sys.exit(2)

if __name__ == "__main__":
    main()


