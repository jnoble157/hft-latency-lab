open_project mlp_core_stream
set_top mlp_core_stream
add_files mlp_core_stream.cpp
open_solution "solution1"
set_part {xc7z020clg400-1}
create_clock -period 10 -name default
csynth_design
export_design -format ip_catalog -display_name "NeuroHFT MLP Core Stream"
exit


