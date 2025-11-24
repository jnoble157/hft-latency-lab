#include "hls_design_meta.h"
const Port_Property HLS_Design_Meta::port_props[]={
	Port_Property("ap_clk", 1, hls_in, -1, "", "", 1),
	Port_Property("ap_rst_n", 1, hls_in, -1, "", "", 1),
	Port_Property("s_axis_feat_TDATA", 128, hls_in, 0, "axis", "in_data", 1),
	Port_Property("s_axis_feat_TVALID", 1, hls_in, 3, "axis", "in_vld", 1),
	Port_Property("s_axis_feat_TREADY", 1, hls_out, 3, "axis", "in_acc", 1),
	Port_Property("s_axis_feat_TKEEP", 16, hls_in, 1, "axis", "in_data", 1),
	Port_Property("s_axis_feat_TSTRB", 16, hls_in, 2, "axis", "in_data", 1),
	Port_Property("s_axis_feat_TLAST", 1, hls_in, 3, "axis", "in_data", 1),
	Port_Property("m_axis_score_TDATA", 32, hls_out, 4, "axis", "out_data", 1),
	Port_Property("m_axis_score_TVALID", 1, hls_out, 7, "axis", "out_vld", 1),
	Port_Property("m_axis_score_TREADY", 1, hls_in, 7, "axis", "out_acc", 1),
	Port_Property("m_axis_score_TKEEP", 4, hls_out, 5, "axis", "out_data", 1),
	Port_Property("m_axis_score_TSTRB", 4, hls_out, 6, "axis", "out_data", 1),
	Port_Property("m_axis_score_TLAST", 1, hls_out, 7, "axis", "out_data", 1),
	Port_Property("done_pulse", 1, hls_out, 8, "ap_none", "out_data", 1),
};
const char* HLS_Design_Meta::dut_name = "mlp_core_stream";
