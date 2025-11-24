#!/usr/bin/env python3
"""
Cycle-accurate benchmark for the simulated full datapath.
Compares FPGA Hardware Latency vs CPU Reflex Latency.
Also generates a 'Jitter Kill Shot' CDF plot.
"""
import struct
import time
import numpy as np
import statistics
import csv
from pathlib import Path

from pynq import Overlay, allocate, MMIO

# Default addresses (override via .hwh resolver when possible)
# NOTE: Based on Vivado Address Editor, traffic_gen_const_0/s_axi_control is at 0x4003_0000.
TGEN_CTRL_ADDR  = 0x40030000   # traffic_gen_const_0 s_axi_control
TIMER_ADDR      = 0x40020000   # latency_timer_0 s_axi_control
DMA0_ADDR       = 0x41E00000   # axi_dma_0
DMA1_ADDR       = 0x41E10000   # axi_dma_1
MLP_ADDR        = 0x40000000   # mlp_infer_stream_0 s_axi_control
WLOAD_CTRL_ADDR = 0x40050000   # weight_loader_0 s_axi_control
WLOAD_PTR_ADDR  = 0x40010000   # weight_loader_0 s_axi_control_r (pointers)

# DMA OFFSETS
S2MM_DMACR = 0x30
S2MM_DMASR = 0x34
S2MM_DA    = 0x48
S2MM_LENGTH = 0x58

def program_traffic_gen(num_words: int):
    """
    Program constant-only traffic_gen_const using a single AXI-Lite map.

    MAP (expected from xtraffic_gen_hw.h for new IP):
      0x00 : AP_CTRL
      0x10 : num_words
      0x18 : start_r
      0x20 : done (RO)
      0x30 : w_const0
      0x38 : w_const1
      0x40 : w_const2
      0x48 : w_const3
    """
    tg = MMIO(TGEN_CTRL_ADDR, 65536)
    tg.write(0x00, 0x00)          # clear AP_CTRL
    tg.write(0x10, int(num_words))
    tg.write(0x18, 1)             # start_r
    tg.write(0x00, 0x01)          # ap_start

def run_tgen_diagnostic():
    print("\n--- TGen Diagnostic (num_words=0) ---")
    try:
        tg = MMIO(TGEN_CTRL_ADDR, 65536)
        tg.write(0x00, 0x00)  # clear
        tg.write(0x10, 0)     # num_words = 0
        tg.write(0x18, 1)     # start_r
        tg.write(0x00, 0x01)  # ap_start
        t0 = time.time()
        while (time.time() - t0) < 0.1:
            if tg.read(0x00) & 0x2:
                print("SUCCESS: TGen completed with num_words=0. Core is alive.")
                return True
            time.sleep(0.001)
        print(f"FAILURE: TGen hung with num_words=0. AP_CTRL=0x{tg.read(0x00):08X}")
        return False
    except Exception as e:
        print(f"Diagnostic failed: {e}")
        return False

def start_tgen_and_wait(num_words: int, pkt_phys_addr: int, timeout_ms: int = 50) -> bool:
    """
    Start TGen and wait briefly for its 'done' to go valid. Returns True if it completed.
    If downstream TREADY is low, this will time out (useful to detect backpressure).
    """
    # New IP: no DDR pointer window, just num_words/start/ap_start
    _ = pkt_phys_addr  # unused in constant generator
    program_traffic_gen(num_words)
    tg = MMIO(TGEN_CTRL_ADDR, 65536)
    t0 = time.time()
    while (time.time() - t0) * 1000.0 < timeout_ms:
        try:
            # Prefer AP_CTRL.ap_done (bit1), which doesn't require IER/GIE
            ap_ctrl = tg.read(0x00)
            if (ap_ctrl & 0x2) != 0:
                # Reading AP_CTRL clears ap_done (COR), treat as success
                return True
        except Exception:
            break
        time.sleep(0.0005)
    return False
        
