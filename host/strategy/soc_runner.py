#!/usr/bin/env python3
"""
Phase 5 SoC Runner
Validates the 'Reflex on PYNQ' architecture.
Sends packets to PYNQ and measures the internal race between ARM (Reflex) and Fabric (Neuro).
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import argparse
import socket
import struct
import time
import csv

# Telemetry Format: T2, T3, T4, T5, T_Reflex, T6, Reflex_Act, MLP_Score
# 6 Q (u64), 2 I (u32)
TELEM_FMT = '>QQQQQQII'
TELEM_LEN = 56

REFLEX_ACTIONS = {0: 'NONE', 1: 'CANCEL', 2: 'TAKE', 3: 'WIDEN'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pps', type=float, default=10.0)
    parser.add_argument('--count', type=int, default=1000)
    parser.add_argument('--out', type=str, default='docs/experiments/exp_phase5_soc_benchmark/data/soc_results.csv')
    parser.add_argument('--ip', type=str, default='192.168.10.2')
    args = parser.parse_args()

    # Create output directory
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    # Setup Network
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('192.168.10.1', 4005)) # New port for SoC tests
    s.setblocking(False)
    dst = (args.ip, 4000)

    # Logging
    f = open(args.out, 'w')
    writer = csv.writer(f)
    writer.writerow(['seq', 't_host_send', 't_host_recv', 't2_rx', 't3_dma_start', 't4_feat_done', 
                     't5_score_done', 't_reflex_done', 't6_tx', 
                     'reflex_act', 'mlp_score', 'latency_internal_gap_ns', 'latency_host_rtt_ns'])

    print(f"Starting SoC Runner. Target: {args.pps} PPS. Count: {args.count}")
    print(f"Logging to {args.out}")

    seq = 0
    interval = 1.0 / args.pps
    next_send = time.time()

    try:
        while seq < args.count:
            now = time.time()
            if now >= next_send:
                # 1. GENERATE & SEND
                t_send_ns = int(time.time() * 1e9)
                # Header (LOB1, Ver1, Type1=Delta)
                pkt = struct.pack('>4sBBHHIQQH', b'LOB1', 1, 1, 0x8001, 32, seq, t_send_ns, 0, 0)
                
                # Generate a fake crossed book occasionally to trigger Reflex
                # Normal: Bid 100, Ask 101. Crossed: Bid 102.
                price = 100000
                if seq % 50 == 0:
                    price = 102000 # Cross logic (Ask is usually ~100100)
                
                # Delta (Price, Qty=100, Bid=0, Add=1)
                delta = struct.pack('>iiHBBI', price, 100, 0, 0, 1, 0)
                
                msg = pkt + delta
                
                t0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                s.sendto(msg, dst)
                
                # 2. RECV & PARSE
                while True:
                    try:
                        data, _ = s.recvfrom(4096)
                        t_recv = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                        
                        # Parse Header (32) + Features (16) + Telemetry (56)
                        if len(data) >= 32 + 16 + TELEM_LEN:
                            # Extract Telemetry
                            telem_bytes = data[-TELEM_LEN:]
                            t2, t3, t4, t5, t_reflex, t6, reflex_act, mlp_score = struct.unpack(TELEM_FMT, telem_bytes)
                            
                            # Calculate Internal Latency Gap
                            # Positive = FPGA was slower. Negative = FPGA was faster.
                            # Note: t4 is Feature Done, t5 is Score Done.
                            # Decision time for FPGA is t5 (if SNN used) or t4 (if just feats).
                            # Let's assume t5 is the "Neuro Decision Time".
                            
                            neuro_time = t5 if t5 > 0 else t4
                            gap = neuro_time - t_reflex
                            
                            act_name = REFLEX_ACTIONS.get(reflex_act, str(reflex_act))
                            score_float = mlp_score / 65536.0
                            
                            rtt = t_recv - t0
                            
                            writer.writerow([seq, t0, t_recv, t2, t3, t4, t5, t_reflex, t6, 
                                             act_name, score_float, gap, rtt])
                            
                            if seq % 10 == 0:
                                print(f"Seq {seq}: RTT={rtt/1e6:.2f}ms Reflex={act_name} Score={score_float:.4f} "
                                      f"Gap={gap/1000:.1f}us (Reflex@{t_reflex-t2}ns, Neuro@{neuro_time-t2}ns)")
                        else:
                            print(f"Seq {seq}: Received short packet len={len(data)}")
                        
                        break
                    except BlockingIOError:
                        if time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW) - t0 > 100_000_000: # 100ms timeout
                            print(f"Seq {seq}: Timeout")
                            break
                        continue
                
                seq += 1
                next_send += interval

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        f.close()
        print(f"Done.")

if __name__ == "__main__":
    main()

