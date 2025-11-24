#include "feature_pipeline.hpp"
#include <cstdio>

int main() {
    hls::stream<axis_t> in, out;
    hls::stream<features_t> feat;
    
    // Build a minimal frame: 32B header (4 beats) + 16B one delta (2 beats)
    axis_t w;
    for (int i = 0; i < 4; i++) {
        w.data = 0; w.keep = 0xFF; w.last = 0; in.write(w);
        feature_pipeline(in, out, feat);
    }
    for (int i = 0; i < 2; i++) {
        w.data = 0; w.keep = 0xFF; w.last = (i == 1); in.write(w);
        feature_pipeline(in, out, feat);
    }
    // Drain one feature if produced
    if (!feat.empty()) {
        features_t f = feat.read();
        printf("ofi=%d imb=%d burst=%u vol=%u\n",
               (int)f.ofi_q32, (int)f.tob_imb_q1_15, (unsigned)f.burst_q16_16, (unsigned)f.vol_q16_16);
    }
    return 0;
}


