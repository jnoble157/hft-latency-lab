#pragma once
#include <ap_int.h>
#include <hls_stream.h>
#include <ap_axi_sdata.h>

// AXIS types
typedef ap_axiu<64,0,0,0>  axis64_t;
typedef ap_axiu<128,0,0,0> axis128_t;

struct delta_t {
    ap_int<32>  price_ticks;
    ap_int<32>  qty;
    ap_uint<16> level;
    ap_uint<1>  side;    // 0=bid,1=ask
    ap_uint<2>  action;  // 0=set,1=add,2=update,3=remove
    ap_uint<64> t_send_ns;
    ap_uint<1>  last_in_pkt;
};

struct features_t {
    ap_int<32>  ofi_q32;
    ap_int<16>  tob_imb_q1_15;
    ap_uint<16> rsv0;
    ap_uint<32> burst_q16_16;
    ap_uint<32> vol_q16_16;
};

void feature_pipeline(hls::stream<axis64_t> &in_axis,
                      hls::stream<axis128_t> &feat_axis,
                      volatile bool *feat_done_pulse,
                      ap_uint<32> &feat_dbg_cycles);


