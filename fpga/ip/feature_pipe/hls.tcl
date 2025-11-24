open_project feature_pipe_hls
set_top feature_pipeline
add_files feature_pipeline.cpp
add_files feature_pipeline.hpp
add_files -tb tb_feature_pipeline.cpp
open_solution -reset solution1
set_part {xc7z020clg400-1}
create_clock -period 6.667 -name default
csynth_design
export_design -format ip_catalog
exit


