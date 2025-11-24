#include "feature_pipeline.hpp"

static const int NLEVEL = 16;

struct level_state_t {
    ap_int<32> price[NLEVEL];
    ap_int<32> qty[NLEVEL];
};

static void parse_stream_one_packet(hls::stream<axis64_t> &in_axis,
                                    hls::stream<delta_t> &out_deltas,
                                    ap_uint<16> &packet_delta_count,
                                    ap_uint<64> &packet_t_send_ns) {
#pragma HLS INLINE off
#pragma HLS PIPELINE II=1
    // Read 32B header (four 64b beats). AXIS packs the first byte of the packet in bits [7:0].
    ap_uint<64> hdr0 = in_axis.read().data; // bytes 0..7
    ap_uint<64> hdr1 = in_axis.read().data; // bytes 8..15
    ap_uint<64> hdr2 = in_axis.read().data; // bytes 16..23
    ap_uint<64> hdr3 = in_axis.read().data; // bytes 24..31

    // Extract flags at header bytes 6..7 (big-endian 16-bit)
    ap_uint<8> b6 = (ap_uint<8>)((hdr0 >> 48) & 0xFF);
    ap_uint<8> b7 = (ap_uint<8>)((hdr0 >> 56) & 0xFF);
    ap_uint<16> flags = ((ap_uint<16>)b6 << 8) | (ap_uint<16>)b7;
    // Host encodes: bit15 = reset, bits[14:0] = delta_count
    ap_uint<16> delta_count = (flags & (ap_uint<16>)0x7FFF);
    if (delta_count > (ap_uint<16>)128) {
        delta_count = (ap_uint<16>)128;
    }
    packet_delta_count = delta_count;

    // t_send_ns at header bytes 14..21 (big-endian 64b spanning hdr1 and hdr2)
    // hdr1 = bytes 8..15; hdr2 = bytes 16..23
    ap_uint<8> h1_b0 = (ap_uint<8>)((hdr1 >> 0)  & 0xFF);
    ap_uint<8> h1_b1 = (ap_uint<8>)((hdr1 >> 8)  & 0xFF);
    ap_uint<8> h1_b2 = (ap_uint<8>)((hdr1 >> 16) & 0xFF);
    ap_uint<8> h1_b3 = (ap_uint<8>)((hdr1 >> 24) & 0xFF);
    ap_uint<8> h1_b4 = (ap_uint<8>)((hdr1 >> 32) & 0xFF);
    ap_uint<8> h1_b5 = (ap_uint<8>)((hdr1 >> 40) & 0xFF);
    ap_uint<8> h1_b6 = (ap_uint<8>)((hdr1 >> 48) & 0xFF);
    ap_uint<8> h1_b7 = (ap_uint<8>)((hdr1 >> 56) & 0xFF);
    ap_uint<8> h2_b0 = (ap_uint<8>)((hdr2 >> 0)  & 0xFF);
    ap_uint<8> h2_b1 = (ap_uint<8>)((hdr2 >> 8)  & 0xFF);
    ap_uint<8> h2_b2 = (ap_uint<8>)((hdr2 >> 16) & 0xFF);
    ap_uint<8> h2_b3 = (ap_uint<8>)((hdr2 >> 24) & 0xFF);
    ap_uint<8> h2_b4 = (ap_uint<8>)((hdr2 >> 32) & 0xFF);
    ap_uint<8> h2_b5 = (ap_uint<8>)((hdr2 >> 40) & 0xFF);
    // Assemble 8 bytes: [14..21] = [h1_b6, h1_b7, h2_b0, h2_b1, h2_b2, h2_b3, h2_b4, h2_b5]
    ap_uint<64> t_be = 0;
    t_be |= (ap_uint<64>)h1_b6 << 56;
    t_be |= (ap_uint<64>)h1_b7 << 48;
    t_be |= (ap_uint<64>)h2_b0 << 40;
    t_be |= (ap_uint<64>)h2_b1 << 32;
    t_be |= (ap_uint<64>)h2_b2 << 24;
    t_be |= (ap_uint<64>)h2_b3 << 16;
    t_be |= (ap_uint<64>)h2_b4 << 8;
    t_be |= (ap_uint<64>)h2_b5;
    packet_t_send_ns = t_be;

    // Read deltas and push to FIFO
    for (ap_uint<16> i = 0; i < delta_count; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=0 max=128
        ap_uint<64> d0 = in_axis.read().data; // delta bytes 0..7
        ap_uint<64> d1 = in_axis.read().data; // delta bytes 8..15

        // Reconstruct big-endian fields from AXIS little-byte positions
        // price_ticks (bytes 0..3, be32)
        ap_uint<8> d0_b0 = (ap_uint<8>)((d0 >> 0)  & 0xFF);
        ap_uint<8> d0_b1 = (ap_uint<8>)((d0 >> 8)  & 0xFF);
        ap_uint<8> d0_b2 = (ap_uint<8>)((d0 >> 16) & 0xFF);
        ap_uint<8> d0_b3 = (ap_uint<8>)((d0 >> 24) & 0xFF);
        ap_uint<8> d0_b4 = (ap_uint<8>)((d0 >> 32) & 0xFF);
        ap_uint<8> d0_b5 = (ap_uint<8>)((d0 >> 40) & 0xFF);
        ap_uint<8> d0_b6 = (ap_uint<8>)((d0 >> 48) & 0xFF);
        ap_uint<8> d0_b7 = (ap_uint<8>)((d0 >> 56) & 0xFF);
        ap_uint<32> price_be = ((ap_uint<32>)d0_b0 << 24) | ((ap_uint<32>)d0_b1 << 16) |
                               ((ap_uint<32>)d0_b2 << 8)  |  (ap_uint<32>)d0_b3;
        // qty (bytes 4..7, be32)
        ap_uint<32> qty_be   = ((ap_uint<32>)d0_b4 << 24) | ((ap_uint<32>)d0_b5 << 16) |
                               ((ap_uint<32>)d0_b6 << 8)  |  (ap_uint<32>)d0_b7;
        // level (bytes 8..9, be16)
        ap_uint<8> d1_b8  = (ap_uint<8>)((d1 >> 0)  & 0xFF);
        ap_uint<8> d1_b9  = (ap_uint<8>)((d1 >> 8)  & 0xFF);
        ap_uint<8> d1_b10 = (ap_uint<8>)((d1 >> 16) & 0xFF);
        ap_uint<8> d1_b11 = (ap_uint<8>)((d1 >> 24) & 0xFF);
        ap_uint<16> lvl_be = ((ap_uint<16>)d1_b8 << 8) | (ap_uint<16>)d1_b9;
        // side (byte 10), action (byte 11)
        ap_uint<8>  side   = d1_b10;
        ap_uint<8>  action = d1_b11;
        delta_t out;
        out.price_ticks = (ap_int<32>)price_be;
        out.qty         = (ap_int<32>)qty_be;
        out.level       = (ap_uint<16>)lvl_be;
        out.side        = (ap_uint<1>)(side & 0x1);
        out.action      = (ap_uint<2>)(action & 0x3);
        out.t_send_ns   = (ap_uint<64>)packet_t_send_ns;
        out.last_in_pkt = (i == (delta_count - 1)) ? (ap_uint<1>)1 : (ap_uint<1>)0;
        out_deltas.write(out);
    }
}

