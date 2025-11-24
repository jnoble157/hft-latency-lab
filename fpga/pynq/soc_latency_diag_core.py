#!/usr/bin/env python3
"""
SoC latency diagnostics for the **mlp_core_stream (no-DMA, no AXI-Lite)** overlay.

Datapath (core overlay):

    traffic_gen_const_0 -> axis_dwidth_converter_0 -> mlp_core_stream_0 -> score_sink_0
                        \-> latency_timer_0  (start: hw_start, stop: score_sink done_pulse)

This script measures pure fabric latency from TGen start to the score being
consumed by `score_sink_0`, using the minimal `mlp_core_stream` wrapper
with `ap_ctrl_none` and no AXI-Lite in the hot path.

Usage on Pynq:

  sudo -E env PYNQ_XRT=0 /usr/local/share/pynq-venv/bin/python3 -u soc_latency_diag_core.py

By default it loads `/home/xilinx/feature_overlay_mlp_core.bit`. Override via:

  NFPGA_BITFILE_CORE=/path/to/bit sudo -E env PYNQ_XRT=0 ... soc_latency_diag_core.py
"""

import os
import statistics
import time
from pathlib import Path

from pynq import MMIO, Overlay


# Default physical base addresses (overridden from .hwh when possible)
FABRIC_TIMER_ADDR = 0x40020000   # latency_timer_0 s_axi_control (hw_start -> score_sink done_pulse)
TGEN_CTRL_ADDR = 0x40030000      # traffic_gen_const_0 s_axi_control


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


def reset_fabric_timer_and_start():
    """
    Per-iteration timer reset + arm for latency_timer_0
    (hw_start -> score_sink done_pulse).
    """
    try:
        mmio = MMIO(FABRIC_TIMER_ADDR, 65536)
        # Assert Reset
        mmio.write(0x20, 1)
        # De-assert Reset
        mmio.write(0x20, 0)
        # Re-arm timer core via AP_CTRL (offset 0x00)
        mmio.write(0x00, 0x81)
    except Exception:
        pass


def read_fabric_cycles_direct() -> int:
    mmio = MMIO(FABRIC_TIMER_ADDR, 65536)
    return mmio.read(0x10)


def build_zero_header_words32():
    """
    Build a 32-byte "header" (8 x 32-bit words). For this overlay we just care
    about having a known payload; traffic_gen_const will repeat these words on
    its 32-bit stream.
    """
    header = bytearray(32)
    words = []
    for i in range(0, 32, 4):
        words.append(int.from_bytes(header[i:i + 4], "big", signed=False))
    return words


def dump_regs(label: str):
    print(f"\n--- {label} ---")
    try:
        t = MMIO(FABRIC_TIMER_ADDR, 65536)
        print(f"TIMER_FABRIC @0x{FABRIC_TIMER_ADDR:08X}: AP_CTRL=0x{t.read(0x00):08X} CYC=0x{t.read(0x10):08X}")
    except Exception as e:
        print(f"TIMER_FABRIC read error: {e}")
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


def run_fpga_once(num_words: int) -> int | None:
    """
    Run a single FPGA inference for the given configuration and return the
    fabric cycle count from latency_timer_0, or None on timeout.
    """
    # 1. Reset timer and arm
    reset_fabric_timer_and_start()

    # 2. Start TGen
    tgen_done = start_tgen_and_wait(num_words, timeout_ms=20)
    if not tgen_done:
        return None

    # 3. Wait a short time for score_sink / timer to finish
    time.sleep(0.001)

    # 4. Read final hardware cycle count
    c = read_fabric_cycles_direct()
    return int(c) if c > 0 else None


def run_fpga_once_traced(num_words: int, iteration: int) -> int | None:
    """
    Verbose single-iteration run that prints:
      - fabric timer cycles
      - basic TGen state
    """
    reset_fabric_timer_and_start()

    tgen_done = start_tgen_and_wait(num_words, timeout_ms=20)
    if not tgen_done:
        cycles = read_fabric_cycles_direct()
        print(
            f"[iter {iteration:02d}] TGEN TIMEOUT  "
            f"cycles={cycles} num_words={num_words}"
        )
        return None

    time.sleep(0.001)
    cycles = read_fabric_cycles_direct()

    if cycles <= 0:
        print(
            f"[iter {iteration:02d}] NO_DATA      "
            f"cycles={cycles} num_words={num_words}"
        )
        return None

    print(
        f"[iter {iteration:02d}] OK            "
        f"cycles={cycles} num_words={num_words}"
    )

    return int(cycles)


def summarize_cycles(label: str, cycles: list[int]):
    if not cycles:
        print(f"{label}: NO DATA")
        return
    avg = statistics.mean(cycles)
    mdn = statistics.median(cycles)
    mn = min(cycles)
    mx = max(cycles)
    stdev = statistics.stdev(cycles) if len(cycles) > 1 else 0.0
    to_ns = lambda c: c * 8.0  # 125 MHz
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
    Resolve IP physical base addresses from .hwh metadata.
    """
    global FABRIC_TIMER_ADDR, TGEN_CTRL_ADDR
    try:
        for k, v in ol.ip_dict.items():
            name = k.lower()
            if "latency_timer_0" in name and "s_axi_control" in name and "phys_addr" in v:
                FABRIC_TIMER_ADDR = v["phys_addr"]
            if ("traffic_gen_const" in name or "traffic_gen" in name) and "/s_axi_control" in name and "phys_addr" in v:
                TGEN_CTRL_ADDR = v["phys_addr"]
    except Exception:
        pass


def program_header_constants():
    """
    Program a zeroed header into traffic_gen_const so that the downstream
    width converter + mlp_core_stream see a stable, known pattern.

    Important: the 32->128b width converter packs **four** 32-bit words into
    one 128-bit beat, so we emit only 4 words per "packet".
    """
    header_words = build_zero_header_words32()
    if len(header_words) < 4:
        raise RuntimeError("Expected at least 4 header words")
    program_traffic_gen_const(header_words[:4])
    return 4


def main():
    print("Loading MLP core Overlay...")
    bitfile_path = Path(
        os.getenv("NFPGA_BITFILE_CORE", "/home/xilinx/feature_overlay_mlp_core.bit")
    )
    ol = Overlay(str(bitfile_path))

    resolve_ip_bases(ol)
    print(
        f"\nResolved addrs:"
        f" TIMER_FABRIC=0x{FABRIC_TIMER_ADDR:08X}"
        f" TGEN_CTRL=0x{TGEN_CTRL_ADDR:08X}"
    )

    num_words_for_header = program_header_constants()
    dump_regs("After header programming")

    N = 50  # iterations per configuration

    print("\n=== Experiment 1: num_words fixed (single-header) ===")
    fixed_num_words = num_words_for_header
    cycles = []
    for _ in range(N):
        c = run_fpga_once(num_words=fixed_num_words)
        if c is not None:
            cycles.append(c)
    summarize_cycles(f"num_words={fixed_num_words}", cycles)
    if not cycles:
        dump_regs("Experiment 1 - no data")

    print("\n=== Experiment 2: per-iteration trace (num_words=header) ===")
    N_trace = 20
    trace_cycles = []
    for i in range(N_trace):
        c = run_fpga_once_traced(num_words=fixed_num_words, iteration=i)
        if c is not None:
            trace_cycles.append(c)
    summarize_cycles(
        f"TRACE summary num_words={fixed_num_words}",
        trace_cycles,
    )


if __name__ == "__main__":
    main()


