# neuro-hft-fpga

> A lab notebook on putting a tiny MLP into an FPGA datapath and counting the cycles honestly.

---

## I. What this is

The goal is a **minimal, measurable HFT datapath** that touches real hardware instead of just Python backtests.

- **Two-lane brain**:
  - **Reflex lane (CPU)**: hard-coded rules on a normal CPU (and later on the Pynq ARM).
  - **Inference lane (FPGA)**: a tiny quantized MLP running on a Pynq-Z2 fabric.
- **Original goal**: packet in → features → MLP → decision → packet out, with timestamps at every stage.
- **Current focus**: a **System-on-Chip (SoC) benchmark** on the Pynq itself:
  - Compare **ARM reflex** vs **fabric MLP lane** on the same chip.
  - Measure where the time actually goes: math vs AXI vs DMA vs glue.

In practice this turns into a **64‑cycle MLP** sitting inside a **~140k‑cycle shell**, with the ARM reflex lane about **100× faster** than the FPGA lane.

The repo is the code, bitstreams, and plots for that experiment.

---

## II. How it works

There are two views: the original host↔FPGA design, and the SoC-only benchmark that everything pivots to.

### 2.1 Host ↔ FPGA path (original setup)

High level:

- `exchange/pcap → X710 NIC → host (DPDK/AF_XDP)`.
- Host converts packets into a **compact LOB** format and sends them over UDP to the Pynq-Z2.
- On the Pynq:
  - `parser → feature_pipeline → mlp_infer_stream → score`.
- Scores go back over UDP; host merges **reflex + FPGA** into simulated orders and logs everything.

This is still in the repo, but it’s not where the interesting latency story ends up.

### 2.2 SoC-only path (current focus)

For the SoC benchmark, Ethernet disappears. Everything happens **inside** the Pynq:

- **Reflex lane (ARM)**:
  - Python/C logic on the Cortex‑A9.
  - Implements simple queue-drop / cancel-storm style rules.
- **Neuro lane (FPGA)**:
  - `traffic_gen_const_0`: synthesizes a stream of toy LOB headers.
  - `feature_pipeline_0`: computes OFI, imbalance, burst, micro-volatility, etc.
  - `mlp_infer_stream_0`: small quantized MLP (4→32→1-ish), weights cached in BRAM.
  - `latency_timer_*`: on-chip timers gating `hw_start` to various done pulses.

To understand where the cycles go, the Vivado design is split into four overlays:

- **Full**: `TrafficGen → Features → MLP → S2MM DMA → ARM`.
- **MLP‑only**: `TrafficGen → width converter → MLP → S2MM DMA → ARM`.
- **No‑DMA**: `TrafficGen → width converter → MLP → on-chip score sink` (pure fabric, no DMA in the hot path).
- **Core probe**: `TrafficGen → width converter → trivial streaming core → score sink`.

On the Pynq, a small set of Python scripts in `fpga/pynq/` drive everything:

- `run_cycle_bench.py`: ARM reflex vs full FPGA lane (SoC CDFs).
- `soc_latency_diag*.py`: low-level sweeps for each overlay, dumping per-iteration traces.

Logs and comparison CSVs land under `latency_analysis/`, and `latency_analysis/analyze_soc.py` turns them into plots.

---

## III. Results

All numbers below are for Pynq-Z2 fabric at **125 MHz**, measured with on-chip timers.

### 3.1 Headline

- The **MLP math** is tiny: about **64 cycles ≈ 0.5 µs**.
- The **fabric shell** (traffic generator, width converters, AXI, control) is huge:
  - **≈140k cycles ≈ 1.0–1.3 ms** even with DMA removed.
- With DMA in the path, the FPGA lane goes to **~3.4–3.6 ms**.
- The **ARM reflex lane** on the same chip is **~16–20 µs**.

So on this SoC, the **CPU is ~100× faster** than the FPGA lane for this workload.  
The point of the project is to **explain that in cycles**, not to pretend the FPGA “wins”.

### 3.2 CPU vs FPGA CDFs

From `run_cycle_bench.py` and the full overlay:

- ARM reflex: p50 ≈ **17 µs**, p99 ≈ **39 µs**.
- Full FPGA lane (features + MLP + DMA): p50 ≈ **1.35 ms**, p99 ≈ **2.2 ms**.

See `latency_analysis/plots/cdf_cpu_vs_fpga.png` for the full distributions.

### 3.3 Fabric breakdown by overlay