def program_traffic_gen_const(words_be32: list):
    """
    Program constant 32-bit header words into traffic_gen_const.
    """
    ctrl = MMIO(TGEN_CTRL_ADDR, 65536)
    ctrl.write(0x30, words_be32[0])
    ctrl.write(0x38, words_be32[1])
    ctrl.write(0x40, words_be32[2])
    ctrl.write(0x48, words_be32[3])

def program_weight_loader(w0_phys: int, b0_phys: int, w1_phys: int, b1_phys: int,
                          w0_bytes: int, b0_words: int, w1_bytes: int, b1_words: int):
    """
    Configure and start weight_loader_0.
    Pointer registers are exposed on WLOAD_PTR_ADDR (control_r-like), sizes on WLOAD_CTRL_ADDR.
    Offsets (expected):
      Pointers bus (WLOAD_PTR_ADDR):
        0x10/0x14 : w0_ptr (low/high)
        0x1C/0x20 : b0_ptr (low/high)
        0x28/0x2C : w1_ptr (low/high)
        0x34/0x38 : b1_ptr (low/high)
      Sizes bus (WLOAD_CTRL_ADDR):
        0x10 : w0_bytes
        0x18 : b0_words
        0x20 : w1_bytes
        0x28 : b1_words
        0x00 : AP_CTRL (write 1 to start)
    """
    # 1) Program pointers on PTR window, verify, then mirror to CTRL if needed
    def write_ptrs(base_addr: int):
        mm = MMIO(base_addr, 65536)
        mm.write(0x10, w0_phys & 0xFFFFFFFF)
        mm.write(0x14, (w0_phys >> 32) & 0xFFFFFFFF)
        mm.write(0x1C, b0_phys & 0xFFFFFFFF)
        mm.write(0x20, (b0_phys >> 32) & 0xFFFFFFFF)
        mm.write(0x28, w1_phys & 0xFFFFFFFF)
        mm.write(0x2C, (w1_phys >> 32) & 0xFFFFFFFF)
        mm.write(0x34, b1_phys & 0xFFFFFFFF)
        mm.write(0x38, (b1_phys >> 32) & 0xFFFFFFFF)
        return mm
    def read_ptrs(base_addr: int):
        mm = MMIO(base_addr, 65536)
        return (mm.read(0x10), mm.read(0x14), mm.read(0x1C), mm.read(0x20),
                mm.read(0x28), mm.read(0x2C), mm.read(0x34), mm.read(0x38))
    try:
        write_ptrs(WLOAD_PTR_ADDR)
        vals = read_ptrs(WLOAD_PTR_ADDR)
        # If b0/b1 stayed zero (observed on hardware), mirror those two pointers on CTRL window (safe: offsets are reserved there)
        if vals[2] == 0 or vals[6] == 0:
            mm_ctrl = MMIO(WLOAD_CTRL_ADDR, 65536)
            # b0_ptr low/high
            mm_ctrl.write(0x1C, b0_phys & 0xFFFFFFFF)
            mm_ctrl.write(0x20, (b0_phys >> 32) & 0xFFFFFFFF)
            # b1_ptr low/high
            mm_ctrl.write(0x34, b1_phys & 0xFFFFFFFF)
            mm_ctrl.write(0x38, (b1_phys >> 32) & 0xFFFFFFFF)
            # Re-read both windows for confirmation
            vals = read_ptrs(WLOAD_PTR_ADDR)
            vals_ctrl = read_ptrs(WLOAD_CTRL_ADDR)
            print(f"[WLDBG] PTR win ptrs: W0L=0x{vals[0]:08X} B0L=0x{vals[2]:08X} W1L=0x{vals[4]:08X} B1L=0x{vals[6]:08X}")
            print(f"[WLDBG] CTRL win ptrs: W0L=0x{vals_ctrl[0]:08X} B0L=0x{vals_ctrl[2]:08X} W1L=0x{vals_ctrl[4]:08X} B1L=0x{vals_ctrl[6]:08X}")
    except Exception as e:
        print(f"Pointer write/read on PTR window failed: {e}")

    # 2) Program sizes on CTRL window (do NOT mirror to PTR; avoids clobbering pointers)
    def write_sizes(base_addr: int):
        mm = MMIO(base_addr, 65536)
        mm.write(0x10, int(w0_bytes))
        mm.write(0x18, int(b0_words))
        mm.write(0x20, int(w1_bytes))
        mm.write(0x28, int(b1_words))
        return mm
    def read_sizes(base_addr: int):
        mm = MMIO(base_addr, 65536)
        return (mm.read(0x10), mm.read(0x18), mm.read(0x20), mm.read(0x28))
    try:
        write_sizes(WLOAD_CTRL_ADDR)
        s = read_sizes(WLOAD_CTRL_ADDR)
        if s[1] != int(b0_words):
            print(f"Warning: weight_loader B0_WORDS readback {s[1]} != {b0_words} at 0x{WLOAD_CTRL_ADDR:08X}+0x18")
            # Safe mirror for WORDS only on PTR window (offsets 0x18/0x28 are reserved there per header)
            try:
                alt = MMIO(WLOAD_PTR_ADDR, 65536)
                alt.write(0x18, int(b0_words))
                s_alt_18 = alt.read(0x18)
                print(f"[WLDBG] Mirrored WORDS to PTR win: B0W@0x18={s_alt_18}")
            except Exception as e2:
                print(f"[WLDBG] Mirror WORDS to PTR win failed: {e2}")
    except Exception as e:
        print(f"Size write/read on CTRL window failed: {e}")

    # 3) start_r and ap_start on the control window (best-effort)
    try:
        ctrl = MMIO(WLOAD_CTRL_ADDR, 65536)
        try:
            ctrl.write(0x30, 1)
        except Exception:
            pass
        ctrl.write(0x00, 0x01)
    except Exception as e:
        print(f"Error starting weight_loader: {e}")

    # 4) Defensive: re-assert pointers AFTER sizes to avoid any alias overwrite
    try:
        # Ensure B0/B1 pointers exist on CTRL window (observed in maps)
        ctrl = MMIO(WLOAD_CTRL_ADDR, 65536)
        ctrl.write(0x1C, b0_phys & 0xFFFFFFFF)            # b0 low (safe)
        # Do NOT touch 0x20 on CTRL window; that's w1_bytes (we set it below)
        ctrl.write(0x34, b1_phys & 0xFFFFFFFF)            # b1 low
        ctrl.write(0x38, (b1_phys >> 32) & 0xFFFFFFFF)    # b1 high (safe)
        # Re-write W0/W1 low/high on PTR window (observed W1 got clobbered)
        ptr2 = MMIO(WLOAD_PTR_ADDR, 65536)
        ptr2.write(0x10, w0_phys & 0xFFFFFFFF)
        ptr2.write(0x14, (w0_phys >> 32) & 0xFFFFFFFF)
        ptr2.write(0x28, w1_phys & 0xFFFFFFFF)
        ptr2.write(0x2C, (w1_phys >> 32) & 0xFFFFFFFF)
        # Re-assert w1_bytes on CTRL window to 32 (it may have been zeroed earlier)
        ctrl.write(0x20, int(w1_bytes))
    except Exception as e:
        print(f"[WLDBG] Post-size pointer reassert failed: {e}")

