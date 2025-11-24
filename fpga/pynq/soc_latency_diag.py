#!/usr/bin/env python3
"""
SoC latency diagnostics for the Neuro-HFT FPGA overlay.

This script is intentionally separate from `run_cycle_bench.py` and is focused
on **explaining** where the cycles go in the internal Pynq benchmark:

    traffic_gen_const_0 -> feature_pipeline_0 -> mlp_infer_stream_0 -> DMA1
                      \-> latency_timer_0

It runs a small matrix of experiments:

  1) Sweep `delay_cycles` on the MLP (0, 1e3, 1e4, 1e5) at fixed header size
     to see whether timer counts track added work inside `mlp_infer_stream_0`.
  2) Sweep `num_words` on the traffic generator (0, 4, 8, 16) at fixed
     `delay_cycles` to see whether header / feature parsing changes latency.

For each configuration it reports:
  - Cycle count from `latency_timer_0` (median / average / min / max).
  - Latency in nanoseconds using 8 ns per cycle (125 MHz).
  - Basic register dumps if no data is collected.

Usage (on Pynq):

  sudo -E env PYNQ_XRT=0 /usr/local/share/pynq-venv/bin/python3 -u soc_latency_diag.py

You can safely run this alongside the existing `run_cycle_bench.py` bitfile,
as it assumes the same address map and overlay name.
"""

import statistics
import time
from pathlib import Path

import numpy as np
from pynq import MMIO, Overlay, allocate


# Default physical base addresses (overridden from .hwh when possible)
TGEN_CTRL_ADDR   = 0x40030000   # traffic_gen_const_0 s_axi_control
TIMER_MLP_ADDR   = 0x40020000   # latency_timer_0 s_axi_control (MLP done_pulse)
TIMER_FEAT_ADDR  = 0x40040000   # latency_timer_1 s_axi_control (feature done_pulse)
FEATURE_ADDR     = 0x40060000   # feature_pipeline_0 s_axi_CTRL (debug cycles)
DMA1_ADDR        = 0x41E10000   # axi_dma_1
MLP_ADDR         = 0x40000000   # mlp_infer_stream_0 s_axi_control
WLOAD_CTRL_ADDR  = 0x40050000   # weight_loader_0 s_axi_control (not used here)
WLOAD_PTR_ADDR   = 0x40010000   # weight_loader_0 pointer window (not used here)

# DMA register offsets (S2MM)
S2MM_DMACR = 0x30
S2MM_DMASR = 0x34
S2MM_DA = 0x48
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


def start_tgen_and_wait(num_words: int, timeout_ms: int = 50) -> bool:
    """
    Start TGen and wait briefly for its 'done' to go valid. Returns True if it
    completed. If downstream TREADY is low, this will time out (useful to
    detect backpressure).
    """
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


def program_traffic_gen_const(words_be32):
    """
    Program constant 32-bit header words into traffic_gen_const.
    """
    ctrl = MMIO(TGEN_CTRL_ADDR, 65536)
    ctrl.write(0x30, int(words_be32[0]))
    ctrl.write(0x38, int(words_be32[1]))
    ctrl.write(0x40, int(words_be32[2]))
    ctrl.write(0x48, int(words_be32[3]))


def start_dma_s2mm(base_addr: int, dst_addr: int, length: int) -> MMIO:
    """
    Arm the AXI DMA S2MM channel for a writeback of `length` bytes starting at
    physical address `dst_addr`.
    """
    mmio = MMIO(base_addr, 65536)
    # Reset IOC/Err bits first
    mmio.write(S2MM_DMASR, 0x7000)
    # RS=1, IOC_IrqEn=1 to allow polling DMASR. IOC bit may not assert without enable.
    mmio.write(S2MM_DMACR, 0x1001)
    mmio.write(S2MM_DA, dst_addr)
    mmio.write(S2MM_LENGTH, length)
    return mmio


def reset_timers_and_start():
    """
    Per-iteration timer reset + arm for BOTH latency timers
    (MLP and feature). This keeps their counts aligned so we
    can compare subsystem latencies.
    """
    # Arm the two reliable latency timers:
    #   - TIMER_MLP_ADDR  : hw_start -> MLP done_pulse
    #   - TIMER_FEAT_ADDR : hw_start -> feature feat_done_pulse
    for addr in (TIMER_MLP_ADDR, TIMER_FEAT_ADDR):
        try:
            mmio = MMIO(addr, 65536)
            # Assert Reset
            mmio.write(0x20, 1)
            # De-assert Reset
            mmio.write(0x20, 0)
            # Re-arm timer core via AP_CTRL (offset 0x00)
            mmio.write(0x00, 0x81)
        except Exception:
            # If a timer instance is absent, ignore.
            continue


