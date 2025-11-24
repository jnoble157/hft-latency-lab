// Stream-only MLP inference core with on-chip static weight cache.
// - s_axis_feat: one 128-bit feature beat per inference
// - s_axis_wload: 32-bit weight stream used to (re)load weights on demand
// - m_axis_score: one 32-bit Q16.16 score per inference
// - No m_axi ports in hot path
//
// Weight load protocol (when reload_weights==1):
//   Consume exactly:
//     w0_bytes bytes  (W0: H*D int8)
//     b0_words words  (B0: H int32)
//     w1_bytes bytes  (W1: H int8)
//     b1_words words  (B1: 1 int32)
//   Packed on s_axis_wload as 32-bit words (big-endian byte order per packet builder).
//   After loading, return without producing output.
//
#include "ap_int.h"
#include "ap_axi_sdata.h"
#include "hls_stream.h"

typedef ap_axiu<128, 0, 0, 0> axis128_t;
typedef ap_axiu<32, 0, 0, 0> axis32_t;

static inline ap_int<32> be32_to_s32(ap_uint<8> b0, ap_uint<8> b1, ap_uint<8> b2, ap_uint<8> b3) {
	#pragma HLS INLINE
	ap_uint<32> u = (ap_uint<32>(b0) << 24) | (ap_uint<32>(b1) << 16) | (ap_uint<32>(b2) << 8) | ap_uint<32>(b3);
	return ap_int<32>(u);
}
static inline ap_int<16> be16_to_s16(ap_uint<8> b0, ap_uint<8> b1) {
	#pragma HLS INLINE
	ap_uint<16> u = (ap_uint<16>(b0) << 8) | ap_uint<16>(b1);
	return ap_int<16>(u);
}
static inline ap_uint<32> be32_to_u32(ap_uint<8> b0, ap_uint<8> b1, ap_uint<8> b2, ap_uint<8> b3) {
	#pragma HLS INLINE
	return (ap_uint<32>(b0) << 24) | (ap_uint<32>(b1) << 16) | (ap_uint<32>(b2) << 8) | ap_uint<32>(b3);
}
static inline ap_int<8> clamp_to_i8(ap_int<32> v) {
	#pragma HLS INLINE
	if (v > 127) return ap_int<8>(127);
	if (v < -128) return ap_int<8>(-128);
	return ap_int<8>(v);
}

enum { D = 4, H = 32 };

