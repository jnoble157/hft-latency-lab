# cursor-agent-context

This repo is a research project, not production software.

It’s a **latency lab notebook**: a minimal HFT-style datapath with a tiny quantized MLP on a Pynq-Z2, a reflex lane on CPU/ARM, and enough instrumentation to see exactly where cycles go (math vs AXI/DMA vs control). Everything is open-source, reproducible, and latency-aware.

## Core principles

- **Every line must earn its keep.** No enterprise abstractions, no frameworks unless they save time and keep things transparent.
- **Measure > assume.** If it affects latency, timestamp it. If it affects accuracy, log it.
- **Simple > clever.** Clear C, Python, and Verilog over over-engineered “solutions”.
- **Composable pieces.** Small modules: feed handler, FPGA pipeline, training scripts, test harness.
- **Reproducible.** Anyone with a PC + X710 NIC + Pynq FPGA should be able to clone, build, and test.

## What you (the agent) should help with

- Writing clean C/C++ (DPDK), Python (training, backtesting), and Verilog/HLS (FPGA modules).
- Generating scaffolding: UDP packet structs, feature extraction blocks, testing harnesses.
- Keeping things minimal: no unnecessary classes, no build systems from hell.
- Explaining decisions briefly when useful (latency, memory, determinism), otherwise stay out of the way.

## What not to do

- Don’t introduce frameworks unless asked (no gRPC, no Kubernetes, no “microservices”).
- Don’t hide the data path behind abstractions. We care about bytes-on-wire and cycles-per-decision.
- Don’t assume unlimited hardware. FPGA = Pynq Z2 (Zynq-7020), CPU = Ryzen, GPU = Radeon.

## Project structure (expected)

/host - userspace feed handler, reflex logic, replay tools
/fpga - verilog/hls: parser → features → snn → action
/models - tiny neural nets, training, quantization
/protocol - packet formats sent over Ethernet to FPGA
/tests - replay, correctness, bit-accurate checks
/paper - whitepaper, experiments, plots


## Style

Think George Hotz or Andrej Karpathy:
- direct, minimal, hackable
- prefer readability over cleverness

---

That’s it. Help me build, don’t overthink it.
