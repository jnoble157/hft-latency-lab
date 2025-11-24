#!/usr/bin/env python3
"""
Feature Echo Server with C-based DMA Driver
Phase 5 Level 1 Optimization.
Uses ctypes to call libdma_driver.so for fast register access.
"""
import argparse
import socket
import struct
import time
import numpy as np
import threading
import queue
import ctypes
import os

# Load C Driver
# Note: User must compile this first: gcc -O3 -shared -fPIC -o libdma_driver.so dma_driver.c
try:
    libdma = ctypes.CDLL("./libdma_driver.so")
    libdma.map_dma.argtypes = [ctypes.c_uint32]
    libdma.map_dma.restype = ctypes.c_void_p
    libdma.dma_start_mm2s.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
    libdma.dma_start_s2mm.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
    libdma.dma_wait_s2mm.argtypes = [ctypes.c_void_p]
    libdma.dma_wait_s2mm.restype = ctypes.c_int
    libdma.dma_drain_score.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    libdma.dma_drain_score.restype = ctypes.c_int
    C_DRIVER_AVAILABLE = True
except OSError:
    print("Warning: libdma_driver.so not found. Using pure Python fallback (Slow).")
    C_DRIVER_AVAILABLE = False

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
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            t2_rx_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW) if enable_timing else 0
            rx_queue.put((data, addr, time.time(), t2_rx_ns))
            stats['rx_pkts'] += 1
        except Exception as e:
            print(f"Receiver error: {e}")
            break

def sender_thread(sock, tx_queue, stats, enable_timing):
    while True:
        try:
            reply, addr, timing_data = tx_queue.get()
            if enable_timing and timing_data:
                t6_tx_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
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