static void update_book(const delta_t &d,
                        level_state_t &bid, level_state_t &ask,
                        ap_int<32> &best_bid_px, ap_int<32> &best_ask_px,
                        ap_int<32> &best_bid_qty, ap_int<32> &best_ask_qty,
                        ap_int<32> &ofi_accum) {
#pragma HLS INLINE
    level_state_t &side = d.side ? ask : bid;
    ap_uint<16> lvl = d.level;
    if (lvl < NLEVEL) {
        switch ((int)d.action) {
            case 0: // set
                side.price[lvl] = d.price_ticks;
                side.qty[lvl] = d.qty;
                break;
            case 1: // add
                side.qty[lvl] = side.qty[lvl] + d.qty;
                break;
            case 2: // update
                side.qty[lvl] = side.qty[lvl] + d.qty;
                break;
            case 3: // remove => clear level (host sends qty=0)
                side.qty[lvl] = 0;
                break;
            default: break;
        }
        // clamp non-negative
        if (side.qty[lvl] < 0) side.qty[lvl] = 0;
    }
    // OFI accumulation: count only add/update; avoid ternary width ambiguity
    if (d.action == 1 || d.action == 2) {
        ap_int<32> amt = d.qty;
        if (d.side == (ap_uint<1>)0) {
            ofi_accum = (ap_int<32>)(ofi_accum + amt);
        } else {
            ofi_accum = (ap_int<32>)(ofi_accum - amt);
        }
    }

    // Best levels from level 0
    best_bid_px = bid.price[0];
    best_ask_px = ask.price[0];
    best_bid_qty = bid.qty[0];
    best_ask_qty = ask.qty[0];
}

