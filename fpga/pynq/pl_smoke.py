#!/usr/bin/env python3
"""
DMA Smoke Test - Low-level diagnostic tool for FPGA feature pipeline.

This script directly manipulates DMA registers and tests single-packet transfers.
Use this for:
- Diagnosing DMA channel issues (hangs, timeouts, invalid states)
- Validating feature pipeline output at the register level
- Understanding bare-metal DMA control patterns

For production workloads, use feature_echo_mt.py instead.
"""
from pynq import Overlay, allocate
import numpy as np
import struct, time

# Ensure /home/xilinx/feature_overlay.bit and .hwh are present
ol = Overlay("/home/xilinx/feature_overlay.bit")
ol.download()  # reprogram to clear any prior DMA/IP state

dma_in  = ol.axi_dma_0.sendchannel   # MM2S
dma_out = ol.axi_dma_0.recvchannel   # S2MM

def d32(x): 
    return hex(x & 0xFFFFFFFF)

def dump_dma_regs(tag):
    mm2s_dmacr = dma_in._mmio.read(0x00)
    mm2s_dmasr = dma_in._mmio.read(0x04)
    s2mm_dmacr = dma_out._mmio.read(0x30)
    s2mm_dmasr = dma_out._mmio.read(0x34)
    print(f"{tag} MM2S_DMACR={d32(mm2s_dmacr)} MM2S_DMASR={d32(mm2s_dmasr)}  S2MM_DMACR={d32(s2mm_dmacr)} S2MM_DMASR={d32(s2mm_dmasr)}")

def reset_dma_channels():
    # Issue reset to both channels (bit 2 = Reset)
    dma_in._mmio.write(0x00, 0x4)
    dma_out._mmio.write(0x30, 0x4)
    # Wait briefly for reset to clear
    for _ in range(1000):
        if (dma_in._mmio.read(0x00) & 0x4) == 0 and (dma_out._mmio.read(0x30) & 0x4) == 0:
            break
        time.sleep(0.001)
    dump_dma_regs("After reset")

FEAT_LEN = 16  # HLS emits exactly one 16-byte feature per packet

def build_hdr(delta_cnt, seq):
    magic      = b"LOB1"
    ver        = 1
    msg_type   = 1
    flags      = (delta_cnt << 1)
    hdr_len    = 32
    t_send_ns  = 123456789 + seq
    t_ing_ns   = 0
    rsv2       = 0
    return struct.pack(">4sBBHHIQQH",
                       magic, ver, msg_type, flags, hdr_len,
                       seq, t_send_ns, t_ing_ns, rsv2)

def build_delta():
    return struct.pack(">iiHBBI", 0, 1, 0, 0, 1, 0)

def do_xfer(payload, label):
    in_buf  = allocate(shape=(len(payload),), dtype="u1")
    # Expect 16B feature from HLS one-shot; arm S2MM for 16 bytes
    out_len = FEAT_LEN
    out_buf = allocate(shape=(FEAT_LEN,), dtype="u1")
    in_buf[:] = np.frombuffer(payload, dtype=np.uint8)
    in_buf.flush()

    print(f"=== {label} (in={len(payload)} bytes) ===")
    dump_dma_regs("Before reset")
    reset_dma_channels()
    dump_dma_regs("Before xfer")
    try:
        dma_out.start()
        dma_in.start()
    except AttributeError:
        dma_out._mmio.write(0x30, dma_out._mmio.read(0x30) | 0x1)
        dma_in._mmio.write(0x00, dma_in._mmio.read(0x00) | 0x1)
    dump_dma_regs("After start")

    dma_out.transfer(out_buf)
    # For the one-shot test, we don't need to send anything; still issue MM2S to keep previous path working if payload is non-empty
    if len(payload) > 0:
        dma_in.transfer(in_buf)

    mm2s_length = dma_in._mmio.read(0x28)
    s2mm_length = dma_out._mmio.read(0x58)
    print(f"LENGTH MM2S=0x{mm2s_length:x} S2MM=0x{s2mm_length:x}")
    start = time.time()
    timeout_s = 1.0
    completed = False
    while time.time() - start < timeout_s:
        s2mm_dmasr = dma_out._mmio.read(0x34)
        mm2s_dmasr = dma_in._mmio.read(0x04)
        if (s2mm_dmasr & (1 << 12)) != 0:
            completed = True
            break
        if (s2mm_dmasr & 0x000070) != 0 or (mm2s_dmasr & 0x000070) != 0:
            print("DMA error detected during transfer")
            break
        time.sleep(0.005)
    dump_dma_regs("After xfer")
    if completed:
        dma_out.wait()
        if len(payload) > 0:
            dma_in.wait()
        out_buf.invalidate()
        data = bytes(out_buf[:FEAT_LEN])
        print("S2MM 16B feature:", data.hex())
    else:
        print("Timeout waiting for S2MM completion")

# Single test: header only (delta_cnt=0). This avoids any risk of parser over-read.
hdr = build_hdr(delta_cnt=0, seq=1)
payload = hdr
do_xfer(payload, "pkt: delta_cnt=0 (header only)")
