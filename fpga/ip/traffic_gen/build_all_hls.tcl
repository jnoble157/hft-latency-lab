# Script to synthesize HLS IPs
# Usage: vivado_hls build_hls_ips.tcl

# 1. Traffic Generator
open_project hls_traffic_gen
set_top traffic_gen
add_files traffic_gen.cpp
open_solution "solution1"
set_part {xc7z020clg400-1}
create_clock -period 10 -name default
csynth_design
export_design -format ip_catalog -display_name "NeuroHFT Traffic Gen" -vendor "NeuroHFT" -version "1.0"
close_project

# 2. Latency Timer
open_project hls_timer
set_top latency_timer
add_files latency_timer.cpp
open_solution "solution1"
set_part {xc7z020clg400-1}
create_clock -period 10 -name default
csynth_design
export_design -format ip_catalog -display_name "NeuroHFT Latency Timer" -vendor "NeuroHFT" -version "1.0"
close_project

exit

