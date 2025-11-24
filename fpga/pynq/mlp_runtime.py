#!/usr/bin/env python3
"""
MLP Score Capture Tool - Standalone utility for capturing raw MLP inference scores.

This script:
1. Programs MLP quantization scales from mlp_int8.json
2. Starts the MLP in auto-restart mode
3. Continuously drains scores from axi_dma_1 S2MM channel
4. Saves raw Q16.16 fixed-point scores to binary file

Use this for:
- Validating MLP inference output against CPU reference
- Collecting large score datasets for analysis
- Debugging MLP FIFO backpressure issues (must drain to prevent deadlock)

For integrated feature+score workflow, use feature_echo_mt.py instead.
"""
import argparse
import json
import struct
import time
from pathlib import Path

import numpy as np


def f32_to_u32(x: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def find_ip(ol, key_substr: str):
    # Find an IP by substring to be resilient to name suffixes
    matches = [k for k in ol.ip_dict.keys() if key_substr in k]
    if not matches:
        raise RuntimeError(f"Could not find IP containing '{key_substr}'. Available: {list(ol.ip_dict.keys())}")
    # Prefer exact match if present
    for k in matches:
        if k == key_substr:
            return getattr(ol, k)
    return getattr(ol, matches[0])


def program_scales(mlp_ip, spec_path: Path):
    spec = json.loads(Path(spec_path).read_text())
    # Expect fields: in_scale, w0_scale, act0_scale, w1_scale
    rm = mlp_ip.register_map
    vals = {
        "in_scale":   f32_to_u32(spec["in_scale"]),
        "w0_scale":   f32_to_u32(spec["w0_scale"]),
        "act0_scale": f32_to_u32(spec["act0_scale"]),
        "w1_scale":   f32_to_u32(spec["w1_scale"]),
    }
    # Robustly set via register_map if supported; otherwise use write() with offsets.
    for name, v in vals.items():
        try:
            setattr(rm, name, v)  # most Pynq versions support assignment
        except Exception:
            try:
                off = getattr(rm, name).offset
                mlp_ip.write(off, v)
            except Exception as e:
                raise RuntimeError(f"Failed to program '{name}': {e}")


def capture_scores(ol, dma_name: str, count_words: int, timeout_s: float, out_path: Path):
    from pynq import allocate
    dma = getattr(ol, dma_name)
    # Ensure S2MM is running (some images require explicit start for recvchannel)
    try:
        dma.recvchannel.stop()
    except Exception:
        pass
    try:
        dma.recvchannel.start()
    except Exception:
        pass
    # Give hardware a brief moment to enter running state
    time.sleep(0.001)
    # On some Pynq DMAs the maximum transfer is 16KB-1 (16383 bytes).
    # Use a conservative chunk of 4092 words (16368 bytes) per transfer.
    CHUNK_WORDS = min(4092, max(1, count_words))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    first_vals = None
    timeouts = 0
    errors = 0
    with open(out_path, "wb") as f:
        buf = allocate(shape=(CHUNK_WORDS,), dtype=np.uint32)
        while total < count_words:
            n_words = min(CHUNK_WORDS, count_words - total)
            view = buf[:n_words]
            # Be robust to sporadic "DMA channel not started"
            try:
                dma.recvchannel.transfer(view)
            except RuntimeError as e:
                if "not started" in str(e):
                    try:
                        dma.recvchannel.start()
                        time.sleep(0.001)
                        dma.recvchannel.transfer(view)
                    except Exception:
                        raise
                else:
                    raise
            # Poll S2MM DMASR for completion with timeout to avoid indefinite block.
            t0 = time.time()
            done = False
            while True:
                status = dma.recvchannel._mmio.read(0x34)  # S2MM_DMASR
                if (status & 0x1000) != 0:  # IOC_Irq
                    done = True
                    break
                if (status & 0x70) != 0:
                    # Error condition; break and attempt to continue.
                    errors += 1
                    break
                if time.time() - t0 > timeout_s:
                    timeouts += 1
                    break
                time.sleep(0.0005)
            try:
                if done:
                    dma.recvchannel.wait()
                else:
                    # Reset S2MM to clear stuck transfer on timeout/error
                    try:
                        dma.recvchannel._mmio.write(0x30, 0x4)
                        time.sleep(0.0005)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                view.invalidate()
            except Exception:
                pass
            b = memoryview(view).tobytes()
            f.write(b)
            if first_vals is None:
                arr = np.frombuffer(b[:min(32, len(b))], dtype="<u4").astype(np.int32)
                first_vals = (arr / float(1 << 16)).tolist()
            total += n_words
        # Free buffer by letting it go out of scope
    if first_vals is None:
        first_vals = []
    # Stop S2MM channel after capture
    try:
        dma.recvchannel.stop()
    except Exception:
        pass
    return first_vals, total, {"timeouts": timeouts, "errors": errors}


def main():
    ap = argparse.ArgumentParser(description="Configure MLP scales and capture scores via DMA on Pynq.")
    ap.add_argument("--bit", default="feature_overlay.bit", help="Bitstream to attach (will not reprogram if already loaded)")
    ap.add_argument("--spec", default="mlp_int8.json", help="Quantized model spec with scales")
    ap.add_argument("--count", type=int, default=65536, help="Number of 32-bit score words to capture")
    ap.add_argument("--timeout", type=float, default=5.0, help="Timeout (s) waiting for DMA capture")
    ap.add_argument("--out", default="scores.bin", help="Output binary of Q16.16 scores")
    ap.add_argument("--dma", default="axi_dma_1", help="DMA IP name for scores S2MM channel")
    args = ap.parse_args()

    from pynq import Overlay
    # Attach to the current overlay if already loaded; do not reprogram
    ol = Overlay(args.bit, download=False)
    try:
        mlp = find_ip(ol, "mlp_infer_0")
    except Exception:
        # Fall back to any IP containing 'mlp_infer'
        mlp = find_ip(ol, "mlp_infer")
    program_scales(mlp, Path(args.spec))
    # Start the core once; ap_ctrl_hs
    # ap_start is bit0; enable auto-restart (bit7) for streaming
    mlp.write(0x00, 0x81)
    # Capture from specified DMA (default axi_dma_1) S2MM
    dma_name = args.dma
    vals, n, stats = capture_scores(ol, dma_name, args.count, args.timeout, Path(args.out))
    print(f"Captured {n} words to {args.out}. First few (Q16.16): {vals}")
    if stats["timeouts"] or stats["errors"]:
        print(f"DMA stats: timeouts={stats['timeouts']} errors={stats['errors']}")


if __name__ == "__main__":
    main()


