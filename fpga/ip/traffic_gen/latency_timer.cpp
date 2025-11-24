#include "ap_int.h"
#include <stdint.h>

void latency_timer(
    bool start_trigger,     // Connected to traffic_gen start
    bool stop_trigger,      // Connected to MLP done/interrupt
    volatile uint32_t *cycle_count,
    bool reset
) {
#pragma HLS INTERFACE ap_none   port=start_trigger
#pragma HLS INTERFACE ap_none   port=stop_trigger
#pragma HLS INTERFACE s_axilite port=cycle_count bundle=control
#pragma HLS INTERFACE s_axilite port=reset       bundle=control
// Free-running block: no ap_start/ap_done handshaking.
#pragma HLS INTERFACE ap_ctrl_none port=return

    static uint32_t counter = 0;
    static bool running = false;

    if (reset) {
        counter = 0;
        running = false;
        *cycle_count = 0;
        return;
    }

    // Start logic
    if (start_trigger && !running) {
        running = true;
    }

    // Stop logic
    if (stop_trigger && running) {
        running = false;
    }

    // Count
    if (running) {
        counter++;
    }

    *cycle_count = counter;
}

