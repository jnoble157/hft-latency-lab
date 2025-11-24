## Feature Pipe IPs

This directory groups all HLS IP blocks that implement the limit‑order‑book feature extraction and MLP inference path.

- `feature_pipeline.cpp`, `feature_pipeline.hpp`, `tb_feature_pipeline.cpp`, `hls.tcl`
  - Top: `feature_pipeline`
  - Role: Convert 32‑byte LOB v1 headers into a single 16‑byte feature vector on a 128‑bit AXI‑Stream.

- `mlp_infer_stream/`
  - Top: `mlp_infer_stream`
  - Role: Quantized 2‑layer MLP (4→8→1) with **static on‑chip weights** and AXI‑Stream feature/score ports.
  - HLS entry: `mlp_infer_stream.cpp`, `hls.tcl`.

- `weight_loader/`
  - Top: `weight_loader`
  - Role: One‑shot DDR → AXIS streamer that loads W0/B0/W1/B1 into `mlp_infer_stream` when `reload_weights` is asserted.

- `mlp_infer/` (**legacy**)
  - Phase 3 monolithic MLP IP with BRAM weight ports and no split loader.
  - Kept for reproducibility of earlier experiments; not used in the current Phase 6+ overlay.


