## `mlp_infer_stream` (Streaming MLP Core)

- **Top function**: `mlp_infer_stream`
- **Role**: 2‑layer quantized MLP (4 inputs → 8 hidden (ReLU) → 1 output) for order‑book features.
- **Interfaces**:
  - AXI‑Stream `s_axis_feat` (128‑bit) — single 16‑byte feature beat.
  - AXI‑Stream `m_axis_score` (32‑bit) — single 32‑bit score (Q16.16).
  - AXI‑Lite control — `reload_weights`, `delay_cycles`, size registers.
  - AXI‑Stream weight input from `weight_loader` during reload.

### Rebuild

```bash
cd fpga/ip/feature_pipe/mlp_infer_stream
vitis_hls -f hls.tcl
```


