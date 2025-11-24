open_project hls_traffic_gen
set_top traffic_gen
add_files traffic_gen.cpp
open_solution "solution1"
set_part {xc7z020clg400-1}
create_clock -period 10 -name default
csynth_design
export_design -format ip_catalog -display_name "NeuroHFT Traffic Gen" -vendor "NeuroHFT"
exit