def read_mlp_cycles_direct() -> int:
    mmio = MMIO(TIMER_MLP_ADDR, 65536)
    return mmio.read(0x10)


def read_feat_cycles_direct() -> int:
    mmio = MMIO(TIMER_FEAT_ADDR, 65536)
    return mmio.read(0x10)


def read_tgen_cycles_direct() -> int:
    """
    Timer 2 (TGen) is not reliable in the current design; treat its
    contribution as zero so we focus on the well-behaved timers.
    """
    return 0


def mlp_wait_done_and_clear(mlp_mmio: MMIO, timeout_us: int = 200_000) -> bool:
    """
    Poll MLP ISR (0x0c) for ap_done (bit 0). Clear on detection.
    Returns True if done observed, else False.
    """
    t0 = time.time()
    while (time.time() - t0) * 1e6 < timeout_us:
        isr = mlp_mmio.read(0x0C)
        if (isr & 0x1) != 0:
            # Clear toggled bit
            mlp_mmio.write(0x0C, 0x1)
            return True
    return False


def build_zero_header_words32():
    """
    Build a 32-byte header (8 x 32-bit words) with delta_count=0.

    Feature pipeline reads four 64-bit beats; zeros are acceptable and
    cause it to emit an immediate feature when delta_count==0.
    """
    header = bytearray(32)
    words = []
    for i in range(0, 32, 4):
        words.append(int.from_bytes(header[i:i + 4], "big", signed=False))
    return words


def dump_regs(label: str):
    print(f"\n--- {label} ---")
    try:
        t = MMIO(TIMER_MLP_ADDR, 65536)
        print(f"TIMER_MLP  @0x{TIMER_MLP_ADDR:08X}: AP_CTRL=0x{t.read(0x00):08X} CYC=0x{t.read(0x10):08X}")
    except Exception as e:
        print(f"TIMER_MLP read error: {e}")
    try:
        tf = MMIO(TIMER_FEAT_ADDR, 65536)
        print(f"TIMER_FEAT @0x{TIMER_FEAT_ADDR:08X}: AP_CTRL=0x{tf.read(0x00):08X} CYC=0x{tf.read(0x10):08X}")
    except Exception as e:
        print(f"TIMER_FEAT read error: {e}")
    try:
        tg = MMIO(TGEN_CTRL_ADDR, 65536)
        print(
            f"TGEN  @0x{TGEN_CTRL_ADDR:08X}: AP_CTRL=0x{tg.read(0x00):08X} "
            f"NUM=0x{tg.read(0x10):08X} START_R=0x{tg.read(0x18):08X}"
        )
        print(
            f"       DONE=0x{tg.read(0x20):08X} W0=0x{tg.read(0x30):08X} "
            f"W1=0x{tg.read(0x38):08X} W2=0x{tg.read(0x40):08X} W3=0x{tg.read(0x48):08X}"
        )
    except Exception as e:
        print(f"TGEN read error: {e}")
    try:
        fp = MMIO(FEATURE_ADDR, 65536)
        dbg = fp.read(0x10)
        print(f"FEAT  @0x{FEATURE_ADDR:08X}: DBG_CYCLES={dbg}")
    except Exception as e:
        print(f"FEATURE read error: {e}")
    try:
        m = MMIO(MLP_ADDR, 65536)
        vals = [m.read(ofs) for ofs in (0x00, 0x0C, 0x30, 0x38, 0x40, 0x48, 0x50, 0x58, 0x60)]
        print(
            f"MLP   @0x{MLP_ADDR:08X}: AP_CTRL=0x{vals[0]:08X} ISR=0x{vals[1]:08X} "
            f"RELOAD=0x{vals[2]:08X} DELAY=0x{vals[3]:08X} "
            f"W0B={vals[4]} B0W={vals[5]} W1B={vals[6]} B1W={vals[7]} DBG_ITERS={vals[8]}"
        )
    except Exception as e:
        print(f"MLP read error: {e}")
    try:
        d1 = MMIO(DMA1_ADDR, 65536)
        print(f"DMA1  @0x{DMA1_ADDR:08X}: S2MM_CR=0x{d1.read(0x30):08X} S2MM_SR=0x{d1.read(0x34):08X}")
    except Exception as e:
        print(f"DMA read error: {e}")


