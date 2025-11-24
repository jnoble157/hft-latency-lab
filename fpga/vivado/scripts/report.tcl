set script_dir [file dirname [info script]]
set build_dir [file normalize "$script_dir/../build"]
file mkdir $build_dir

# Optional argument: path to .xpr
if {[llength $argv] > 0} {
  set xpr_path [lindex $argv 0]
} else {
  set xpr_path [file normalize "$script_dir/../vivado_proj/feature_overlay.xpr"]
}

if {[catch {current_project}]} {
  if {[file exists $xpr_path]} {
    puts "INFO: Opening project: $xpr_path"
    open_project $xpr_path
  } else {
    puts "ERROR: No open project and XPR not found at: $xpr_path"
    exit 1
  }
}

if {[catch {open_run impl_1}]} {
  puts "INFO: impl_1 not open; attempting to open checkpoint if available"
}

report_timing_summary -warn_on_violation -file "$build_dir/timing_summary.rpt"
report_utilization -file "$build_dir/utilization.rpt"
puts "INFO: Reports written to $build_dir"


