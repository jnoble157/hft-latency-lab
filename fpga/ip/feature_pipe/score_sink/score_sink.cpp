// Simple AXIS score sink used for "no-DMA" latency experiments.
// - Consumes one 32-bit score word from AXIS.
// - Asserts a one-cycle done_pulse when TLAST is seen.
// - No AXI-Lite or m_axi ports; purely stream+strobe.
//
// Intended BD wiring:
//   mlp_infer_stream_0/m_axis_score -> score_sink_0/s_axis_score
//   traffic_gen_const_0/hw_start    -> latency_timer_0/start_trigger
//   score_sink_0/done_pulse        -> latency_timer_0/stop_trigger
//
// This lets latency_timer_0 measure end-to-end fabric latency without DMA.

#include "ap_int.h"
#include "ap_axi_sdata.h"
#include "hls_stream.h"

typedef ap_axiu<32,0,0,0> axis32_t;

void score_sink(hls::stream<axis32_t> &s_axis_score,
                bool                   &done_pulse) {
#pragma HLS INTERFACE axis     port=s_axis_score
#pragma HLS INTERFACE ap_none  port=done_pulse
#pragma HLS INTERFACE ap_ctrl_none port=return

    done_pulse = false;

    if (!s_axis_score.empty()) {
        axis32_t w = s_axis_score.read();
        (void)w;  // data is ignored
        if (w.last) {
            // One-cycle pulse when we consume the last word of a score.
            done_pulse = true;
        }
    }
}


