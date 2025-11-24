## Traffic Generator & Timer IPs

This directory contains HLS IPs used exclusively for benchmarking and latency studies.

- `traffic_gen_const.cpp`, `build_traffic_gen_const.tcl`
  - Top: `traffic_gen_const`
  - Role: Constant‑pattern AXI‑Stream traffic generator with AXI‑Lite control and no DDR dependency.
  - Used as the packet source in the Phase 6 SoC latency benchmark.

- `latency_timer.cpp`, `build_timer.tcl`
  - Top: `latency_timer`
  - Role: Free‑running cycle counter with AXI‑Lite control, gated by `start_trigger` and `stop_trigger`.

- `traffic_gen.cpp`, `build_traffic_gen.tcl` (**legacy**)
  - Older DDR‑backed traffic generator with an `m_axi` port; superseded by `traffic_gen_const` in current designs.

HLS out‑of‑context project directories (e.g., `hls_*`) live alongside these sources and are ignored by `.gitignore`.


