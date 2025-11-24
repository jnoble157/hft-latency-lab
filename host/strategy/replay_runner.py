#!/usr/bin/env python3
"""
Phase 4 Replay Runner (Optimized)
Feeds real LOBSTER data into the Two-Lane Brain.
Now with correct MLP Score parsing and optimized Book logic.
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import argparse
import socket
import time
import csv
import struct
from host.strategy.book import SimpleBook
from host.strategy.reflex import ReflexEngine
from host.strategy.arbiter import Arbiter
from host.strategy.lobster_loader import parse_lobster_message, lobster_to_lob_packet, load_lobster_snapshot

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file', type=str, help='LOBSTER message CSV')
    parser.add_argument('--book-file', type=str, help='LOBSTER orderbook snapshot CSV', required=True)
    parser.add_argument('--limit', type=int, default=10000, help='Max packets')
    parser.add_argument('--pps', type=float, default=100.0, help='Replay speed (pkts/sec)')
    parser.add_argument('--out', type=str, default='docs/experiments/exp_phase4_two_lane_brain/data/replay.csv')
    args = parser.parse_args()

    # Setup Network
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('192.168.10.1', 4003))
    s.setblocking(False)
    dst = ('192.168.10.2', 4000)

    # Strategies
    book = SimpleBook()
    reflex = ReflexEngine()
    arbiter = Arbiter()

    # Load Initial Book State
    print(f"Loading initial book from {args.book_file}...")
    asks, bids = load_lobster_snapshot(args.book_file)
    book.load_snapshot(asks, bids)
    print(f"Book initialized: Best Bid={book.best_bid} Best Ask={book.best_ask} Spread={book.get_spread()}")

    # Logging
    f_out = open(args.out, 'w')
    writer = csv.writer(f_out)
    writer.writerow(['seq', 'lob_time', 't_send', 't_reflex', 't_fpga', 'latency_gap_ns', 'reflex_act', 'fpga_score', 'final_dec'])

    print(f"Replaying {args.csv_file} at {args.pps} PPS...")

    seq = 0
    interval = 1.0 / args.pps
    next_send = time.time()
    
    with open(args.csv_file, 'r') as f_in:
        for line in f_in:
            if seq >= args.limit:
                break
                
            msg = parse_lobster_message(line)
            if not msg: continue
            
            # Rate Limit
            now = time.time()
            if now < next_send:
                time.sleep(next_send - now)
            
            # 1. Prepare & Send
            t_send_ns = int(time.time() * 1e9)
            pkt = lobster_to_lob_packet(msg, seq, t_send_ns)
            
            t0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
            s.sendto(pkt, dst)
            
            # 2. Reflex Lane (CPU)
            # Map LOBSTER types to simple actions for book update
            action_code = 1 if msg['type'] == 1 else 3
            book.apply_update(
                0 if msg['side'] == 1 else 1,
                msg['price'],
                msg['size'],
                action_code
            )
            reflex_act = reflex.evaluate(book, msg['price'], 0 if msg['side'] == 1 else 1)
            t_reflex = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
            
            # 3. FPGA Lane (Wait for Neural Score)
            fpga_score = 0.0
            t_fpga = 0
            
            while True:
                try:
                    data, _ = s.recvfrom(4096)
                    t_fpga = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                    
                    # Parse correctly based on lob_v1.h
                    # Offset 32: Features (16B)
                    # Offset 48: Score (4B, Q16.16)
                    if len(data) >= 52: # Header(32) + Features(16) + Score(4)
                        score_int = struct.unpack('>I', data[48:52])[0]
                        # Convert Q16.16 to float
                        fpga_score = score_int / 65536.0
                    elif len(data) >= 48:
                        # Fallback if score missing (shouldn't happen with correct bitstream)
                        # Just use 0.0
                        pass
                        
                    break
                except BlockingIOError:
                    if time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW) - t0 > 20_000_000:
                        break
                    continue
            
            # 4. Arbiter
            final_dec = arbiter.decide(reflex_act, fpga_score, {})

            # Stats
            gap = t_fpga - t_reflex if t_fpga > 0 else -1
            
            writer.writerow([seq, msg['time'], t0, t_reflex, t_fpga, gap, reflex_act.name, fpga_score, final_dec.name])
            
            if seq % 100 == 0:
                print(f"Seq {seq}: Gap={gap/1000:.1f}us Reflex={reflex_act.name} Score={fpga_score:.4f} Dec={final_dec.name}")
            
            seq += 1
            next_send += interval

    f_out.close()
    print(f"Done. Saved to {args.out}")

if __name__ == '__main__':
    main()
