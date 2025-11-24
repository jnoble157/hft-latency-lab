#!/usr/bin/env python3
"""
Multi-threaded feature echo server for high-throughput LOB processing.
Decouples network I/O from PL/DMA processing for better performance.
"""
import argparse
import socket
import struct
import time
import numpy as np
import threading
import queue

HDR_FMT = ">4sBBHHIQQH"
HDR_LEN = 32
FEAT_LEN = 16
DELTA_FMT = ">iiHBBI"
DELTA_LEN = 16

def find_ip(ol, key_substr):
    matches = [k for k in ol.ip_dict.keys() if key_substr in k]
    if not matches:
        raise RuntimeError(f"Could not find IP containing '{key_substr}'. Available: {list(ol.ip_dict.keys())}")
    for k in matches:
        if k == key_substr:
            return getattr(ol, k)
    return getattr(ol, matches[0])

def now_ns():
    try:
        return time.clock_gettime_ns(time.CLOCK_TAI)
    except Exception:
        try:
            return time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
        except Exception:
            return time.time_ns()

def receiver_thread(sock, rx_queue, stats, enable_timing):
    """Continuously drain UDP socket and push to processing queue."""
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            # T2: PYNQ RX timestamp (immediately after recvfrom)
            t2_rx_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW) if enable_timing else 0
            rx_queue.put((data, addr, time.time(), t2_rx_ns))
            stats['rx_pkts'] += 1
        except Exception as e:
            print(f"Receiver error: {e}")
            break

def sender_thread(sock, tx_queue, stats, enable_timing):
    """Continuously send replies from output queue."""
    while True:
        try:
            reply, addr, timing_data = tx_queue.get()
            # T6: PYNQ TX timestamp (immediately before sendto)
            if enable_timing and timing_data:
                t6_tx_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                # New Format: T2, T3, T4, T5, T_Reflex, T6, Reflex_Act, MLP_Score
                # 6 x u64, 2 x u32 = 48 + 8 = 56 bytes
                # Note: T_Reflex is new.
                timing_payload = struct.pack('>QQQQQQII', 
                    timing_data.get('t2', 0), 
                    timing_data.get('t3', 0), 
                    timing_data.get('t4', 0), 
                    timing_data.get('t5', 0), 
                    timing_data.get('t_reflex', 0),
                    t6_tx_ns,
                    timing_data.get('reflex_act', 0),
                    timing_data.get('mlp_score', 0)
                )
                reply = reply + timing_payload
            sock.sendto(reply, addr)
            stats['tx_pkts'] += 1
        except Exception as e:
            print(f"Sender error: {e}")
            break