def dump_regs(label: str):
    print(f"\n--- {label} ---")
    try:
        t = MMIO(TIMER_ADDR, 65536)
        print(f"TIMER @0x{TIMER_ADDR:08X}: AP_CTRL=0x{t.read(0x00):08X} CYC=0x{t.read(0x10):08X}")
    except Exception as e:
        print(f"TIMER read error: {e}")
    try:
        tg = MMIO(TGEN_CTRL_ADDR, 65536)
        print(f"TGEN  @0x{TGEN_CTRL_ADDR:08X}: AP_CTRL=0x{tg.read(0x00):08X} NUM=0x{tg.read(0x10):08X} START_R=0x{tg.read(0x18):08X}")
        print(f"       DONE=0x{tg.read(0x20):08X} W0=0x{tg.read(0x30):08X} W1=0x{tg.read(0x38):08X} W2=0x{tg.read(0x40):08X} W3=0x{tg.read(0x48):08X}")
    except Exception as e:
        print(f"TGEN read error: {e}")
    try:
        m = MMIO(MLP_ADDR, 65536)
        vals = [m.read(ofs) for ofs in (0x00,0x0C,0x30,0x38,0x40,0x48,0x50,0x58)]
        print(f"MLP   @0x{MLP_ADDR:08X}: AP_CTRL=0x{vals[0]:08X} ISR=0x{vals[1]:08X} RELOAD=0x{vals[2]:08X} DELAY=0x{vals[3]:08X} "
              f"W0B={vals[4]} B0W={vals[5]} W1B={vals[6]} B1W={vals[7]}")
    except Exception as e:
        print(f"MLP read error: {e}")
    try:
        wl = MMIO(WLOAD_CTRL_ADDR, 65536)
        print(f"WLOAD @0x{WLOAD_CTRL_ADDR:08X}: AP_CTRL=0x{wl.read(0x00):08X} W0B={wl.read(0x10)} B0W={wl.read(0x18)} W1B={wl.read(0x20)} B1W={wl.read(0x28)}")
        # Quick map sweep to spot mis-mapped regs
        try:
            words = []
            for ofs in range(0x00, 0x40, 0x04):
                words.append(f"{ofs:02X}:{wl.read(ofs):08X}")
            print("WLOAD CTRL MAP:", " ".join(words))
        except Exception:
            pass
    except Exception as e:
        print(f"WLOAD read error: {e}")
    try:
        wlptr = MMIO(WLOAD_PTR_ADDR, 65536)
        pvals = [wlptr.read(ofs) for ofs in (0x10,0x14,0x1C,0x20,0x28,0x2C,0x34,0x38)]
        print(f"WLPTR @0x{WLOAD_PTR_ADDR:08X}: W0L=0x{pvals[0]:08X} W0H=0x{pvals[1]:08X} B0L=0x{pvals[2]:08X} B0H=0x{pvals[3]:08X} "
              f"W1L=0x{pvals[4]:08X} W1H=0x{pvals[5]:08X} B1L=0x{pvals[6]:08X} B1H=0x{pvals[7]:08X}")
        # Also dump the PTR window word-like locations to detect aliasing
        try:
            words2 = []
            for ofs in range(0x00, 0x40, 0x04):
                words2.append(f"{ofs:02X}:{wlptr.read(ofs):08X}")
            print("WLOAD PTR  MAP:", " ".join(words2))
        except Exception:
            pass
    except Exception as e:
        print(f"WLPTR read error: {e}")
    try:
        d0 = MMIO(DMA0_ADDR, 65536)
        d1 = MMIO(DMA1_ADDR, 65536)
        print(f"DMA1  @0x{DMA1_ADDR:08X}: S2MM_CR=0x{d1.read(0x30):08X} S2MM_SR=0x{d1.read(0x34):08X}")
    except Exception as e:
        print(f"DMA read error: {e}")

