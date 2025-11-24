

set RtlHierarchyInfo {[
	{"ID" : "0", "Level" : "0", "Path" : "`AUTOTB_DUT_INST", "Parent" : "", "Child" : ["1", "2", "3", "4"],
		"CDFG" : "score_sink",
		"Protocol" : "ap_ctrl_none",
		"ControlExist" : "0", "ap_start" : "0", "ap_ready" : "0", "ap_done" : "0", "ap_continue" : "0", "ap_idle" : "0", "real_start" : "0",
		"Pipeline" : "None", "UnalignedPipeline" : "0", "RewindPipeline" : "0", "ProcessNetwork" : "0",
		"II" : "0",
		"VariableLatency" : "1", "ExactLatency" : "-1", "EstimateLatencyMin" : "1", "EstimateLatencyMax" : "1",
		"Combinational" : "0",
		"Datapath" : "0",
		"ClockEnable" : "0",
		"HasSubDataflow" : "0",
		"InDataflowNetwork" : "0",
		"HasNonBlockingOperation" : "1",
		"IsBlackBox" : "0",
		"Port" : [
			{"Name" : "s_axis_score_V_data_V", "Type" : "Axis", "Direction" : "I", "BaseName" : "s_axis_score",
				"BlockSignal" : [
					{"Name" : "s_axis_score_TDATA_blk_n", "Type" : "RtlSignal"}]},
			{"Name" : "s_axis_score_V_keep_V", "Type" : "Axis", "Direction" : "I", "BaseName" : "s_axis_score"},
			{"Name" : "s_axis_score_V_strb_V", "Type" : "Axis", "Direction" : "I", "BaseName" : "s_axis_score"},
			{"Name" : "s_axis_score_V_last_V", "Type" : "Axis", "Direction" : "I", "BaseName" : "s_axis_score"},
			{"Name" : "done_pulse", "Type" : "None", "Direction" : "O"}]},
	{"ID" : "1", "Level" : "1", "Path" : "`AUTOTB_DUT_INST.regslice_both_s_axis_score_V_data_V_U", "Parent" : "0"},
	{"ID" : "2", "Level" : "1", "Path" : "`AUTOTB_DUT_INST.regslice_both_s_axis_score_V_keep_V_U", "Parent" : "0"},
	{"ID" : "3", "Level" : "1", "Path" : "`AUTOTB_DUT_INST.regslice_both_s_axis_score_V_strb_V_U", "Parent" : "0"},
	{"ID" : "4", "Level" : "1", "Path" : "`AUTOTB_DUT_INST.regslice_both_s_axis_score_V_last_V_U", "Parent" : "0"}]}
