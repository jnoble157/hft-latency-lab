# neuro-hft-fpga — Quick Start

This document keeps the **practical getting-started instructions** for the project.  
The main `README.md` is reserved for the evolving **paper-style narrative**.

---

## Project overview

Research project exploring **hardware-accelerated decision-making for high-frequency trading**.

Core idea: split decision logic into two parts —
- **Reflex lane**: hard-coded, deterministic reactions to order book events.  
- **Inference lane**: tiny quantized MLP on FPGA that scores order flow toxicity / edge.

Goal isn’t to beat Citadel. Goal is to **build a reproducible, open-source reference** for co-designing:
- market data features  
- hardware (FPGA) + software (CPU)  
- latency budgets and predictive models

This repo is the lab notebook + code + paper.

---

## Hardware I'm using

| Component        | Role                                       |
|------------------|--------------------------------------------|
| Ryzen 3800X CPU  | Feed replay, orchestration                 |
| Intel X710 NIC   | Kernel-bypass packet I/O (AF_XDP / DPDK)   |
| Pynq Z2 FPGA     | Feature compute + MLP scoring over 1GbE    |
| Radeon 6900XT    | Offline model training / simulation        |

---

## What this will deliver

- ✔ Minimal reproducible HFT datapath: packet in → decision out  
- ✔ FPGA pipeline for OFI, imbalance, burst detection, micro-volatility  
- ✔ Tiny quantized MLP in hardware (<200 LUT neurons)  
- ✔ Latency measurements at nanosecond precision  
- ✔ Whitepaper + code so others can build/extend

---

## Why this matters

Most HFT research lives in two worlds:
- Math papers that ignore hardware  
- FPGA papers that ignore markets  

This project lives in the gap: *what features are worth 100 ns of compute?*  
That’s the real HFT question.

---

## Quick Start (SoC benchmark — recommended)

This is the fastest way to reproduce the **ARM vs fabric** SoC results shown in `README.md`.

```bash
# 1. SSH into the Pynq
ssh xilinx@<PYNQ_IP>

# 2. Run the main SoC latency benchmark (CPU vs full FPGA lane)
cd ~/neuro-hft-fpga/fpga/pynq
python3 run_cycle_bench.py  # resolves IPs from .hwh and logs to soc_full.log / latency_comparison.csv

# 3. Run the diagnostic overlays to decompose fabric latency
python3 soc_latency_diag.py          # full overlay
python3 soc_latency_diag_mlp_only.py # MLP-only + DMA overlay
python3 soc_latency_diag_nodma.py    # no-DMA overlay
python3 soc_latency_diag_core.py     # core-probe overlay

# 4. Copy logs back to your host under latency_analysis/
exit
scp xilinx@<PYNQ_IP>:/home/xilinx/neuro-hft-fpga/latency_analysis/soc_*.log \
    /path/to/host/neuro-hft-fpga/latency_analysis/
scp xilinx@<PYNQ_IP>:/home/xilinx/neuro-hft-fpga/latency_analysis/latency_comparison.csv \
    /path/to/host/neuro-hft-fpga/latency_analysis/

# 5. On the host, regenerate all SoC plots and summary CSVs
cd /path/to/host/neuro-hft-fpga
python3 latency_analysis/analyze_soc.py
```

If everything is wired correctly, you should see:
- Updated PNGs under `latency_analysis/plots/` matching the figures in `README.md`.
- A refreshed `latency_analysis/soc_summaries.csv` with per-overlay statistics.

---

## Quick Start (host ↔ FPGA over Ethernet — legacy path)

This path exercises the original “packet in → decision out” design over 1GbE. It is useful context, but the SoC benchmark above is the centerpiece of the current writeup.

```bash
# 1. Deploy overlay to Pynq
make deploy PYNQ_IP=192.168.10.2

# 2. Run end-to-end validation
make validate PYNQ_IP=192.168.10.2

# 3. Measure latency at 100 Hz
cd host/udp && ./run_latency_tests.sh
```

---

## Repo Structure

```text
├── docs/             # Phase-organized engineering notes + paper scaffold
├── host/             # Feed handler, replay, latency analysis
├── fpga/             # HLS feature pipeline + Vivado overlays + Pynq scripts
├── models/           # MLP training, quantization, BRAM exports
├── protocol/         # UDP wire format (LOB_v1)
├── infra/            # System tuning, DPDK, PTP scripts
├── tests/            # Validation and smoke tests
├── sample_data/      # LOBSTER sample files
└── latency_analysis/ # Measured latency results
```

---

## License

MIT. Use it, break it, improve it.


