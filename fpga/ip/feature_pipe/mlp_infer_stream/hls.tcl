open_project mlp_infer_stream
set_top mlp_infer_stream
add_files mlp_infer_stream.cpp
open_solution "solution1"
set_part {xc7z020clg400-1}
create_clock -period 10 -name default
csynth_design
export_design -format ip_catalog -display_name "NeuroHFT MLP Infer Stream"
exit