def start_dma_s2mm(base_addr, dst_addr, length):
    mmio = MMIO(base_addr, 65536)
    # Reset IOC/Err bits first
    mmio.write(S2MM_DMASR, 0x7000) 
    # RS=1, IOC_IrqEn=1 to allow polling DMASR. IOC bit may not assert without enable.
    mmio.write(S2MM_DMACR, 0x1001)
    mmio.write(S2MM_DA, dst_addr)
    mmio.write(S2MM_LENGTH, length)
    return mmio

def read_cycles_direct() -> int:
    mmio = MMIO(TIMER_ADDR, 65536)
    return mmio.read(0x10)

def reset_timer_and_start():
    mmio = MMIO(TIMER_ADDR, 65536)
    
    # Toggle Reset (Offset 0x20 for 'reset' argument, per xlatency_timer_hw.h)
    # 0x10: cycle_count (data)
    # 0x14: cycle_count (ctrl)
    # 0x20: reset (data)
    
    # Assert Reset
    mmio.write(0x20, 1)
    # De-assert Reset
    mmio.write(0x20, 0)
    
    # Re-arm timer core via AP_CTRL (offset 0x00).
    # Even though the autogenerated header doesn't expose AP_CTRL,
    # the control_s_axi wrapper still implements the standard ap_start/ap_idle
    # register at 0x00. Writing 0x81 sets ap_start=1 and auto_restart=1,
    # letting the block run continuously and respond to start/stop triggers.
    mmio.write(0x00, 0x81)
    
