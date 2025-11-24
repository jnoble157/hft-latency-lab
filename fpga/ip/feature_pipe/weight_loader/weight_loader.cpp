// Weight loader: reads weights from DDR (m_axi) and streams 32-bit words to mlp_infer_stream.
// Order: W0 bytes -> B0 words -> W1 bytes -> B1 words
#include "ap_int.h"
#include "ap_axi_sdata.h"
#include "hls_stream.h"

typedef ap_axiu<32, 0, 0, 0> axis32_t;

void weight_loader(
	const ap_uint<8>*  w0_ptr,  // bytes
	const ap_int<32>*  b0_ptr,  // words
	const ap_uint<8>*  w1_ptr,  // bytes
	const ap_int<32>*  b1_ptr,  // words
	hls::stream<axis32_t>& m_axis_wload,
	ap_uint<32> w0_bytes,
	ap_uint<32> b0_words,
	ap_uint<32> w1_bytes,
	ap_uint<32> b1_words,
	ap_uint<1>  start
) {
#pragma HLS INTERFACE m_axi port=w0_ptr offset=slave bundle=W0 depth=2048 max_read_burst_length=128
#pragma HLS INTERFACE m_axi port=b0_ptr offset=slave bundle=B0 depth=2048 max_read_burst_length=128
#pragma HLS INTERFACE m_axi port=w1_ptr offset=slave bundle=W1 depth=2048 max_read_burst_length=128
#pragma HLS INTERFACE m_axi port=b1_ptr offset=slave bundle=B1 depth=16   max_read_burst_length=16
#pragma HLS INTERFACE axis port=m_axis_wload
#pragma HLS INTERFACE s_axilite port=w0_bytes bundle=CTRL
#pragma HLS INTERFACE s_axilite port=b0_words bundle=CTRL
#pragma HLS INTERFACE s_axilite port=w1_bytes bundle=CTRL
#pragma HLS INTERFACE s_axilite port=b1_words bundle=CTRL
#pragma HLS INTERFACE s_axilite port=start     bundle=CTRL
#pragma HLS INTERFACE s_axilite port=return    bundle=CTRL

	if (!start) return;

	axis32_t outw;

	// Stream W0 as 32-bit big-endian words, packing 4 bytes per word
	ap_uint<32> idx = 0;
	while (idx < w0_bytes) {
		#pragma HLS PIPELINE II=1
		ap_uint<8> b0 = (idx + 0 < w0_bytes) ? w0_ptr[idx + 0] : (ap_uint<8>)0;
		ap_uint<8> b1 = (idx + 1 < w0_bytes) ? w0_ptr[idx + 1] : (ap_uint<8>)0;
		ap_uint<8> b2 = (idx + 2 < w0_bytes) ? w0_ptr[idx + 2] : (ap_uint<8>)0;
		ap_uint<8> b3 = (idx + 3 < w0_bytes) ? w0_ptr[idx + 3] : (ap_uint<8>)0;
		ap_uint<32> be = (ap_uint<32>(b0) << 24) | (ap_uint<32>(b1) << 16) | (ap_uint<32>(b2) << 8) | (ap_uint<32>(b3));
		outw.data = be;
		outw.keep = 0xF;
		outw.strb = 0xF;
		outw.last = 0;
		m_axis_wload.write(outw);
		idx += 4;
	}

	// Stream B0 as 32-bit words
	for (ap_uint<32> i = 0; i < b0_words; ++i) {
		#pragma HLS PIPELINE II=1
		outw.data = (ap_uint<32>) b0_ptr[i];
		outw.keep = 0xF;
		outw.strb = 0xF;
		outw.last = 0;
		m_axis_wload.write(outw);
	}

	// Stream W1 as 32-bit big-endian words
	idx = 0;
	while (idx < w1_bytes) {
		#pragma HLS PIPELINE II=1
		ap_uint<8> b0 = (idx + 0 < w1_bytes) ? w1_ptr[idx + 0] : (ap_uint<8>)0;
		ap_uint<8> b1 = (idx + 1 < w1_bytes) ? w1_ptr[idx + 1] : (ap_uint<8>)0;
		ap_uint<8> b2 = (idx + 2 < w1_bytes) ? w1_ptr[idx + 2] : (ap_uint<8>)0;
		ap_uint<8> b3 = (idx + 3 < w1_bytes) ? w1_ptr[idx + 3] : (ap_uint<8>)0;
		ap_uint<32> be = (ap_uint<32>(b0) << 24) | (ap_uint<32>(b1) << 16) | (ap_uint<32>(b2) << 8) | (ap_uint<32>(b3));
		outw.data = be;
		outw.keep = 0xF;
		outw.strb = 0xF;
		outw.last = 0;
		m_axis_wload.write(outw);
		idx += 4;
	}

	// Stream B1 as 32-bit words
	for (ap_uint<32> i = 0; i < b1_words; ++i) {
		#pragma HLS PIPELINE II=1
		outw.data = (ap_uint<32>) b1_ptr[i];
		outw.keep = 0xF;
		outw.strb = 0xF;
		outw.last = (i == b1_words - 1) ? (ap_uint<1>)1 : (ap_uint<1>)0;
		m_axis_wload.write(outw);
	}
}


