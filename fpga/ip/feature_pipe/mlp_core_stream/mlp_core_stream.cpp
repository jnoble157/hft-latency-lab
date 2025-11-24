// Minimal streaming MLP "core" used to probe control/stream overhead.
// This IP is NOT meant to be a production-accurate model; it is a
// latency probe with an ap_ctrl_none top and no AXI-Lite in the hot path.
//
// Interfaces:
//   - s_axis_feat  : 128-bit AXIS, one feature beat per inference
//   - m_axis_score : 32-bit AXIS, one score beat per inference
//   - done_pulse   : single-bit strobe for latency_timer stop_trigger
//
// For now the "MLP" is a tiny placeholder that just forwards some bits
// from the input to the output to exercise the pipeline. The point of
// this IP is to measure how much latency remains when we remove AXI-Lite
// control and DMA from the path, not to compute a real score.

#include "ap_int.h"
#include "ap_axi_sdata.h"
#include "hls_stream.h"

typedef ap_axiu<128,0,0,0> axis128_t;
typedef ap_axiu<32,0,0,0>  axis32_t;

void mlp_core_stream(hls::stream<axis128_t> &s_axis_feat,
                     hls::stream<axis32_t>  &m_axis_score,
                     bool                   &done_pulse) {
#pragma HLS INTERFACE axis     port=s_axis_feat
#pragma HLS INTERFACE axis     port=m_axis_score
#pragma HLS INTERFACE ap_none  port=done_pulse
#pragma HLS INTERFACE ap_ctrl_none port=return

    done_pulse = false;

    if (s_axis_feat.empty()) {
        return;
    }

    // Consume one 128-bit feature beat.
    axis128_t inw = s_axis_feat.read();
    ap_uint<128> din = inw.data;

    // Placeholder "compute": fold the 128-bit input down to a 32-bit word.
    // This keeps a bit of logic in the core so that synthesis doesn't
    // optimize it away, but the depth is tiny compared to the surrounding
    // stream/control overhead we are trying to measure.
    ap_uint<32> acc = 0;
    for (int i = 0; i < 4; ++i) {
#pragma HLS UNROLL
        acc ^= din.range((i + 1) * 32 - 1, i * 32);
    }

    axis32_t outw;
    outw.data = acc;
    outw.keep = 0xF;
    outw.strb = 0xF;
    outw.last = inw.last;
    m_axis_score.write(outw);

    // One-cycle completion strobe for latency measurement.
    done_pulse = true;
}