def mlp_wait_done_and_clear(mlp_mmio: MMIO, timeout_us: int = 100000) -> bool:
    """
    Poll MLP ISR (0x0c) for ap_done (bit 0). Clear on detection. Timeout in microseconds.
    Returns True if done observed, else False.
    """
    t0 = time.time()
    while (time.time() - t0) * 1e6 < timeout_us:
        isr = mlp_mmio.read(0x0c)
        if (isr & 0x1) != 0:
            # Clear toggled bit
            mlp_mmio.write(0x0c, 0x1)
            return True
    return False

def build_test_packet(seq: int = 0) -> bytes:
    # Build a single 128-bit (16 bytes) feature word in network (big-endian) layout:
    # [0:3]  ofi (int32)
    # [4:5]  imb (int16)
    # [6:7]  rsv (uint16)
    # [8:11] burst (uint32)
    # [12:15] vol (uint32)
    FEAT_FMT = ">i h H I I"
    ofi = 1234
    imb = 100
    rsv = 0
    burst = 200
    vol = 300
    return struct.pack(FEAT_FMT, ofi, imb, rsv, burst, vol)

def build_zero_header_words32() -> list:
    """
    Build a 32-byte header (8 x 32-bit words) with delta_count=0.
    Feature pipeline reads four 64-bit beats; zeros are acceptable and
    cause it to emit an immediate feature when delta_count==0.
    """
    header = bytearray(32)
    # bytes 6..7 hold flags (bit15 reset, bits[14:0] delta_count). Keep zero.
    # t_send_ns bytes 14..21 can be zero.
    # Return as big-endian 32-bit words for use_const path.
    words = []
    for i in range(0, 32, 4):
        words.append(int.from_bytes(header[i:i+4], 'big', signed=False))
    return words

# --- CPU REFLEX SIMULATION ---
def cpu_reflex_task(packet_data):
    # Supports two input formats:
    # 1) Original 48B packet: [32B header][16B delta]
    # 2) New 16B feature-only packet: [ofi:int32][imb:int16][rsv:uint16][burst:uint32][vol:uint32]
    if len(packet_data) >= 48:
        HDR_FMT = ">4sBBHHIQQH"
        DELTA_FMT = ">iiHBBI"
        magic, ver, msg_type, flags_be, hdr_len_be, seq_be, t_send_be, t_ing_be, rsv2 = struct.unpack(HDR_FMT, packet_data[:32])
        price_ticks, qty, level, side, action, _ = struct.unpack(DELTA_FMT, packet_data[32:48])
        best_bid_p = price_ticks
        best_ask_p = price_ticks + 100
    elif len(packet_data) >= 16:
        FEAT_FMT = ">i h H I I"
        ofi, imb, rsv, burst, vol = struct.unpack(FEAT_FMT, packet_data[:16])
        best_bid_p = ofi
        best_ask_p = ofi + 100
    else:
        # Not enough data; return neutral decision
        return 0
    decision = 0
    if best_bid_p >= best_ask_p:
        decision = 2
    elif (best_ask_p - best_bid_p) > 1000:
        decision = 3
    return decision

