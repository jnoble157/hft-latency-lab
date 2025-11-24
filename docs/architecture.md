# System Architecture

Goal: process live (or replayed) limit-order-book updates, extract features, score toxicity on FPGA, and produce a trading decision — all under a hard latency budget.

This document explains **how bytes and cycles move through the system**. For the paper-style narrative and measured SoC results, see `README.md`. For commands to reproduce experiments, see `docs/quickstart.md`.

---

## Data Flow

- **Original host/NIC/FPGA path** (Phase 0–4):
  - `exchange/pcap → X710 NIC → host (DPDK/AF_XDP) → compact LOB over UDP @1GbE → FPGA (Pynq Z2)`.
  - On the FPGA: `parser → feature pipeline → MLP → decision`.
  - Back to host: merge reflex + FPGA decision → (simulated order) → evaluation/logging.
  - No PCIe to FPGA. Everything is Ethernet. Latency is measured, not assumed.

- **SoC-only path** (Phase 5/6 pivot, current focus):
  - Inside Pynq: `TrafficGen → Feature Pipeline → MLP → Latency Timer`.
  - The ARM core runs the reflex lane; the PL runs the MLP lane.
  - On-chip timers measure **ARM vs fabric** directly, with no NIC/RTT in the loop.

---

## Two-Lane Brain

| Lane        | Runs on | Purpose                          |
|-------------|---------|----------------------------------|
| Reflex      | CPU     | Hard-coded rules (queue drop, burst cancel, cross) |
| Inference   | FPGA    | Quantized MLP scoring flow toxicity / edge |

Host decides: trust reflex, trust FPGA score, or ignore both.

---

## Feature Pipeline (FPGA)

All fixed-point. Single-cycle or pipelined.

- Order Flow Imbalance (Δbid - Δask)
- Top-of-book imbalance
- EWMA micro-volatility
- Burst detector (updates/time window)
- Optional: queue aging, lead/lag flag

Outputs → small MLP.

---

## Quantized MLP

Why: ML without GPUs in the hot path. Low compute, deterministic latency.

- Inputs: normalized features
- Hidden: 16–32 neurons (ReLU/Linear)
- Output: scalar score (toxicity / alpha sign)
- Weights: 8–12 bit fixed-point, loaded from BRAM
- Training is offline (PyTorch → quantized → BRAM dump)

In the current SoC design the MLP is split into two IP blocks:

- `mlp_infer_stream_0`: pure AXI-Stream compute core with **static on-chip weights** and AXI-Lite control (reload flag, scaling, optional delay).  
- `weight_loader_0`: AXI master that streams weights once from DDR into `mlp_infer_stream_0` when models are updated (hot swap).

---

## Timing Budget (goal, not promise)

For the **host/NIC/FPGA** path, a rough latency budget is:

| Stage               | Target                          |
|---------------------|---------------------------------|
| RX host timestamp   | ~1 µs (X710→userspace)         |
| Host → FPGA UDP send| ~5–10 µs                       |
| FPGA pipeline       | 0.5–1.0 µs                     |
| FPGA → Host return  | ~5–10 µs                       |

This is slow vs real HFT, but measurable and improvable. Publish the numbers.

For the **SoC-only benchmark** (Phase 5/6 pivot), Ethernet is removed and we time:

- **Reflex lane (ARM):** Python/C logic on Cortex-A9.  
- **Neuro lane (FPGA):** `TrafficGen → Feature Pipeline → MLP → Latency Timer`.  

This isolates architectural latency and jitter, independent of NIC/RTT.

---

## Why Ethernet between host and FPGA?

- Pynq Z2 has no PCIe
- Ethernet forces clean serialization and timestamping
- Reproducible by anyone with $100 board

---

## Future upgrade path

- Swap Pynq for PCIe SmartNIC / VCU118
- Push reflex lane to hardware
- Add actual exchange connectivity

First: make it work. Then: make it fast.