def run_fpga_once(delay_cycles: int, num_words: int) -> int | None:
    """
    Run a single FPGA inference for the given configuration and return the
    hardware cycle count from latency_timer, or None on timeout.
    """
    # Prepare MLP MMIO
    mlp = MMIO(MLP_ADDR, 65536)

    # 0. Program delay_cycles
    DELAY_OFFSET = 0x38
    mlp.write(DELAY_OFFSET, int(delay_cycles))

    # 1. Clear any stale MLP done/ready and DMA status
    try:
        mlp.write(0x0C, 0x3)
    except Exception:
        pass
    try:
        dma1 = MMIO(DMA1_ADDR, 65536)
        dma1.write(S2MM_DMASR, 0x7000)
    except Exception:
        pass

    # 2. Reset timers and arm
    reset_timers_and_start()

    # 3. Arm DMA for score (single 32-bit word => 4 bytes)
    score_buf = allocate(shape=(64,), dtype="u1")
    start_dma_s2mm(DMA1_ADDR, score_buf.physical_address, 4)

    # 4. Start TGen
    tgen_done = start_tgen_and_wait(num_words, timeout_ms=20)
    if not tgen_done:
        # TGen backpressure or flow issue; treat as failed iteration
        return None

    # 5. Wait for MLP done (which also stops the hardware timer)
    done = mlp_wait_done_and_clear(mlp, timeout_us=200_000)
    if not done:
        return None

    # 6. Read final hardware cycle count (MLP timer)
    c = read_mlp_cycles_direct()
    return int(c) if c > 0 else None


def run_fpga_once_traced(delay_cycles: int, num_words: int, iteration: int) -> int | None:
    """
    Verbose single-iteration run that prints out:
      - timer cycles
      - DMA1 S2MM_SR
      - MLP AP_CTRL / ISR
    along with whether TGen or MLP timed out.
    """
    mlp = MMIO(MLP_ADDR, 65536)
    dma1 = MMIO(DMA1_ADDR, 65536)

    # Program delay_cycles
    DELAY_OFFSET = 0x38
    mlp.write(DELAY_OFFSET, int(delay_cycles))

    # Clear any stale MLP done/ready and DMA status
    try:
        mlp.write(0x0C, 0x3)
    except Exception:
        pass
    try:
        dma1.write(S2MM_DMASR, 0x7000)
    except Exception:
        pass

    # Snapshot before arming timer
    ap_before = mlp.read(0x00)
    isr_before = mlp.read(0x0C)
    dbg_before = mlp.read(0x60)

    reset_timers_and_start()

    # Arm DMA for score
    score_buf = allocate(shape=(64,), dtype="u1")
    start_dma_s2mm(DMA1_ADDR, score_buf.physical_address, 4)

    # Start TGen
    tgen_done = start_tgen_and_wait(num_words, timeout_ms=20)
    if not tgen_done:
        cycles = read_mlp_cycles_direct()
        dma_sr = dma1.read(S2MM_DMASR)
        print(
            f"[iter {iteration:02d}] TGEN TIMEOUT  "
            f"cycles={cycles} delay={delay_cycles} num_words={num_words} "
            f"DMA1_SR=0x{dma_sr:08X} MLP_AP=0x{ap_before:08X} MLP_ISR=0x{isr_before:08X}"
        )
        return None

    # Wait for MLP done
    done = mlp_wait_done_and_clear(mlp, timeout_us=200_000)
    ap_after = mlp.read(0x00)
    isr_after = mlp.read(0x0C)
    dbg_after = mlp.read(0x60)
    dma_sr_after = dma1.read(S2MM_DMASR)
    # Read feature debug cycles (best-effort; may be from last packet)
    try:
        fp = MMIO(FEATURE_ADDR, 65536)
        feat_dbg = fp.read(0x10)
    except Exception:
        feat_dbg = -1
    cycles = read_mlp_cycles_direct()
    feat_cycles = read_feat_cycles_direct()
    tgen_cycles = read_tgen_cycles_direct()
    # Segment breakdown (clamped to >=0)
    feat_only = feat_cycles - tgen_cycles if feat_cycles >= tgen_cycles else 0
    mlp_only = cycles - feat_cycles if cycles >= feat_cycles else 0

    if not done:
        print(
            f"[iter {iteration:02d}] MLP TIMEOUT   "
            f"cycles_mlp={cycles} cycles_feat={feat_cycles} cycles_tgen={tgen_cycles} "
            f"feat_only={feat_only} mlp_only={mlp_only} feat_dbg={feat_dbg} "
            f"delay={delay_cycles} num_words={num_words} "
            f"DMA1_SR=0x{dma_sr_after:08X} MLP_AP=0x{ap_after:08X} MLP_ISR=0x{isr_after:08X} "
            f"DBG_ITERS(before/after)={dbg_before}/{dbg_after}"
        )
        return None

    print(
        f"[iter {iteration:02d}] OK            "
        f"cycles_mlp={cycles} cycles_feat={feat_cycles} cycles_tgen={tgen_cycles} "
        f"feat_only={feat_only} mlp_only={mlp_only} feat_dbg={feat_dbg} "
        f"delay={delay_cycles} num_words={num_words} "
        f"DMA1_SR=0x{dma_sr_after:08X} "
        f"MLP_AP(before/after)=0x{ap_before:08X}/0x{ap_after:08X} "
        f"MLP_ISR(before/after)=0x{isr_before:08X}/0x{isr_after:08X} "
        f"DBG_ITERS(before/after)={dbg_before}/{dbg_after}"
    )

    return int(cycles) if cycles > 0 else None


