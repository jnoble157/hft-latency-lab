#!/usr/bin/env bash
# Configuration for low-latency tuning. Values may be empty to skip features.

ISOL_CPUS="4-7,12-15"
NOHZ_FULL_CPUS="4-7,12-15"
RCU_NOCBS_CPUS="4-7,12-15"

HUGEPAGES_2M="1024"      # ~2GB
HUGEPAGES_1G="0"         # keep off unless you need it and kernel supports it
HUGEPAGES_MOUNT="/dev/hugepages"

NON_ISOL_IRQ_CPUS="0-3,8-11"  # steer IRQs to housekeeping cores (optional)

# Internal defaults (unlikely to change)
GRUB_FILE="/etc/default/grub"
SYSCTL_DROPIN="/etc/sysctl.d/90-lowlatency.conf"
SYSTEMD_SERVICE="/etc/systemd/system/disable-cstates.service"


