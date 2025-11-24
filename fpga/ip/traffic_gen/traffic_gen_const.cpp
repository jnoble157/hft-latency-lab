#include "ap_int.h"
#include "hls_stream.h"
#include "ap_axi_sdata.h"
#include <stdint.h>

// AXI Stream Interface (32-bit data)
typedef ap_axis<32, 2, 5, 6> axis_t;

// Constant-only Traffic Generator
// - No m_axi ports
// - One AXI4-Stream output
// - One AXI4-Lite control port ("control" bundle)
//
// Ports:
//   num_words : number of 32-bit words to emit
//   start     : software start flag (latched by HLS wrapper into start_r)
//   tx_stream : AXI4-Stream out
//   done      : status bit (mirrored into AXI-Lite)
//   hw_start  : single-bit pulse to start external latency_timer
//   last_pulse: single-bit flag asserted when the last word is emitted
//   w_const0-3: 4 constant words used in round-robin order
//
void traffic_gen_const(
    uint32_t              num_words,
    bool                  start,
    hls::stream<axis_t>  &tx_stream,
    volatile bool        *done,
    volatile bool        *hw_start,
    volatile bool        *last_pulse,
    uint32_t              w_const0,
    uint32_t              w_const1,
    uint32_t              w_const2,
    uint32_t              w_const3
) {
#pragma HLS INTERFACE s_axilite port=num_words bundle=control
#pragma HLS INTERFACE s_axilite port=start     bundle=control
#pragma HLS INTERFACE s_axilite port=done      bundle=control
#pragma HLS INTERFACE ap_none   port=hw_start
#pragma HLS INTERFACE ap_none   port=last_pulse
#pragma HLS INTERFACE axis      port=tx_stream
#pragma HLS INTERFACE s_axilite port=return    bundle=control
#pragma HLS INTERFACE s_axilite port=w_const0  bundle=control
#pragma HLS INTERFACE s_axilite port=w_const1  bundle=control
#pragma HLS INTERFACE s_axilite port=w_const2  bundle=control
#pragma HLS INTERFACE s_axilite port=w_const3  bundle=control

    *done       = false;
    *hw_start   = false;
    *last_pulse = false;

    if (!start) {
        return;
    }

    // One-cycle strobe to external timer
    *hw_start = true;

    // Emit num_words 32-bit words, cycling through the 4 constants
    for (uint32_t i = 0; i < num_words; ++i) {
#pragma HLS PIPELINE II=1
        axis_t temp;
        switch (i & 3U) {
            case 0: temp.data = w_const0; break;
            case 1: temp.data = w_const1; break;
            case 2: temp.data = w_const2; break;
            default: temp.data = w_const3; break;
        }
        temp.keep = 0xF;
        temp.strb = 0xF;
        temp.user = 0;
        temp.id   = 0;
        temp.dest = 0;
        bool is_last = (i == (num_words - 1));
        temp.last = is_last ? 1 : 0;
        tx_stream.write(temp);
        if (is_last) {
            // Flag last-beat emission for an external latency_timer
            *last_pulse = true;
        }
    }

    *done = true;
}