def summarize_cycles(label: str, cycles: list[int]):
    if not cycles:
        print(f"{label}: NO DATA")
        return
    avg = statistics.mean(cycles)
    mdn = statistics.median(cycles)
    mn = min(cycles)
    mx = max(cycles)
    stdev = statistics.stdev(cycles) if len(cycles) > 1 else 0.0
    # Convert to ns assuming 125 MHz
    to_ns = lambda c: c * 8.0
    print(f"\n[{label}]")
    print(f"  Samples        : {len(cycles)}")
    print(f"  Cycles (avg)   : {avg:.1f}")
    print(f"         median  : {mdn:.1f}")
    print(f"         min/max : {mn} / {mx}")
    print(f"         stdev   : {stdev:.1f}")
    print(f"  Latency ns (avg): {to_ns(avg):.1f} ns")
    print(f"             min : {to_ns(mn):.1f} ns")
    print(f"             max : {to_ns(mx):.1f} ns")


def resolve_ip_bases(ol: Overlay):
    """
    Best-effort resolution of IP physical base addresses from .hwh metadata.
    Mirrors the logic used in run_cycle_bench.py so this stays in sync with
    the Vivado design without hard-coding addresses.
    """
    global TIMER_MLP_ADDR, TIMER_FEAT_ADDR, TGEN_CTRL_ADDR, FEATURE_ADDR, MLP_ADDR, WLOAD_CTRL_ADDR, WLOAD_PTR_ADDR, DMA1_ADDR
    try:
        for k, v in ol.ip_dict.items():
            name = k.lower()
            if "latency_timer" in name and "s_axi_control" in name and "phys_addr" in v:
                # Distinguish the two timers by instance name.
                #   latency_timer_0 -> MLP done_pulse
                #   latency_timer_1 -> feature_pipeline feat_done_pulse
                if "latency_timer_0" in name:
                    TIMER_MLP_ADDR = v["phys_addr"]
                elif "latency_timer_1" in name:
                    TIMER_FEAT_ADDR = v["phys_addr"]
            if ("traffic_gen_const" in name or "traffic_gen" in name) and "/s_axi_control" in name and "phys_addr" in v:
                TGEN_CTRL_ADDR = v["phys_addr"]
            if "feature_pipeline" in name and "/s_axi_ctrl" in name and "phys_addr" in v:
                FEATURE_ADDR = v["phys_addr"]
            if "mlp_infer_stream" in name and "s_axi_control" in name and "phys_addr" in v:
                MLP_ADDR = v["phys_addr"]
            if "weight_loader" in name and "/s_axi_control" in name and "phys_addr" in v:
                WLOAD_CTRL_ADDR = v["phys_addr"]
            if "weight_loader" in name and ("/s_axi_ctrl" in name or "control_r" in name) and "phys_addr" in v:
                WLOAD_PTR_ADDR = v["phys_addr"]
            if "axi_dma_1" in name and "phys_addr" in v:
                DMA1_ADDR = v["phys_addr"]
    except Exception:
        pass


