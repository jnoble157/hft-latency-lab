#!/usr/bin/env python3
"""
Phase 4 Main Loop: The Two-Lane Brain
Streams packets, runs CPU reflex logic in parallel with FPGA inference,
and measures the 'Latency Gap' between the two answers.
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import argparse
import socket
import struct
import time
import csv
from host.strategy.book import SimpleBook
from host.strategy.reflex import ReflexEngine, ReflexAction
from host.strategy.arbiter import Arbiter, Decision

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pps', type=float, default=10.0)
    parser.add_argument('--count', type=int, default=1000)
    parser.add_argument('--out', type=str, default='docs/experiments/exp_phase4_two_lane_brain/data/results.csv')
    args = parser.parse_args()

    # Setup Network
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('192.168.10.1', 4002)) # Different port than test_lob_stream
    s.setblocking(False) # Non-blocking for the parallel loop
    dst = ('192.168.10.2', 4000)

    # Setup Strategy Components
    book = SimpleBook()
    reflex = ReflexEngine()
    arbiter = Arbiter()

    # Logging
    f = open(args.out, 'w')
    writer = csv.writer(f)
    writer.writerow(['seq', 't_send', 't_reflex', 't_fpga', 't_decide', 
                     'reflex_act', 'fpga_score', 'final_dec', 'latency_gap_ns'])

    print(f"Starting Phase 4 Runner. Target: {args.pps} PPS. Count: {args.count}")

    seq = 0
    interval = 1.0 / args.pps
    next_send = time.time()

    try:
        while seq < args.count:
            now = time.time()
            if now >= next_send:
                # 1. GENERATE & SEND
                # Simplified packet for this test
                t_send_ns = int(time.time() * 1e9)
                # Header (LOB1, Ver1, Type1=Delta)
                pkt = struct.pack('>4sBBHHIQQH', b'LOB1', 1, 1, 0x8001, 32, seq, t_send_ns, 0, 0)
                # Delta (Price=100.00, Qty=10, Bid, Add)
                delta = struct.pack('>iiHBBI', 100000 + (seq % 100), 10, 0, 0, 1, 0)
                
                msg = pkt + delta
                
                # --- CRITICAL PATH START ---
                t0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                s.sendto(msg, dst)
                
                # 2. REFLEX LANE (CPU)
                # Update book and check rules immediately
                book.apply_update(0, 100000 + (seq % 100), 10, 1) 
                reflex_act = reflex.evaluate(book, 100000, 0)
                
                t_reflex = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                
                # 3. NEUROMORPHIC LANE (FPGA) - WAIT & RECV
                # In a real system, we wouldn't block here blindly, 
                # we'd poll or use select, but for this test we want to measure the gap.
                
                fpga_resp = None
                fpga_score = 0.0
                t_fpga = 0
                
                while True:
                    try:
                        data, _ = s.recvfrom(4096)
                        t_fpga = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                        
                        # Parse Score (assuming it comes back in the features packet)
                        # For now, using the 'ofi' field as a proxy for score since we don't have the MLP output format handy in docs
                        if len(data) >= 48:
                             ofi = struct.unpack('>i', data[32:36])[0]
                             fpga_score = float(ofi)
                        break
                    except BlockingIOError:
                        # Timeout check
                        if time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW) - t0 > 20_000_000: # 20ms timeout
                            t_fpga = 0 # Timeout
                            break
                        continue

                # 4. ARBITER (JOIN)
                final_decision = arbiter.decide(reflex_act, fpga_score, {})
                t_decide = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                
                # Stats
                latency_gap = t_fpga - t_reflex if t_fpga > 0 else -1
                
                writer.writerow([seq, t0, t_reflex, t_fpga, t_decide, 
                                 reflex_act.name, fpga_score, final_decision.name, latency_gap])
                
                if seq % 10 == 0:
                    print(f"Seq {seq}: Gap={latency_gap/1000:.1f}us Reflex={reflex_act.name} FPGA={fpga_score}")

                seq += 1
                next_send += interval

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        f.close()
        print(f"Results saved to {args.out}")

if __name__ == "__main__":
    main()

