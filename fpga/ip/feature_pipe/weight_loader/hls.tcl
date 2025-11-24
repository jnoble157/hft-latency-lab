open_project weight_loader
set_top weight_loader
add_files weight_loader.cpp
open_solution "solution1"
set_part {xc7z020clg400-1}
create_clock -period 10 -name default
csynth_design
export_design -format ip_catalog -display_name "NeuroHFT Weight Loader"
exit


