#!/usr/bin/env python3
"""
Simple LOB streaming test - sends packets at controlled rate, receives features.
No retransmits, no connected socket - just clean send/receive.
Includes latency measurement with nanosecond precision.
"""
import argparse
import csv
import socket
import struct
import time
import sys

def main():
    parser = argparse.ArgumentParser(description='Stream LOB packets and measure latency')
    parser.add_argument('pps', type=float, help='Packets per second')
    parser.add_argument('--log-csv', type=str, help='CSV file to log latency data')
    parser.add_argument('--max-packets', type=int, help='Stop after N packets')
    args = parser.parse_args()
    
    pps = args.pps
    interval = 1.0 / pps if pps > 0 else 0
    
    # Setup CSV logging if requested
    csv_file = None
    csv_writer = None
    if args.log_csv:
        csv_file = open(args.log_csv, 'w', newline='')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['seq', 't1_host_ns', 't5_host_ns', 'rtt_ns', 
                            't2_pynq_ns', 't3_pynq_ns', 't4_pynq_ns', 't5_pynq_ns', 't6_pynq_ns',
                            'pynq_total_ns', 'dma_ns', 'net_est_ns',
                            'ofi', 'imb_q15', 'burst_q16', 'vol_q16'])
        print(f"Logging latency data to {args.log_csv}")
    
    # Create unconnected UDP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('192.168.10.1', 4001))
    s.settimeout(0.001)  # 1ms timeout for non-blocking receive
    
    dst = ('192.168.10.2', 4000)
    
    # LOB header format: magic(4) ver(1) type(1) flags(2) hdr_len(2) seq(4) t_send_ns(8) t_ing(8) rsv2(2)
    # Delta format: price_ticks(4) qty(4) level(2) side(1) action(1) rsv(4) = 16 bytes
    
    sent = 0
    received = 0
    feat_count = 0
    start_time = time.time()
    last_print = start_time
    
    # Timing data storage (seq -> timestamps)
    pending_sends = {}  # seq -> t1_ns
    
    print(f"Streaming LOB packets at {pps} pps to {dst}")
    if args.log_csv:
        print(f"Latency measurement enabled (CSV logging)")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            # Check max packets limit
            if args.max_packets and sent >= args.max_packets:
                break
            
            # Send a LOB packet with 1 delta (minimal)
            seq = sent
            t_send_ns = int(time.time() * 1e9)
            
            # Header: type=1 (DELTAS), flags=0x8001 (reset + count=1)
            hdr = struct.pack('>4sBBHHIQQH', 
                b'LOB1', 1, 1, 0x8001, 32, seq, t_send_ns, 0, 0)
            
            # One delta: price=100000 (in ticks), qty=100, level=0, side=0 (bid), action=1 (add)
            delta = struct.pack('>iiHBBI', 100000, 100, 0, 0, 1, 0)
            
            pkt = hdr + delta
            
            # T1: Host send timestamp (immediately before sendto)
            t1_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
            s.sendto(pkt, dst)
            
            if csv_writer:
                pending_sends[seq] = t1_ns
            sent += 1
            
            # Try to receive (non-blocking)
            try:
                data, addr = s.recvfrom(4096)
                # T5: Host receive timestamp (immediately after recvfrom)
                t5_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                
                if len(data) >= 32:
                    magic = data[0:4]
                    msg_type = data[5]
                    if magic == b'LOB1':
                        received += 1
                        if msg_type == 2 or msg_type == 4:  # FEATURES or FEATURES_WITH_TIMING
                            feat_count += 1
                            
                            # Parse sequence number from reply (offset 10 per lob_v1.h)
                            reply_seq = struct.unpack('>I', data[10:14])[0]
                            
                            # Parse features if payload is long enough
                            ofi = imb = burst = vol = None
                            if len(data) >= 48:  # 32 (header) + 16 (features)
                                feat_data = data[32:48]
                                ofi = struct.unpack('>i', feat_data[0:4])[0]
                                imb = struct.unpack('>h', feat_data[4:6])[0]
                                burst = struct.unpack('>I', feat_data[8:12])[0]
                                vol = struct.unpack('>I', feat_data[12:16])[0]
                            
                            # Parse timing metadata if present (msg_type=4)
                            t2 = t3 = t4 = t5_pynq = t6 = None
                            if msg_type == 4 and len(data) >= 88:  # 32 (header) + 16 (features) + 40 (timing)
                                timing_data = data[48:88]
                                t2, t3, t4, t5_pynq, t6 = struct.unpack('>QQQQQ', timing_data)
                            
                            # Log timing data if we sent this packet
                            if csv_writer and reply_seq in pending_sends:
                                t1_ns = pending_sends.pop(reply_seq)
                                rtt_ns = t5_ns - t1_ns
                                
                                # Compute derived metrics
                                pynq_total = (t6 - t2) if (t6 and t2) else None
                                dma_time = (t5_pynq - t3) if (t5_pynq and t3) else None
                                net_est = (rtt_ns - pynq_total) if pynq_total else None
                                
                                csv_writer.writerow([reply_seq, t1_ns, t5_ns, rtt_ns,
                                                    t2, t3, t4, t5_pynq, t6,
                                                    pynq_total, dma_time, net_est,
                                                    ofi, imb, burst, vol])
            except socket.timeout:
                pass
            
            # Print stats every second
            now = time.time()
            if now - last_print >= 1.0:
                elapsed = now - start_time
                print(f"sent={sent} recv={received} feat={feat_count} "
                      f"rate={sent/elapsed:.1f} pps feat_rate={feat_count/elapsed:.1f} pps")
                last_print = now
            
            # Rate limiting
            if interval > 0:
                time.sleep(interval)
                
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.time() - start_time
        print(f"\n\nFinal: sent={sent} recv={received} feat={feat_count}")
        print(f"Elapsed: {elapsed:.1f}s")
        print(f"Send rate: {sent/elapsed:.1f} pps")
        print(f"Feature rate: {feat_count/elapsed:.1f} pps")
        print(f"Success rate: {100.0*feat_count/sent if sent > 0 else 0:.1f}%")
        
        # Close CSV file
        if csv_file:
            csv_file.close()
            print(f"Latency data written to {args.log_csv}")

if __name__ == '__main__':
    main()