static void compute_features(const delta_t &d,
                             ap_int<32> best_bid_px, ap_int<32> best_ask_px,
                             ap_int<32> best_bid_qty, ap_int<32> best_ask_qty,
                             ap_int<32> &ofi_accum,
                             ap_uint<64> &last_t,
                             ap_uint<32> &burst_q16_16,
                             ap_uint<32> &vol_q16_16,
                             ap_int<32> &mid_prev,
                             features_t &f) {
#pragma HLS INLINE
    ap_uint<64> dt64 = (last_t == (ap_uint<64>)0) ? (ap_uint<64>)0 : (ap_uint<64>)(d.t_send_ns - last_t);
    last_t = d.t_send_ns;
    // Reduce multiplier width: clamp dt to 32 bits (packet gaps are in the us-ms range)
    ap_uint<32> dt = (dt64 > (ap_uint<64>)0xFFFFFFFFULL) ? (ap_uint<32>)0xFFFFFFFFU : (ap_uint<32>)dt64;

    // Top-of-book imbalance Q1.15
    ap_int<33> num = (ap_int<33>)best_bid_qty - (ap_int<33>)best_ask_qty;
    ap_int<33> den = (ap_int<33>)best_bid_qty + (ap_int<33>)best_ask_qty;
    ap_int<16> imb_q1_15 = 0;
    if (den != 0) {
        ap_int<48> num_scaled = ((ap_int<48>)num) << 15;
        // Raw quotient can overflow Q1.15 positive side (32768) when |num| == den; clamp to 0x7FFF
        ap_int<32> q = (ap_int<32>)(num_scaled / den);
        if (q > (ap_int<32>)0x7FFF) {
            imb_q1_15 = (ap_int<16>)0x7FFF;
        } else if (q < (ap_int<32>)(-0x8000)) {
            imb_q1_15 = (ap_int<16>)(-0x8000);
        } else {
            imb_q1_15 = (ap_int<16>)q;
        }
    }

    // Burst leaky bucket: v = v - v*dt/tau + 1
    const ap_uint<32> tau_burst_ns = (ap_uint<32>)200000; // 0.2 ms
    ap_uint<64> decay_b = ((ap_uint<64>)burst_q16_16 * (ap_uint<64>)dt) / (ap_uint<64>)tau_burst_ns;
    ap_int<64> v_b = (ap_int<64>)burst_q16_16 - (ap_int<64>)decay_b + ((ap_int<64>)1 << 16);
    if (v_b < (ap_int<64>)0) v_b = (ap_int<64>)0;
    if (v_b > (ap_int<64>)0xFFFFFFFFLL) v_b = (ap_int<64>)0xFFFFFFFFLL;
    burst_q16_16 = (ap_uint<32>)v_b;

    // Micro-vol EWMA on mid
    const ap_uint<32> tau_vol_ns = (ap_uint<32>)2000000; // 2 ms
    ap_int<32> mid_now = (best_bid_px + best_ask_px) >> 1;
    ap_int<32> diff = mid_now - mid_prev;
    ap_uint<32> dp_abs = (diff >= 0) ? (ap_uint<32>)diff : (ap_uint<32>)(-diff);
    mid_prev = mid_now;
    ap_int<64> num_vol = (ap_int<64>)(((ap_uint<64>)dp_abs << 16) - (ap_uint<64>)vol_q16_16);
    ap_int<64> delta_v = (num_vol * (ap_int<64>)dt) / (ap_int<64>)tau_vol_ns;
    ap_int<64> v_vol = (ap_int<64>)vol_q16_16 + delta_v;
    if (v_vol < (ap_int<64>)0) v_vol = (ap_int<64>)0;
    if (v_vol > (ap_int<64>)0xFFFFFFFFLL) v_vol = (ap_int<64>)0xFFFFFFFFLL;
    vol_q16_16 = (ap_uint<32>)v_vol;

    f.ofi_q32 = ofi_accum;
    f.tob_imb_q1_15 = imb_q1_15;
    f.rsv0 = 0;
    f.burst_q16_16 = burst_q16_16;
    f.vol_q16_16 = vol_q16_16;
}

