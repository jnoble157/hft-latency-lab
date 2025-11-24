#include "ap_int.h"
#include "hls_stream.h"
#include "ap_axi_sdata.h"
#include <stdint.h>

// AXI Stream Interface
typedef ap_axis<32, 2, 5, 6> axis_t;

// Minimal Traffic Generator
// Removed m_axi/bram_ptr completely to avoid unmapped master hangs.
// Purely generates traffic from register-based constants.

void traffic_gen(
    uint32_t num_words,      // How many 32-bit words to send
    bool start,              // Trigger signal
    hls::stream<axis_t> &tx_stream, // Output stream to Feature Pipe
    volatile bool *done,     // Done register
    volatile bool *hw_start, // Hardware strobe for timer
    uint32_t w_const0,       // Constant word 0
    uint32_t w_const1,       // Constant word 1
    uint32_t w_const2,       // Constant word 2
    uint32_t w_const3        // Constant word 3
) {
#pragma HLS INTERFACE s_axilite port=num_words bundle=control
#pragma HLS INTERFACE s_axilite port=start bundle=control
#pragma HLS INTERFACE s_axilite port=done bundle=control
#pragma HLS INTERFACE ap_none port=hw_start
#pragma HLS INTERFACE axis port=tx_stream
#pragma HLS INTERFACE s_axilite port=return bundle=control
// Constants mapped to AXI-Lite
#pragma HLS INTERFACE s_axilite port=w_const0 bundle=control
#pragma HLS INTERFACE s_axilite port=w_const1 bundle=control
#pragma HLS INTERFACE s_axilite port=w_const2 bundle=control
#pragma HLS INTERFACE s_axilite port=w_const3 bundle=control

    *done = false;
    *hw_start = false;

    if (!start) {
        return;
    }

    *hw_start = true; // Strobe logic start

    // Stream out constants
    for (int i = 0; i < num_words; i++) {
#pragma HLS PIPELINE II=1
        axis_t temp;
        
        // Map i -> const word (repeat pattern if num_words > 4)
        switch (i & 3) {
            case 0: temp.data = w_const0; break;
            case 1: temp.data = w_const1; break;
            case 2: temp.data = w_const2; break;
            case 3: temp.data = w_const3; break;
        }
        
        // AXI Stream Sideband signals
        temp.keep = 0xF; // All bytes valid
        temp.strb = 0xF;
        temp.user = 0;
        temp.id = 0;
        temp.dest = 0;
        
        // TLAST on final word
        temp.last = (i == num_words - 1) ? 1 : 0;
        
        tx_stream.write(temp);
    }

    *done = true;
}