void mlp_infer_stream(
	hls::stream<axis128_t>& s_axis_feat,
	hls::stream<axis32_t>&  s_axis_wload,
	hls::stream<axis32_t>&  m_axis_score,
	bool&                   done_pulse,
	float in_scale,
	float w0_scale,
	float act0_scale,
	float w1_scale,
	ap_uint<32> reload_weights,
	ap_uint<32> delay_cycles,
	ap_uint<32> w0_bytes,
	ap_uint<32> b0_words,
	ap_uint<32> w1_bytes,
	ap_uint<32> b1_words,
	ap_uint<32> &mlp_dbg_iters
) {
#pragma HLS INTERFACE axis port=s_axis_feat
#pragma HLS INTERFACE axis port=s_axis_wload
#pragma HLS INTERFACE axis port=m_axis_score
#pragma HLS INTERFACE ap_none port=done_pulse
#pragma HLS INTERFACE s_axilite port=in_scale       bundle=CTRL
#pragma HLS INTERFACE s_axilite port=w0_scale       bundle=CTRL
#pragma HLS INTERFACE s_axilite port=act0_scale     bundle=CTRL
#pragma HLS INTERFACE s_axilite port=w1_scale       bundle=CTRL
#pragma HLS INTERFACE s_axilite port=reload_weights bundle=CTRL
#pragma HLS INTERFACE s_axilite port=delay_cycles   bundle=CTRL
#pragma HLS INTERFACE s_axilite port=w0_bytes       bundle=CTRL
#pragma HLS INTERFACE s_axilite port=b0_words       bundle=CTRL
#pragma HLS INTERFACE s_axilite port=w1_bytes       bundle=CTRL
#pragma HLS INTERFACE s_axilite port=b1_words       bundle=CTRL
#pragma HLS INTERFACE s_axilite port=mlp_dbg_iters  bundle=CTRL
#pragma HLS INTERFACE s_axilite port=return         bundle=CTRL

	static ap_uint<8>  s_w0[H][D];
	#pragma HLS ARRAY_PARTITION variable=s_w0 complete dim=0
	static ap_int<32>  s_b0[H];
	#pragma HLS ARRAY_PARTITION variable=s_b0 complete dim=1
	static ap_uint<8>  s_w1[H];
	#pragma HLS ARRAY_PARTITION variable=s_w1 complete dim=1
	static ap_int<32>  s_b1_scalar;

	// Debug counter: counts iterations of key pipelined loops (not exact
	// clock cycles, but a proxy for "amount of MLP work" per inference).
	ap_uint<32> dbg_iters = 0;
	// Approximate cycle counter for the inference path. This is *not* a precise
	// clock count, but it increments in the main pipelined loops and tracks
	// relative latency between configurations.
	ap_uint<32> dbg_cycles = 0;

	// Default completion pulse low; asserted for one cycle at the end of
	// each successful inference transaction.
	done_pulse = false;

	// Weight reload path
	if (reload_weights == 1) {
		// Load W0 bytes (max 128 bytes -> 32 words)
		ap_uint<8>  tmp_bytes[4];
		for (int w = 0; w < 32; ++w) {
			#pragma HLS PIPELINE II=1
			#pragma HLS LOOP_TRIPCOUNT max=32
			if ((ap_uint<32>)(w * 4) >= w0_bytes) break;
			axis32_t wi = s_axis_wload.read();
			ap_uint<32> d = wi.data;
			tmp_bytes[0] = (ap_uint<8>) (d >> 24);
			tmp_bytes[1] = (ap_uint<8>) (d >> 16);
			tmp_bytes[2] = (ap_uint<8>) (d >> 8);
			tmp_bytes[3] = (ap_uint<8>) (d);
			for (int k = 0; k < 4; ++k) {
				#pragma HLS UNROLL
				ap_uint<32> idx = (ap_uint<32>)(w * 4 + k);
				if (idx < w0_bytes) {
					ap_uint<32> hidx = idx / D;
					ap_uint<32> didx = idx % D;
					if (hidx < H) {
						s_w0[hidx][didx] = tmp_bytes[k];
					}
				}
			}
		}
		// Load B0 words
		for (ap_uint<32> i = 0; i < b0_words; ++i) {
			#pragma HLS PIPELINE II=1
			#pragma HLS LOOP_TRIPCOUNT max=32
			axis32_t w = s_axis_wload.read();
			s_b0[i] = (ap_int<32>) w.data;
		}
		// Load W1 bytes (max 32 bytes -> 8 words)
		for (int w = 0; w < 8; ++w) {
			#pragma HLS PIPELINE II=1
			#pragma HLS LOOP_TRIPCOUNT max=8
			if ((ap_uint<32>)(w * 4) >= w1_bytes) break;
			axis32_t wi = s_axis_wload.read();
			ap_uint<32> d = wi.data;
			tmp_bytes[0] = (ap_uint<8>) (d >> 24);
			tmp_bytes[1] = (ap_uint<8>) (d >> 16);
			tmp_bytes[2] = (ap_uint<8>) (d >> 8);
			tmp_bytes[3] = (ap_uint<8>) (d);
			for (int k = 0; k < 4; ++k) {
				#pragma HLS UNROLL
				ap_uint<32> idx = (ap_uint<32>)(w * 4 + k);
				if (idx < w1_bytes && idx < H) {
					s_w1[(int)idx] = tmp_bytes[k];
				}
			}
		}
		// Load B1 words (scalar)
		for (ap_uint<32> i = 0; i < b1_words; ++i) {
			#pragma HLS PIPELINE II=1
			#pragma HLS LOOP_TRIPCOUNT max=1
			axis32_t w = s_axis_wload.read();
			if (i == 0) s_b1_scalar = (ap_int<32>) w.data;
		}
		return;
	}

	// Inference path
	axis128_t inw = s_axis_feat.read();
	ap_uint<128> din = inw.data;

	// Calibration delay
	for (ap_uint<32> dc = 0; dc < delay_cycles; ++dc) {
		#pragma HLS PIPELINE II=1
		dbg_cycles++;
	}

	ap_uint<8> B[16];
	#pragma HLS ARRAY_PARTITION variable=B complete dim=1
	for (int i = 0; i < 16; ++i) {
		#pragma HLS UNROLL
		B[i] = din.range((i + 1) * 8 - 1, i * 8);
	}

	ap_int<32> ofi_q32    = be32_to_s32(B[0], B[1], B[2], B[3]);
	ap_int<16> imb_q1_15  = be16_to_s16(B[4], B[5]);
	ap_uint<32> burst_q16 = be32_to_u32(B[8], B[9], B[10], B[11]);
	ap_uint<32> vol_q16   = be32_to_u32(B[12], B[13], B[14], B[15]);

	float x0 = (float)ofi_q32;
	float x1 = ((float)imb_q1_15) / 32768.0f;
	float x2 = ((float)burst_q16) / 65536.0f;
	float x3 = ((float)vol_q16) / 65536.0f;

	float inv_in_scale = (in_scale > 1e-12f) ? (1.0f / in_scale) : 0.0f;
	ap_int<8> xi[D];
	#pragma HLS ARRAY_PARTITION variable=xi complete dim=1
	xi[0] = clamp_to_i8((ap_int<32>) (x0 * inv_in_scale + (x0 >= 0 ? 0.5f : -0.5f)));
	xi[1] = clamp_to_i8((ap_int<32>) (x1 * inv_in_scale + (x1 >= 0 ? 0.5f : -0.5f)));
	xi[2] = clamp_to_i8((ap_int<32>) (x2 * inv_in_scale + (x2 >= 0 ? 0.5f : -0.5f)));
	xi[3] = clamp_to_i8((ap_int<32>) (x3 * inv_in_scale + (x3 >= 0 ? 0.5f : -0.5f)));

	ap_int<8> y0_i8[H];
	#pragma HLS ARRAY_PARTITION variable=y0_i8 complete dim=1
	float s0 = in_scale * w0_scale;
	float inv_act0 = (act0_scale > 1e-12f) ? (1.0f / act0_scale) : 0.0f;

	for(int h=0; h<H; ++h) {
		#pragma HLS PIPELINE II=2
		ap_int<32> acc = s_b0[h];
		for(int d=0; d<D; ++d) {
			#pragma HLS UNROLL
			acc += (ap_int<32>)xi[d] * (ap_int<32>)s_w0[h][d];
		}
		float val = (float)acc * s0;
		if (val < 0.0f) val = 0.0f;
		val = val * inv_act0;
		y0_i8[h] = clamp_to_i8((ap_int<32>)(val + 0.5f));
		// Each hidden neuron update represents work; count it toward the
		// approximate cycle budget.
		dbg_cycles++;
	}

	ap_int<32> acc1 = s_b1_scalar;
	for (int h = 0; h < H; ++h) {
		#pragma HLS PIPELINE II=1
		acc1 += (ap_int<32>) y0_i8[h] * (ap_int<32>) s_w1[h];
		dbg_iters++;
		dbg_cycles++;
	}
	float logits = (float)acc1 * (act0_scale * w1_scale);

	axis32_t outw;
	float scaled = logits * 65536.0f;
	if (scaled > 2147483647.0f) scaled = 2147483647.0f;
	if (scaled < -2147483648.0f) scaled = -2147483648.0f;
	ap_int<32> score_q16 = (ap_int<32>) (scaled + (scaled >= 0 ? 0.5f : -0.5f));
	outw.data = (ap_uint<32>) score_q16;
	outw.keep = ap_uint<32/8>(0xF);
	outw.strb = ap_uint<32/8>(0xF);
	outw.last = inw.last;
	m_axis_score.write(outw);

	// One-cycle completion strobe for latency measurement.
	done_pulse = true;

	// Expose approximate cycle count on AXI-Lite for software to read back.
	mlp_dbg_iters = dbg_cycles;
}


