#!/usr/bin/env bash
set -euo pipefail

# Usage: sudo infra/ptp/ptp-start.sh <iface> [profile]
# profile: oc (ordinary clock, default) | bc (boundary) | p2p (peer-to-peer delay)

iface="${1:-}"
profile="${2:-oc}"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Run as root" >&2; exit 1
fi
[[ -n "$iface" ]] || { echo "[USAGE] $0 <iface> [profile]"; exit 2; }

ptp_dev=$(readlink -f "/sys/class/net/${iface}/device/ptp"/ptp* 2>/dev/null || true)
[[ -n "$ptp_dev" ]] || { echo "[ERR] No PHC for ${iface}"; exit 3; }
phc="/dev/$(basename "$ptp_dev")"

conf="/tmp/ptp4l-${iface}.conf"
cat > "$conf" <<EOF
[global]
tx_timestamp_timeout  10
logging_level         6
message_tag           1
summary_interval      1
time_stamping         hardware
EOF

case "$profile" in
  p2p) echo 'delay_mechanism P2P' >> "$conf" ;;
  *) : ;;
esac

mkdir -p /run/ptp
ptp4l_log="/run/ptp/ptp4l-${iface}.log"
phc2sys_log="/run/ptp/phc2sys-${iface}.log"

echo "[INFO] Starting ptp4l on ${iface} (PHC ${phc})"
ptp4l -i "$iface" -f "$conf" -m -2 >"$ptp4l_log" 2>&1 & echo $! >/run/ptp/ptp4l.pid

sleep 1
echo "[INFO] Starting phc2sys (PHC -> CLOCK_REALTIME)"
phc2sys -s "$phc" -c CLOCK_REALTIME -O 0 -m -w >"$phc2sys_log" 2>&1 & echo $! >/run/ptp/phc2sys.pid

echo "[OK] ptp4l/phc2sys started. Logs in /run/ptp/*.log"


