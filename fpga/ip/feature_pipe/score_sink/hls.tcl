open_project score_sink
set_top score_sink
add_files score_sink.cpp
open_solution "solution1"
set_part {xc7z020clg400-1}
create_clock -period 10 -name default
csynth_design
export_design -format ip_catalog -display_name "NeuroHFT Score Sink"
exit