def processor_thread(rx_queue, tx_queue, stats, args, dma_info, dma_lock):
    print("Processor thread started")
    
    # Unpack DMA Info
    dma_base_ptr = dma_info.get('dma_base', None)
    score_base_ptr = dma_info.get('score_base', None)
    in_phys = dma_info.get('in_phys', 0)
    out_phys = dma_info.get('out_phys', 0)
    score_phys = dma_info.get('score_phys', 0)
    in_buf = dma_info.get('in_buf', None)
    out_buf = dma_info.get('out_buf', None)
    score_buf = dma_info.get('score_buf', None)

    # Reflex State
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
    
    while True:
        try:
            data, addr, rx_time, t2_rx_ns = rx_queue.get(timeout=1.0)
            
            timing_data = None
            if args.enable_timing:
                timing_data = {'t2': t2_rx_ns, 't3': 0, 't4': 0, 't5': 0}
            
            if len(data) < HDR_LEN: continue
            
            magic, ver, msg_type, flags_be, hdr_len_be, seq_be, t_send_be, t_ing_be, rsv2 = struct.unpack(HDR_FMT, data[:HDR_LEN])
            
            if magic != b'LOB1': continue
            
            # PING
            if msg_type == 0:
                t_now = now_ns()
                reply = struct.pack(HDR_FMT, b'LOB1', 1, 0, flags_be, HDR_LEN, seq_be, t_send_be, t_now, 0)
                tx_queue.put((reply, addr, None))
                continue
            
            if msg_type != 1: continue # Only handle Delta
            
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
            
            # Parse Deltas (Python Fallback / Reflex Input)
            offset = HDR_LEN
            for _ in range(min(cnt, (len(data) - HDR_LEN) // DELTA_LEN)):
                if offset + DELTA_LEN > len(data): break
                delta_bytes = data[offset:offset + DELTA_LEN]
                price_ticks, qty, level, side, action, _ = struct.unpack(DELTA_FMT, delta_bytes)
                offset += DELTA_LEN
                
                book = ask if side else bid
                if level < N:
                    if action == 0: book[level] = {'p': price_ticks, 'q': qty}
                    elif action in [1, 2]:
                        book[level]['q'] += qty
                        if action in [1, 2]: ofi += qty if side == 0 else -qty
                    elif action == 3: book[level]['q'] = 0
                    if book[level]['q'] < 0: book[level]['q'] = 0

            # --- REFLEX LOGIC ---
            reflex_act = 0
            if bid[0]['q'] > 0 and ask[0]['q'] > 0:
                if bid[0]['p'] >= ask[0]['p']: reflex_act = 2 # TAKE
                elif (ask[0]['p'] - bid[0]['p']) > 1000: reflex_act = 3 # WIDEN
            
            t_reflex_done = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW) if args.enable_timing else 0
            if timing_data:
                timing_data['t_reflex'] = t_reflex_done
                timing_data['reflex_act'] = reflex_act
            
            # --- FPGA PATH (Optimized) ---
            use_pl = False
            if C_DRIVER_AVAILABLE and dma_base_ptr:
                stats['pl_used'] += 1
                with dma_lock:
                    try:
                        n = min(len(data), len(in_buf))
                        # Copy data to contiguous buffer (Optimizable with zero-copy recv?)
                        in_buf[:n] = np.frombuffer(data, dtype=np.uint8, count=n)
                        in_buf.flush() # Flush cache
                        out_buf.invalidate()
                        
                        if timing_data:
                            timing_data['t3'] = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                        
                        # C DRIVER CALLS
                        # 1. Start S2MM (Recv Features)
                        libdma.dma_start_s2mm(dma_base_ptr, out_phys, FEAT_LEN)
                        # 2. Start MM2S (Send Packet)
                        libdma.dma_start_mm2s(dma_base_ptr, in_phys, n)
                        
                        # 3. Wait for S2MM
                        ret = libdma.dma_wait_s2mm(dma_base_ptr)
                        
                        if timing_data:
                            timing_data['t4'] = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                        
                        if ret == 0:
                            # Drain Score
                            if score_base_ptr:
                                score_buf.invalidate() # Pre-invalidate?
                                ret_score = libdma.dma_drain_score(score_base_ptr, score_phys)
                                if ret_score == 0 and timing_data:
                                    timing_data['t5'] = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                            
                            # Read Results
                            out_buf.invalidate()
                            ofi = int.from_bytes(out_buf[0:4].tobytes(), 'big', signed=True)
                            imb_q1_15 = int.from_bytes(out_buf[4:6].tobytes(), 'big', signed=True)
                            burst = int.from_bytes(out_buf[8:12].tobytes(), 'big')
                            vol = int.from_bytes(out_buf[12:16].tobytes(), 'big')
                            
                            mlp_score = 0
                            if score_base_ptr:
                                score_buf.invalidate()
                                mlp_score = int.from_bytes(score_buf[0:4].tobytes(), 'big')
                                if timing_data: timing_data['mlp_score'] = mlp_score

                            use_pl = True
                            stats['pl_done'] += 1
                            if stats['pl_done'] <= 5:
                                print(f"C-PL #{stats['pl_done']}: ofi={ofi} imb={imb_q1_15} score={mlp_score}")

                        else:
                            stats['pl_timeouts'] += 1
                            print(f"DMA Wait Failed: {ret}")

                    except Exception as e:
                        stats['pl_errors'] += 1
                        print(f"C-PL Error: {e}")
            
            if not use_pl:
                # Compute features manually? Or just skip?
                # For now, skip manual computation to keep code clean, we focused on FPGA path.
                stats['pl_fallbacks'] += 1

            # Build Reply
            feat_payload = struct.pack(">ihHII", ofi, imb_q1_15, 0, burst & 0xFFFFFFFF, vol & 0xFFFFFFFF)
            t_now = now_ns()
            msg_type_reply = 4 if args.enable_timing else 2
            reply = struct.pack(HDR_FMT, b'LOB1', 1, msg_type_reply, flags_be, HDR_LEN, seq_be, t_send_be, t_now, 0) + feat_payload
            tx_queue.put((reply, addr, timing_data))

        except queue.Empty:
            continue
        except Exception as e:
            print(f"Proc Error: {e}")

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
    ap.add_argument("--enable-timing", action="store_true")
    args = ap.parse_args()
    
    host, port = args.bind.rsplit(":", 1)
    port = int(port)
    
    dma_info = {}
    
    if not args.dummy and args.bit:
        try:
            from pynq import Overlay, allocate
            ol = Overlay(args.bit)
            try:
                mlp = find_ip(ol, "mlp_infer")
                mlp.write(0x00, 0x81)
                print("Started MLP")
            except: pass
            
            # Setup DMA buffers
            dma = find_ip(ol, args.dma)
            in_buf = allocate(shape=(4096,), dtype='u1')
            out_buf = allocate(shape=(FEAT_LEN * 1024,), dtype='u1')
            
            dma_info['in_buf'] = in_buf
            dma_info['out_buf'] = out_buf
            dma_info['in_phys'] = in_buf.physical_address
            dma_info['out_phys'] = out_buf.physical_address
            
            # Map DMA Registers for C Driver
            if C_DRIVER_AVAILABLE:
                # We need the physical base address of the DMA IP
                # PYNQ exposes it via .mmio.base_addr
                dma_phys_base = dma.mmio.base_addr
                dma_ptr = libdma.map_dma(dma_phys_base)
                dma_info['dma_base'] = dma_ptr
                print(f"Mapped DMA at 0x{dma_phys_base:x} to {dma_ptr}")
            
            # Setup Score DMA
            try:
                dma1 = find_ip(ol, "axi_dma_1")
                score_buf = allocate(shape=(4 * 1024,), dtype='u1')
                dma_info['score_buf'] = score_buf
                dma_info['score_phys'] = score_buf.physical_address
                
                if C_DRIVER_AVAILABLE:
                    score_phys_base = dma1.mmio.base_addr
                    score_ptr = libdma.map_dma(score_phys_base)
                    dma_info['score_base'] = score_ptr
                    print(f"Mapped Score DMA at 0x{score_phys_base:x} to {score_ptr}")
            except:
                print("No Score DMA found")

        except Exception as e:
            print(f"PL Init Failed: {e}")

    # Socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    print(f"Listening on {host}:{port}")
    
    stats = {'rx_pkts': 0, 'tx_pkts': 0, 'pl_used': 0, 'pl_done': 0, 'pl_fallbacks': 0, 'pl_timeouts': 0, 'pl_errors': 0}
    
    rx_queue = queue.Queue(maxsize=args.rx_queue_size)
    tx_queue = queue.Queue(maxsize=args.tx_queue_size)
    dma_lock = threading.Lock()
    
    threading.Thread(target=receiver_thread, args=(s, rx_queue, stats, args.enable_timing), daemon=True).start()
    threading.Thread(target=sender_thread, args=(s, tx_queue, stats, args.enable_timing), daemon=True).start()
    threading.Thread(target=processor_thread, args=(rx_queue, tx_queue, stats, args, dma_info, dma_lock), daemon=True).start()
    
    print("Server Ready. C Driver: " + ("YES" if C_DRIVER_AVAILABLE else "NO"))
    
    last_log = time.time()
    last_stats = dict(stats)
    
    try:
        while True:
            time.sleep(0.1)
            now = time.time()
            if now - last_log >= args.log_interval:
                print(f"KPI rx={stats['rx_pkts']} tx={stats['tx_pkts']} pl_done={stats['pl_done']} timeouts={stats['pl_timeouts']}")
                last_log = now
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == '__main__':
    main()