def run_cpu_benchmark(packet_data, iterations=1000):
    latencies = []
    for _ in range(iterations):
        t0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
        _ = cpu_reflex_task(packet_data)
        t1 = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
        latencies.append(t1 - t0)
    return latencies

def run_fpga_benchmark(ol, buf, pkt_phys, num_words, iterations=1000):
    latencies_ns = []
    dma_fallback_ns = []
    
    # Pre-allocate DMA buffers once
    feat_buf = allocate(shape=(64,), dtype="u1")
    score_buf = allocate(shape=(64,), dtype="u1")
    
    mlp = MMIO(MLP_ADDR, 65536)
    dma1 = MMIO(DMA1_ADDR, 65536)
    
    tgen_timeout_count = 0
    first_tgen_msg_printed = False
    for i in range(iterations):
        # -1. Clear any stale MLP done/ready and DMA IOC/Err
        try: mlp.write(0x0c, 0x3)
        except Exception: pass
        try: dma1.write(S2MM_DMASR, 0x7000)
        except Exception: pass

        # 0. Reset Timer (Essential to prevent accumulation) - single-shot.
        # Also clear MLP ISR again right before arming to ensure stop_trigger isn't stuck high.
        try: mlp.write(0x0c, 0x3)
        except Exception: pass
        reset_timer_and_start()

        # 1. Re-Arm DMA for score (must be done every time as they complete)
        start_dma_s2mm(DMA1_ADDR, score_buf.physical_address, 4)
        
        # 2. Start TGen
        tgen_done = start_tgen_and_wait(num_words, pkt_phys, timeout_ms=20)
        if not tgen_done:
            tgen_timeout_count += 1
            if not first_tgen_msg_printed:
                print("[DBG] TGen did not complete (20ms). Suppressing further messages. Check stream TREADY or control offsets.")
                first_tgen_msg_printed = True
        
        # 3. Wait for MLP done (which also stops the hardware timer)
        done = mlp_wait_done_and_clear(mlp, timeout_us=200000)  # 200 us window
        if not done:
            # If MLP doesn't signal done, skip this iteration
            continue

        # 4. Read final hardware cycle count
        c = read_cycles_direct()
        if c > 0:
            # 125 MHz clock -> 8 ns per cycle
            latencies_ns.append(c * 8)
        # else leave as missing; no SW fallback here while we focus on pure HW
            
    if tgen_timeout_count > 0:
        print(f"[DBG] TGen timeout summary: {tgen_timeout_count}/{iterations} iterations")
    return latencies_ns

