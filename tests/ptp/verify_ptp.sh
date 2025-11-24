#!/usr/bin/env bash
set -euo pipefail

# Usage: tests/ptp/verify_ptp.sh <iface>

iface="${1:-}"
[[ -n "$iface" ]] || { echo "[USAGE] $0 <iface>"; exit 2; }

echo "[INFO] Checking caps for $iface"
ethtool -T "$iface" | sed '1,1!b; $!b' || true

ptp_path=$(readlink -f "/sys/class/net/${iface}/device/ptp"/ptp* 2>/dev/null || true)
[[ -n "$ptp_path" ]] || { echo "[FAIL] No PHC device"; exit 1; }
phc="/dev/$(basename "$ptp_path")"
echo "[PASS] PHC device: $phc"

echo "[INFO] If ptp4l/phc2sys are running, tail logs:"
tail -n 5 /run/ptp/ptp4l-${iface}.log 2>/dev/null || true
tail -n 5 /run/ptp/phc2sys-${iface}.log 2>/dev/null || true

exit 0