def processor_thread(rx_queue, tx_queue, stats, args, dma_in, dma_out, in_buf, out_buf, dma_score, score_buf, dma_lock):
    """Process packets through PL/DMA or PS fallback."""
    print("Processor thread started")
    # State for feature computation
    N = 16
    bid = [{'p': 0, 'q': 0} for _ in range(N)]
    ask = [{'p': 0, 'q': 0} for _ in range(N)]
    ofi = 0
    burst = 0
    vol = 0
    last_t = None
    mid_prev = 0
    tau_burst_ns = 200_000
    tau_vol_ns = 2_000_000
    
    timeout_s = args.dma_timeout_us / 1_000_000.0
    
    while True:
        try:
            data, addr, rx_time, t2_rx_ns = rx_queue.get(timeout=1.0)
            
            # Initialize timing data
            timing_data = None
            if args.enable_timing:
                timing_data = {'t2': t2_rx_ns, 't3': 0, 't4': 0, 't5': 0}
            
            if len(data) < HDR_LEN:
                continue
            
            # Parse header
            magic, ver, msg_type, flags_be, hdr_len_be, seq_be, t_send_be, t_ing_be, rsv2 = struct.unpack(HDR_FMT, data[:HDR_LEN])
            
            if magic != b'LOB1':
                continue
            
            # Handle PING
            if msg_type == 0:
                t_now = now_ns()
                reply = struct.pack(HDR_FMT, b'LOB1', 1, 0, flags_be, HDR_LEN, seq_be, t_send_be, t_now, 0)
                tx_queue.put((reply, addr, None))  # No timing for PING
                continue
            
            # Handle DELTAS
            if msg_type != 1:
                continue
            
            flags = (flags_be >> 8) | ((flags_be & 0xFF) << 8)
            reset = (flags & 0x8000) != 0
            cnt = flags & 0x7FFF
            
            if reset:
                bid = [{'p': 0, 'q': 0} for _ in range(N)]
                ask = [{'p': 0, 'q': 0} for _ in range(N)]
                ofi = 0
                burst = 0
                vol = 0
                last_t = None
                mid_prev = 0
            
            # Compute PS features as fallback
            offset = HDR_LEN
            for _ in range(min(cnt, (len(data) - HDR_LEN) // DELTA_LEN)):
                if offset + DELTA_LEN > len(data):
                    break
                delta_bytes = data[offset:offset + DELTA_LEN]
                price_ticks, qty, level, side, action, _ = struct.unpack(DELTA_FMT, delta_bytes)
                offset += DELTA_LEN
                
                book = ask if side else bid
                if level < N:
                    if action == 0:
                        book[level] = {'p': price_ticks, 'q': qty}
                    elif action == 1 or action == 2:
                        book[level]['q'] += qty
                        if action == 1 or action == 2:
                            ofi += qty if side == 0 else -qty
                    elif action == 3:
                        book[level]['q'] = 0
                    if book[level]['q'] < 0:
                        book[level]['q'] = 0
            
            # --- REFLEX LANE START (ARM) ---
            # Simple Reflex Logic: Check for Crossed Book or Wide Spread
            # bid[0] is best bid, ask[0] is best ask
            reflex_act = 0 # NONE
            
            best_bid_p = bid[0]['p']
            best_ask_p = ask[0]['p']
            best_bid_q = bid[0]['q']
            best_ask_q = ask[0]['q']
            
            if best_bid_q > 0 and best_ask_q > 0:
                if best_bid_p >= best_ask_p:
                    reflex_act = 2 # TAKE_LIQUIDITY (Crossed)
                elif (best_ask_p - best_bid_p) > 1000: # Spread threshold (1000 ticks)
                     reflex_act = 3 # WIDEN_SPREADS
            
            t_reflex_done = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW) if args.enable_timing else 0
            
            if timing_data:
                timing_data['t_reflex'] = t_reflex_done
                timing_data['reflex_act'] = reflex_act
            # --- REFLEX LANE END ---
            
            # Compute features
            t_send_ns = (t_send_be >> 56) | ((t_send_be >> 40) & 0xFF00) | ((t_send_be >> 24) & 0xFF0000) | \
                        ((t_send_be >> 8) & 0xFF000000) | ((t_send_be << 8) & 0xFF00000000) | \
                        ((t_send_be << 24) & 0xFF0000000000) | ((t_send_be << 40) & 0xFF000000000000) | \
                        ((t_send_be << 56) & 0xFF00000000000000)
            
            dt_ns = 0 if last_t is None else max(0, t_send_ns - last_t)
            last_t = t_send_ns
            
            best_bid_q = bid[0]['q']
            best_ask_q = ask[0]['q']
            denom = best_bid_q + best_ask_q
            imb_q1_15 = 0
            if denom > 0:
                imb_q1_15 = int(((best_bid_q - best_ask_q) * 32768) // denom)
                imb_q1_15 = max(-32768, min(32767, imb_q1_15))
            
            if dt_ns > 0:
                decay = (burst * dt_ns) // tau_burst_ns
                burst = max(0, burst - decay + 65536)
                if burst > 0xFFFFFFFF:
                    burst = 0xFFFFFFFF
                
                mid = (bid[0]['p'] + ask[0]['p']) // 2
                dp = abs(mid - mid_prev)
                mid_prev = mid
                delta_v = ((dp * 65536 - vol) * dt_ns) // tau_vol_ns
                vol = max(0, vol + delta_v)
                if vol > 0xFFFFFFFF:
                    vol = 0xFFFFFFFF
            
            # Try PL path if enabled
            use_pl_result = False
            if dma_in is not None and dma_out is not None:
                stats['pl_used'] += 1
                with dma_lock:
                    try:
                        n = min(len(data), len(in_buf))
                        in_buf[:n] = np.frombuffer(data, dtype=np.uint8, count=n)
                        in_buf.flush()
                        out_buf.invalidate()
                        
                        # BARE METAL DMA - No PYNQ API, direct register access only
                        # This is the only way to avoid threading issues
                        
                        # S2MM registers (offset 0x30)
                        S2MM_DMACR = 0x30      # Control
                        S2MM_DMASR = 0x34      # Status  
                        S2MM_DA = 0x48         # Destination Address
                        S2MM_LENGTH = 0x58     # Length (triggers transfer)
                        
                        # MM2S registers (offset 0x00)
                        MM2S_DMACR = 0x00      # Control
                        MM2S_DMASR = 0x04      # Status
                        MM2S_SA = 0x18         # Source Address
                        MM2S_LENGTH = 0x28     # Length (triggers transfer)
                        
                        # T3: DMA start timestamp (before writing LENGTH register)
                        if timing_data:
                            timing_data['t3'] = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                        
                        # Start S2MM: set RS=1 (run)
                        dma_out._mmio.write(S2MM_DMACR, 0x0001)
                        # Write dest address and length
                        dma_out._mmio.write(S2MM_DA, out_buf.physical_address)
                        dma_out._mmio.write(S2MM_LENGTH, FEAT_LEN)
                        
                        # Start MM2S if we have data
                        if n > 0:
                            dma_in._mmio.write(MM2S_DMACR, 0x0001)
                            dma_in._mmio.write(MM2S_SA, in_buf.physical_address)
                            dma_in._mmio.write(MM2S_LENGTH, n)
                        
                        # Poll for S2MM completion
                        start = time.time()
                        while True:
                            s2mm_sr = dma_out._mmio.read(S2MM_DMASR)
                            
                            # Check for completion (IOC bit 12)
                            if (s2mm_sr & 0x1000) != 0:
                                # Clear IOC flag
                                dma_out._mmio.write(S2MM_DMASR, 0x1000)
                                
                                # T4: Feature DMA complete timestamp
                                if timing_data:
                                    timing_data['t4'] = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                                
                                # CRITICAL: Drain MLP score to prevent backpressure
                                if dma_score is not None:
                                    try:
                                        # Start score S2MM transfer
                                        dma_score._mmio.write(0x30, 0x0001)  # RS=1
                                        dma_score._mmio.write(0x48, score_buf.physical_address)
                                        dma_score._mmio.write(0x58, 4)  # 4 bytes per score
                                        # Poll briefly for completion (don't wait long)
                                        for _ in range(100):
                                            score_sr = dma_score._mmio.read(0x34)
                                            if (score_sr & 0x1000) != 0:
                                                dma_score._mmio.write(0x34, 0x1000)  # Clear IOC
                                                # T5: Score DMA complete timestamp
                                                if timing_data:
                                                    timing_data['t5'] = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                                                break
                                            time.sleep(0.00001)
                                    except:
                                        pass
                                
                                # Read result
                                out_buf.invalidate()
                                ofi = int.from_bytes(out_buf[0:4].tobytes(), 'big', signed=True)
                                imb_q1_15 = int.from_bytes(out_buf[4:6].tobytes(), 'big', signed=True)
                                burst = int.from_bytes(out_buf[8:12].tobytes(), 'big')
                                vol = int.from_bytes(out_buf[12:16].tobytes(), 'big')
                                use_pl_result = True
                                
                                # Read Score
                                mlp_score = 0
                                if dma_score is not None:
                                    score_buf.invalidate()
                                    mlp_score = int.from_bytes(score_buf[0:4].tobytes(), 'big')
                                
                                if timing_data:
                                    timing_data['mlp_score'] = mlp_score
                                    
                                stats['pl_done'] += 1
                                if stats['pl_done'] <= 5:
                                    print(f"PL #{stats['pl_done']}: ofi={ofi} imb={imb_q1_15} burst={burst} vol={vol} score={mlp_score}")
                                break
                            
                            # Check for errors (bits 4,5,6)
                            if (s2mm_sr & 0x70) != 0:
                                stats['pl_errors'] += 1
                                if stats['pl_errors'] < 5:
                                    print(f"DMA error: s2mm=0x{s2mm_sr:x}")
                                break
                            
                            # Check timeout
                            if time.time() - start > timeout_s:
                                stats['pl_timeouts'] += 1
                                if stats['pl_timeouts'] < 5:
                                    mm2s_sr = dma_in._mmio.read(MM2S_DMASR) if n > 0 else 0
                                    print(f"Timeout: s2mm=0x{s2mm_sr:x} mm2s=0x{mm2s_sr:x}")
                                break
                            
                            time.sleep(0.00001)  # 10us poll interval
                        
                        if not use_pl_result:
                            stats['pl_fallbacks'] += 1
                            
                    except Exception as e:
                        stats['pl_errors'] += 1
                        if stats['pl_errors'] < 5:
                            print(f"PL exception: {type(e).__name__}: {e}")
                            import traceback
                            traceback.print_exc()
            
            # Build reply
            feat_payload = struct.pack(">ihHII", ofi, imb_q1_15, 0, burst & 0xFFFFFFFF, vol & 0xFFFFFFFF)
            t_now = now_ns()
            # Use msg_type=4 (FEATURES_WITH_TIMING) when timing is enabled, otherwise msg_type=2 (FEATURES)
            msg_type_reply = 4 if args.enable_timing else 2
            reply = struct.pack(HDR_FMT, b'LOB1', 1, msg_type_reply, flags_be, HDR_LEN, seq_be, t_send_be, t_now, 0) + feat_payload
            tx_queue.put((reply, addr, timing_data))
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Processor error: {e}")
            import traceback
            traceback.print_exc()
            # Don't break - keep processing

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="192.168.10.2:4000")
    ap.add_argument("--bit", default="feature_overlay.bit")
    ap.add_argument("--dummy", action="store_true")
    ap.add_argument("--dma-timeout-us", type=int, default=2000)
    ap.add_argument("--log-interval", type=float, default=1.0)
    ap.add_argument("--dma", default="axi_dma_0")
    ap.add_argument("--rx-queue-size", type=int, default=1000)
    ap.add_argument("--tx-queue-size", type=int, default=1000)
    ap.add_argument("--enable-timing", action="store_true", help="Include timing metadata in replies")
    args = ap.parse_args()
    
    host, port = args.bind.rsplit(":", 1)
    port = int(port)
    
    # Initialize PL if not dummy
    dma_in = dma_out = in_buf = out_buf = dma_score = score_buf = None
    if not args.dummy and args.bit:
        try:
            from pynq import Overlay, allocate
            ol = Overlay(args.bit)
            
            # Start MLP to prevent backpressure
            try:
                mlp = find_ip(ol, "mlp_infer")
                mlp.write(0x00, 0x81)
                print("Started MLP in auto-restart mode")
            except:
                pass
            
            dma = find_ip(ol, args.dma)
            dma_in = dma.sendchannel
            dma_out = dma.recvchannel
            in_buf = allocate(shape=(4096,), dtype='u1')
            out_buf = allocate(shape=(FEAT_LEN * 1024,), dtype='u1')
            print(f"PL enabled with DMA '{args.dma}'")
            
            # CRITICAL: Also set up axi_dma_1 to drain MLP scores
            # If we don't drain scores, the MLP FIFO fills up after ~14 transfers
            # and backpressures the entire pipeline
            try:
                dma1 = find_ip(ol, "axi_dma_1")
                dma_score = dma1.recvchannel
                score_buf = allocate(shape=(4 * 1024,), dtype='u1')  # 4 bytes per score
                print("MLP score drain enabled (axi_dma_1)")
            except:
                print("Warning: Could not find axi_dma_1 for MLP scores")
                
        except Exception as e:
            print(f"PL init failed: {e}, using PS-only mode")
    
    # Create socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8 << 20)
    except:
        pass
    s.bind((host, port))
    print(f"Listening on {host}:{port}")
    
    # Shared stats
    stats = {
        'rx_pkts': 0,
        'tx_pkts': 0,
        'pl_used': 0,
        'pl_done': 0,
        'pl_fallbacks': 0,
        'pl_timeouts': 0,
        'pl_errors': 0
    }
    
    # Create queues and locks
    rx_queue = queue.Queue(maxsize=args.rx_queue_size)
    tx_queue = queue.Queue(maxsize=args.tx_queue_size)
    dma_lock = threading.Lock()
    
    # Start threads
    rx_thread = threading.Thread(target=receiver_thread, args=(s, rx_queue, stats, args.enable_timing), daemon=True)
    tx_thread = threading.Thread(target=sender_thread, args=(s, tx_queue, stats, args.enable_timing), daemon=True)
    proc_thread = threading.Thread(target=processor_thread, args=(rx_queue, tx_queue, stats, args, dma_in, dma_out, in_buf, out_buf, dma_score, score_buf, dma_lock), daemon=True)
    
    rx_thread.start()
    tx_thread.start()
    proc_thread.start()
    
    print("Multi-threaded server started")
    
    # Stats reporting
    last_log = time.time()
    last_stats = dict(stats)
    
    try:
        while True:
            time.sleep(0.1)
            now = time.time()
            if now - last_log >= args.log_interval:
                rx_delta = stats['rx_pkts'] - last_stats['rx_pkts']
                tx_delta = stats['tx_pkts'] - last_stats['tx_pkts']
                pl_used = stats['pl_used'] - last_stats['pl_used']
                pl_done = stats['pl_done'] - last_stats['pl_done']
                pl_fb = stats['pl_fallbacks'] - last_stats['pl_fallbacks']
                
                print(f"KPI rx={stats['rx_pkts']} tx={stats['tx_pkts']} "
                      f"pl_used={stats['pl_used']} pl_done={stats['pl_done']} "
                      f"fallbacks={stats['pl_fallbacks']} timeouts={stats['pl_timeouts']} "
                      f"errors={stats['pl_errors']} "
                      f"rx_q={rx_queue.qsize()} tx_q={tx_queue.qsize()}")
                
                last_log = now
                last_stats = dict(stats)
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == '__main__':
    main()