void feature_pipeline(hls::stream<axis64_t> &in_axis,
                      hls::stream<axis128_t> &feat_axis,
                      volatile bool *feat_done_pulse,
                      ap_uint<32> &feat_dbg_cycles) {
#pragma HLS INTERFACE axis port=in_axis
#pragma HLS INTERFACE axis port=feat_axis
#pragma HLS INTERFACE ap_none port=feat_done_pulse
#pragma HLS INTERFACE s_axilite port=feat_dbg_cycles bundle=CTRL
#pragma HLS INTERFACE ap_ctrl_none port=return

    static level_state_t bid = {}, ask = {};
    static ap_int<32> best_bid_px = 0, best_ask_px = 0;
    static ap_int<32> best_bid_qty = 0, best_ask_qty = 0;
    static ap_int<32> ofi_accum = 0;
    static ap_uint<64> last_t = 0;
    static ap_uint<32> burst_q16_16 = 0;
    static ap_uint<32> vol_q16_16 = 0;
    static ap_int<32> mid_prev = 0;

    hls::stream<delta_t> ds;
#pragma HLS STREAM depth=8 variable=ds

    // Internal cycle counter for one packet (header -> feature beat out).
    static ap_uint<32> cyc = 0;
    static bool measuring = false;

    // Perpetual packet pump
    while (1) {
#pragma HLS PIPELINE II=1
        // Start a new measurement window at the beginning of each packet.
        if (!measuring) {
            cyc = 0;
            measuring = true;
        }
        // Count this cycle while we're processing the current packet.
        if (measuring) {
            cyc++;
        }

        // Default: no completion pulse this cycle. We will assert a
        // one-cycle strobe when emitting a feature beat.
        *feat_done_pulse = false;
        // One-shot debug emit disabled for production
        ap_uint<16> packet_delta_count = 0;
        ap_uint<64> packet_t_send_ns = 0;
        // Block until one packet is parsed in
        parse_stream_one_packet(in_axis, ds, packet_delta_count, packet_t_send_ns);
        // If there are zero deltas, emit a feature immediately after header to verify S2MM path
        if (packet_delta_count == (ap_uint<16>)0) {
            delta_t d_end_immediate;
            d_end_immediate.t_send_ns = packet_t_send_ns;
            d_end_immediate.last_in_pkt = 1;
            features_t f_immediate;
            compute_features(d_end_immediate, best_bid_px, best_ask_px, best_bid_qty, best_ask_qty,
                             ofi_accum, last_t, burst_q16_16, vol_q16_16, mid_prev, f_immediate);
            ap_uint<128> w_immediate = 0;
            w_immediate.range(31, 0)   = (ap_uint<32>)f_immediate.ofi_q32;
            w_immediate.range(47, 32)  = (ap_uint<16>)f_immediate.tob_imb_q1_15;
            w_immediate.range(63, 48)  = (ap_uint<16>)f_immediate.rsv0;
            w_immediate.range(95, 64)  = (ap_uint<32>)f_immediate.burst_q16_16;
            w_immediate.range(127, 96) = (ap_uint<32>)f_immediate.vol_q16_16;
            axis128_t axo0;
            axo0.data = w_immediate;
            axo0.keep = 0xFFFF;
            axo0.strb = 0xFFFF;
            axo0.last = 1;
            feat_axis.write(axo0);
            *feat_done_pulse = true;
            // Latch measured cycles for this packet and stop measuring
            feat_dbg_cycles = cyc;
            measuring = false;
            continue;
        }
        // Consume the packet's deltas
        for (int i = 0; i < packet_delta_count; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=0 max=128
#pragma HLS PIPELINE II=1
            delta_t d = ds.read();
            update_book(d, bid, ask, best_bid_px, best_ask_px, best_bid_qty, best_ask_qty, ofi_accum);
        }
        // Emit one feature beat per packet
        delta_t d_end; d_end.t_send_ns = packet_t_send_ns; d_end.last_in_pkt = 1;
        features_t f;
        compute_features(d_end, best_bid_px, best_ask_px, best_bid_qty, best_ask_qty,
                         ofi_accum, last_t, burst_q16_16, vol_q16_16, mid_prev, f);
        ap_uint<128> w = 0;
        w.range(31, 0)   = (ap_uint<32>)f.ofi_q32;
        w.range(47, 32)  = (ap_uint<16>)f.tob_imb_q1_15;
        w.range(63, 48)  = (ap_uint<16>)f.rsv0;
        w.range(95, 64)  = (ap_uint<32>)f.burst_q16_16;
        w.range(127, 96) = (ap_uint<32>)f.vol_q16_16;
        axis128_t axo;
        axo.data = w;
        axo.keep = 0xFFFF;
        axo.strb = 0xFFFF;
        axo.last = 1;
        feat_axis.write(axo);
        *feat_done_pulse = true;
        feat_dbg_cycles = cyc;
        measuring = false;
    }
}