Using the four overlays with `delay_cycles=0`, `num_words=4`:

- **Core probe** (minimal streaming core): ≈ **2.2 ms**.
- **No‑DMA** (fabric only): ≈ **1.1 ms**.
- **MLP‑only** (DMA): ≈ **3.4 ms**.
- **Full** (features + MLP + DMA): ≈ **3.7 ms**.

Plots:

- `latency_analysis/plots/soc_overlay_bar_avg_latency.png` — average fabric latency by overlay.
- `latency_analysis/plots/soc_nodma_stacked_overhead.png` — stacked view inside the no‑DMA overlay.

Reading those plots together: the **MLP core is basically free**, the **shell dominates**, and **DMA is expensive** even at 1 GbE / low rate.

---

## IV. Why is the FPGA logic latency so high?

Short answer: this is a **Zynq SoC with a generic AXI shell**, not a stripped-down trading NIC. The math is cheap; the infrastructure is not.

### 4.1 What the measurements say

From the no‑DMA overlay:

- Internal MLP counter (`mlp_dbg_iters`): **64 cycles**.
- Fabric timer from `hw_start` to `score_sink` done: **≈140k cycles**.

The core-probe overlay replaces the real MLP with a trivial streaming core and still measures **O(10⁵) cycles**. That pins most of the cost on:

- AXI interconnect and handshaking.
- Width converters and register slices.
- PL/PS boundary and control glue.

In other words: the “empty” shell is already slow.

### 4.2 Constraints and quirks of the Pynq-Z2 setup

Some of this is just the board and the way Zynq SoCs are normally used:

- **Fabric clock**: 125 MHz is modest. Even a 1k-cycle shell would still be ~8 µs; this design sits at O(10⁵) cycles instead.
- **Generic AXI infrastructure**:
  - Xilinx IPs (DMA, dwidth converters, FIFOs) are built for flexibility, not single-digit microseconds.
  - Every boundary adds buffering, back-pressure logic, and sometimes clock conversion.
- **PS/PL boundary**:
  - Traffic ultimately lands in ARM DDR via S2MM DMA and the AXI HP ports.
  - Transactions fight with everything else in the SoC (caches, other masters).
- **Software control path**:
  - Python on ARM, talking over AXI-Lite, is easy to script but not what you’d run in a trading card shell.

None of these are “bugs”. They’re just what happens when you take a teaching board and wire it up with off-the-shelf IP instead of a hand-rolled shell.

### 4.3 How this compares to real HFT hardware

Modern HFT setups don’t look like “Pynq over 1 GbE”.

Rough contrasts:

- **Fabric and I/O**:
  - NIC/FPGA cards (UltraScale+, Agilex, etc.) run cores **~400–800 MHz**, often with hardened MACs and PHYs.
  - You get direct access to line-rate packets and low-jitter clocks, not a PS/PL bridge.
- **Shell design philosophy**:
  - Real designs collapse the shell into a **thin streaming pipeline**: MAC → parser → features → model → egress.
  - No generic S2MM DMA in the hot path; no unnecessary width converters; minimal FIFOs.
- **Control**:
  - Slow controls (weight updates, config) are pushed to a sideband path or microcontroller.
  - The hot path is just combinational + small state machines.

If you ported the **cycle counts** from this project straight to 400–800 MHz silicon, you’d already move from milliseconds into **hundreds of microseconds**:

- 64-cycle MLP @ 800 MHz ≈ **80 ns**.
- 140k-cycle shell @ 800 MHz ≈ **175 µs**.

But a serious design would also **cut the shell** by 1–2 orders of magnitude. A 10k-cycle shell at 600 MHz is ~17 µs. That’s the regime real NICs play in.

The point of this repo is not to build that NIC; it’s to make the cycle budget obvious enough that you can reason about what that NIC has to look like.

---

## V. Concluding thoughts

- A **64‑cycle MLP** can easily drown inside a **100k+ cycle shell** if you’re not disciplined about the datapath.
- SoC boards like Pynq-Z2 are great for learning and measurement, but they are **architecture-limited**, not compute-limited.
- The interesting work is not shaving a few cycles off the MLP; it’s **designing shells and control paths** that earn their keep in cycles.
- If you want to reproduce the plots or poke at the scripts, start with `docs/quickstart.md` and `latency_analysis/analyze_soc.py`, then read `fpga/pynq/soc_latency_diag*.py` and the HLS IP in `fpga/ip/feature_pipe`.

The rest of the repo is just code to keep myself honest.