def configure_mlp_for_inference():
    """
    Put mlp_infer_stream into inference/auto-restart mode with reload disabled
    and delay=0. We leave scales at their default values (they don't affect
    latency meaningfully).
    """
    try:
        mlp = MMIO(MLP_ADDR, 65536)
        # Enable global + channel interrupts
        mlp.write(0x04, 1)  # GIE
        mlp.write(0x08, 1)  # IER
        # Ensure reload is off and auto-restart is on
        mlp.write(0x30, 0)      # reload_weights off
        mlp.write(0x38, 0)      # delay_cycles = 0
        mlp.write(0x00, 0x81)   # ap_start + auto_restart
        print("MLP configured for inference (reload off, auto-restart on).")
    except Exception as e:
        print(f"Error configuring MLP: {e}")


def program_header_constants():
    """
    Program a zeroed header into traffic_gen_const so that feature_pipeline
    sees delta_count == 0 and immediately emits a feature.
    """
    header_words = build_zero_header_words32()
    program_traffic_gen_const(header_words)
    return len(header_words)


def main():
    print("Loading Overlay...")
    # Reuse the same bitfile path as run_cycle_bench.py
    bitfile_path = Path("/home/xilinx/feature_overlay.bit")
    ol = Overlay(str(bitfile_path))

    # Resolve base addresses from .hwh (best-effort)
    resolve_ip_bases(ol)
    print(
        f"\nResolved addrs:"
        f" TIMER_MLP=0x{TIMER_MLP_ADDR:08X}"
        f" TIMER_FEAT=0x{TIMER_FEAT_ADDR:08X}"
        f" TGEN_CTRL=0x{TGEN_CTRL_ADDR:08X}"
        f" MLP=0x{MLP_ADDR:08X}"
        f" WLOAD_CTRL=0x{WLOAD_CTRL_ADDR:08X}"
        f" WLOAD_PTR=0x{WLOAD_PTR_ADDR:08X}"
        f" DMA1=0x{DMA1_ADDR:08X}"
    )

    configure_mlp_for_inference()

    num_words_for_zero_header = program_header_constants()
    dump_regs("After header programming")

    N = 50  # iterations per configuration

    # --- Experiment 1: delay_cycles sweep at fixed num_words (zero-header path) ---
    print("\n=== Experiment 1: delay_cycles sweep (num_words fixed) ===")
    fixed_num_words = num_words_for_zero_header
    for delay in [0, 1_000, 10_000, 100_000]:
        cycles = []
        for _ in range(N):
            c = run_fpga_once(delay_cycles=delay, num_words=fixed_num_words)
            if c is not None:
                cycles.append(c)
        summarize_cycles(f"delay_cycles={delay} num_words={fixed_num_words}", cycles)
        if not cycles:
            dump_regs(f"Experiment 1 (delay={delay}) - no data")

    # --- Experiment 2: num_words sweep at fixed delay_cycles ---
    print("\n=== Experiment 2: num_words sweep (delay_cycles fixed) ===")
    fixed_delay = 0
    for num_words in [0, 4, num_words_for_zero_header, 16]:
        cycles = []
        for _ in range(N):
            c = run_fpga_once(delay_cycles=fixed_delay, num_words=num_words)
            if c is not None:
                cycles.append(c)
        summarize_cycles(f"delay_cycles={fixed_delay} num_words={num_words}", cycles)
        if not cycles:
            dump_regs(f"Experiment 2 (num_words={num_words}) - no data")

    # --- Experiment 3: per-iteration trace at a representative config ---
    print("\n=== Experiment 3: per-iteration trace (delay_cycles=0, num_words=zero-header) ===")
    trace_delay = 0
    trace_num_words = num_words_for_zero_header
    N_trace = 20
    trace_cycles = []
    for i in range(N_trace):
        c = run_fpga_once_traced(delay_cycles=trace_delay, num_words=trace_num_words, iteration=i)
        if c is not None:
            trace_cycles.append(c)
    summarize_cycles(
        f"TRACE summary delay_cycles={trace_delay} num_words={trace_num_words}",
        trace_cycles,
    )


if __name__ == "__main__":
    main()

