set moduleName score_sink
set isTopModule 1
set isCombinational 0
set isDatapathOnly 0
set isPipelined 1
set isPipelined_legacy 0
set pipeline_type none
set FunctionProtocol ap_ctrl_none
set isOneStateSeq 0
set ProfileFlag 0
set StallSigGenFlag 0
set isEnableWaveformDebug 1
set hasInterrupt 0
set DLRegFirstOffset 0
set DLRegItemOffset 0
set svuvm_can_support 1
set cdfgNum 2
set C_modelName {score_sink}
set C_modelType { void 0 }
set ap_memory_interface_dict [dict create]
set C_modelArgList {
	{ s_axis_score_V_data_V int 32 regular {axi_s 0 volatile  { s_axis_score Data } }  }
	{ s_axis_score_V_keep_V int 4 regular {axi_s 0 volatile  { s_axis_score Keep } }  }
	{ s_axis_score_V_strb_V int 4 regular {axi_s 0 volatile  { s_axis_score Strb } }  }
	{ s_axis_score_V_last_V int 1 regular {axi_s 0 volatile  { s_axis_score Last } }  }
	{ done_pulse int 1 regular {pointer 1}  }
}
set hasAXIMCache 0
set l_AXIML2Cache [list]
set AXIMCacheInstDict [dict create]
set C_modelArgMapList {[ 
	{ "Name" : "s_axis_score_V_data_V", "interface" : "axis", "bitwidth" : 32, "direction" : "READONLY"} , 
 	{ "Name" : "s_axis_score_V_keep_V", "interface" : "axis", "bitwidth" : 4, "direction" : "READONLY"} , 
 	{ "Name" : "s_axis_score_V_strb_V", "interface" : "axis", "bitwidth" : 4, "direction" : "READONLY"} , 
 	{ "Name" : "s_axis_score_V_last_V", "interface" : "axis", "bitwidth" : 1, "direction" : "READONLY"} , 
 	{ "Name" : "done_pulse", "interface" : "wire", "bitwidth" : 1, "direction" : "WRITEONLY"} ]}
# RTL Port declarations: 
set portNum 9
set portList { 
	{ ap_clk sc_in sc_logic 1 clock -1 } 
	{ ap_rst_n sc_in sc_logic 1 reset -1 active_low_sync } 
	{ s_axis_score_TDATA sc_in sc_lv 32 signal 0 } 
	{ s_axis_score_TVALID sc_in sc_logic 1 invld 3 } 
	{ s_axis_score_TREADY sc_out sc_logic 1 inacc 3 } 
	{ s_axis_score_TKEEP sc_in sc_lv 4 signal 1 } 
	{ s_axis_score_TSTRB sc_in sc_lv 4 signal 2 } 
	{ s_axis_score_TLAST sc_in sc_lv 1 signal 3 } 
	{ done_pulse sc_out sc_lv 1 signal 4 } 
}
set NewPortList {[ 
	{ "name": "ap_clk", "direction": "in", "datatype": "sc_logic", "bitwidth":1, "type": "clock", "bundle":{"name": "ap_clk", "role": "default" }} , 
 	{ "name": "ap_rst_n", "direction": "in", "datatype": "sc_logic", "bitwidth":1, "type": "reset", "bundle":{"name": "ap_rst_n", "role": "default" }} , 
 	{ "name": "s_axis_score_TDATA", "direction": "in", "datatype": "sc_lv", "bitwidth":32, "type": "signal", "bundle":{"name": "s_axis_score_V_data_V", "role": "default" }} , 
 	{ "name": "s_axis_score_TVALID", "direction": "in", "datatype": "sc_logic", "bitwidth":1, "type": "invld", "bundle":{"name": "s_axis_score_V_last_V", "role": "default" }} , 
 	{ "name": "s_axis_score_TREADY", "direction": "out", "datatype": "sc_logic", "bitwidth":1, "type": "inacc", "bundle":{"name": "s_axis_score_V_last_V", "role": "default" }} , 
 	{ "name": "s_axis_score_TKEEP", "direction": "in", "datatype": "sc_lv", "bitwidth":4, "type": "signal", "bundle":{"name": "s_axis_score_V_keep_V", "role": "default" }} , 
 	{ "name": "s_axis_score_TSTRB", "direction": "in", "datatype": "sc_lv", "bitwidth":4, "type": "signal", "bundle":{"name": "s_axis_score_V_strb_V", "role": "default" }} , 
 	{ "name": "s_axis_score_TLAST", "direction": "in", "datatype": "sc_lv", "bitwidth":1, "type": "signal", "bundle":{"name": "s_axis_score_V_last_V", "role": "default" }} , 
 	{ "name": "done_pulse", "direction": "out", "datatype": "sc_lv", "bitwidth":1, "type": "signal", "bundle":{"name": "done_pulse", "role": "default" }}  ]}

set ArgLastReadFirstWriteLatency {
	score_sink {
		s_axis_score_V_data_V {Type I LastRead 0 FirstWrite -1}
		s_axis_score_V_keep_V {Type I LastRead 0 FirstWrite -1}
		s_axis_score_V_strb_V {Type I LastRead 0 FirstWrite -1}
		s_axis_score_V_last_V {Type I LastRead 0 FirstWrite -1}
		done_pulse {Type O LastRead -1 FirstWrite 0}}}

set hasDtUnsupportedChannel 0

set PerformanceInfo {[
	{"Name" : "Latency", "Min" : "1", "Max" : "1"}
	, {"Name" : "Interval", "Min" : "2", "Max" : "2"}
]}

set PipelineEnableSignalInfo {[
]}

set Spec2ImplPortList { 
	s_axis_score_V_data_V { axis {  { s_axis_score_TDATA in_data 0 32 } } }
	s_axis_score_V_keep_V { axis {  { s_axis_score_TKEEP in_data 0 4 } } }
	s_axis_score_V_strb_V { axis {  { s_axis_score_TSTRB in_data 0 4 } } }
	s_axis_score_V_last_V { axis {  { s_axis_score_TVALID in_vld 0 1 }  { s_axis_score_TREADY in_acc 1 1 }  { s_axis_score_TLAST in_data 0 1 } } }
	done_pulse { ap_none {  { done_pulse out_data 1 1 } } }
}

set maxi_interface_dict [dict create]

# RTL port scheduling information:
set fifoSchedulingInfoList { 
}

# RTL bus port read request latency information:
set busReadReqLatencyList { 
}

# RTL bus port write response latency information:
set busWriteResLatencyList { 
}

# RTL array port load latency information:
set memoryLoadLatencyList { 
}
