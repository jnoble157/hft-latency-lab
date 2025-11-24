## `weight_loader` (DDR → Stream Weight Loader)

- **Top function**: `weight_loader`
- **Role**: Reads W0/B0/W1/B1 from DDR via `m_axi` and streams them over AXI‑Stream into `mlp_infer_stream` when `reload_weights` is enabled.
- **Interfaces**:
  - `m_axi` master for DDR reads.
  - AXI‑Stream output carrying quantized weights/biases.
  - AXI‑Lite control + pointer windows for buffer addresses and sizes.

### Rebuild

```bash
cd fpga/ip/feature_pipe/weight_loader
vitis_hls -f hls.tcl
```