def main():
    print("Loading Overlay...")
    ol = Overlay("/home/xilinx/feature_overlay.bit")
    
    ENABLE_WEIGHT_LOAD = False  # temporary: bypass weight streaming while we validate datapath/timer
    
    # Resolve base addresses from .hwh (best-effort)
    try:
        for k, v in ol.ip_dict.items():
            name = k.lower()
            if 'latency_timer' in name and 's_axi_control' in name and 'phys_addr' in v:
                global TIMER_ADDR; TIMER_ADDR = v['phys_addr']
            if ('traffic_gen_const' in name or 'traffic_gen' in name) and '/s_axi_control' in name and 'phys_addr' in v:
                global TGEN_CTRL_ADDR; TGEN_CTRL_ADDR = v['phys_addr']
            if 'feature_pipeline' in name and 'phys_addr' in v:
                # If feature_pipeline has an address, it might need starting
                print(f"[INFO] Found feature_pipeline at 0x{v['phys_addr']:08X}")
            if 'mlp_infer_stream' in name and 's_axi_control' in name and 'phys_addr' in v:
                global MLP_ADDR; MLP_ADDR = v['phys_addr']
            if 'weight_loader' in name and '/s_axi_control' in name and 'phys_addr' in v:
                global WLOAD_CTRL_ADDR; WLOAD_CTRL_ADDR = v['phys_addr']
            if 'weight_loader' in name and ('/s_axi_ctrl' in name or 'control_r' in name) and 'phys_addr' in v:
                global WLOAD_PTR_ADDR; WLOAD_PTR_ADDR = v['phys_addr']
            if 'axi_dma_0' in name and 'phys_addr' in v:
                global DMA0_ADDR; DMA0_ADDR = v['phys_addr']
            if 'axi_dma_1' in name and 'phys_addr' in v:
                global DMA1_ADDR; DMA1_ADDR = v['phys_addr']
    except Exception:
        pass
    print(f"\nResolved addrs:"
          f" TIMER=0x{TIMER_ADDR:08X}"
          f" TGEN_CTRL=0x{TGEN_CTRL_ADDR:08X}"
          f" MLP=0x{MLP_ADDR:08X}"
          f" WLOAD_CTRL=0x{WLOAD_CTRL_ADDR:08X}"
          f" WLOAD_PTR=0x{WLOAD_PTR_ADDR:08X}"
          f" DMA0=0x{DMA0_ADDR:08X}"
          f" DMA1=0x{DMA1_ADDR:08X}")

    # Run TGen Diagnostic
    if not run_tgen_diagnostic():
        print("ABORTING: TGen core unresponsive.")
        return

    # Init MLP interrupts/Control
    try:
        mlp = MMIO(MLP_ADDR, 65536)
        mlp.write(0x04, 1) # GIE
        mlp.write(0x08, 1) # IER
        mlp.write(0x00, 0x00) # Stop (Do not auto-restart yet)
        print("MLP Configured.")
        
        # Program delay_cycles default 0 (0x38). We keep this hook for future
        # calibration, but normal measurements run with no artificial delay.
        DELAY_OFFSET = 0x38
        mlp.write(DELAY_OFFSET, 0)
        
    except Exception as e:
        print(f"Error configuring MLP: {e}")
        pass

    # --- WEIGHT LOAD path (temporarily optional to unblock datapath test) ---
    if ENABLE_WEIGHT_LOAD:
        # Minimal dummy weights for bench
        W0_BYTES = 128; B0_WORDS = 32; W1_BYTES = 32; B1_WORDS = 1
        w0_buf = allocate(shape=(W0_BYTES,), dtype='u1'); w0_buf[:] = 1; w0_buf.flush()
        b0_buf = allocate(shape=(B0_WORDS,), dtype='u4'); b0_buf[:] = 0; b0_buf.flush()
        w1_buf = allocate(shape=(W1_BYTES,), dtype='u1'); w1_buf[:] = 1; w1_buf.flush()
        b1_buf = allocate(shape=(B1_WORDS,), dtype='u4'); b1_buf[:] = 0; b1_buf.flush()
        # Program mlp sizes and set reload=1 to consume the stream
        try:
            mlp = MMIO(MLP_ADDR, 65536)
            mlp.write(0x40, W0_BYTES); mlp.write(0x48, B0_WORDS)
            mlp.write(0x50, W1_BYTES); mlp.write(0x58, B1_WORDS)
            mlp.write(0x30, 1)  # reload on
            # Start MLP once to execute the reload path
            mlp.write(0x00, 0x01)  # ap_start
        except Exception as e:
            print(f"Error programming MLP sizes/reload: {e}")
        # Stream weights
        try:
            program_weight_loader(w0_buf.physical_address, b0_buf.physical_address,
                                  w1_buf.physical_address, b1_buf.physical_address,
                                  W0_BYTES, B0_WORDS, W1_BYTES, B1_WORDS)
            # Wait for MLP to finish reload (ap_done)
            done = mlp_wait_done_and_clear(MMIO(MLP_ADDR, 65536), timeout_us=200000)
            if not done:
                print("Warning: MLP reload did not signal done (timeout).")
            dump_regs("After weight load")
            mlp.write(0x30, 0)  # reload off
            mlp.write(0x00, 0x81)  # auto-restart
            print("Weights Loaded. Switched to Inference Mode.")
        except Exception as e:
            print(f"Weight load failed (continuing with zeros): {e}")
    else:
        # No reload: ensure MLP is in inference mode and auto-restart
        try:
            mlp = MMIO(MLP_ADDR, 65536)
            mlp.write(0x30, 0)     # reload off
            mlp.write(0x00, 0x81)  # auto-restart
            dump_regs("After weight load (skipped)")
        except Exception as e:
            print(f"Error enabling inference mode: {e}")

    # Prepare single-beat feature packet (16 bytes) and load into DMA buf
    pkt = build_test_packet(seq=0)
    # For hardware path, send a 32-byte header (8 words) so feature_pipeline
    # will accept input and emit a single 128-bit feature beat.
    header_words = build_zero_header_words32()
    num_words = len(header_words)
    buf = allocate(shape=(len(pkt),), dtype="u1")
    buf[: len(pkt)] = np.frombuffer(pkt, dtype=np.uint8)
    buf.flush()
    # Program TGEN to emit a 32-byte header via constants
    program_traffic_gen_const(header_words)
    dump_regs("Before benchmark loop")

    N = 100
    print(f"\n--- RUNNING BENCHMARKS (N={N}) ---")
    
    # 1. CPU Reflex
    print("Running CPU Reflex Benchmark...")
    cpu_stats = run_cpu_benchmark(pkt, N)
    
    # 2. FPGA Hardware
    print("Running FPGA Hardware Benchmark...")
    fpga_stats = run_fpga_benchmark(ol, buf, buf.physical_address, num_words, N)
    if not fpga_stats:
        dump_regs("After benchmark (no data)")
    
    # Report
    def report(name, data):
        if not data:
            print(f"{name}: No Data")
            return
        avg = statistics.mean(data)
        mdn = statistics.median(data)
        stdev = statistics.stdev(data) if len(data) > 1 else 0
        mn = min(data)
        mx = max(data)
        print(f"{name:25} | Avg: {avg/1000:6.2f} us | Min: {mn/1000:6.2f} us | Max: {mx/1000:6.2f} us | Jitter(std): {stdev:6.2f} ns")

    print("\n" + "="*80)
    print(f"{'METRIC':25} | {'AVERAGE':9} | {'MIN':9} | {'MAX':9} | {'JITTER'}")
    print("="*80)
    report("CPU Reflex Lane", cpu_stats)
    report("FPGA Neuro Lane", fpga_stats)
    print("="*80)
    
    # Ratio
    if cpu_stats and fpga_stats:
        cpu_avg = statistics.mean(cpu_stats)
        fpga_avg = statistics.mean(fpga_stats)
        speedup = cpu_avg / fpga_avg
        print(f"\nFPGA Speedup Factor: {speedup:.2f}x")

    # Save results to CSV for plotting
    print("\nSaving raw data to 'latency_comparison.csv'...")
    with open('latency_comparison.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['cpu_ns', 'fpga_ns'])
        # Pad shorter list with None
        max_len = max(len(cpu_stats), len(fpga_stats))
        for i in range(max_len):
            c = cpu_stats[i] if i < len(cpu_stats) else ''
            f = fpga_stats[i] if i < len(fpga_stats) else ''
            writer.writerow([c, f])
    
    print("Data saved. Now copy 'latency_comparison.csv' to host and run the plotter.")

if __name__ == "__main__":
    main()
