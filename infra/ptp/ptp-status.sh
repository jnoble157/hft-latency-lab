#!/usr/bin/env bash
set -euo pipefail

# Usage: infra/ptp/ptp-status.sh <iface>

iface="${1:-}"
[[ -n "$iface" ]] || { echo "[USAGE] $0 <iface>"; exit 2; }

ptp_path=$(readlink -f "/sys/class/net/${iface}/device/ptp"/ptp* 2>/dev/null || true)
if [[ -z "$ptp_path" ]]; then
  echo "[ERR] No PHC for ${iface}"; exit 3
fi
phc="/dev/$(basename "$ptp_path")"

echo "[INFO] Interface: $iface  PHC: $phc"
echo "[INFO] Timestamp caps:" && ethtool -T "$iface" || true

echo "[INFO] Recent ptp4l log lines:" && tail -n 10 /run/ptp/ptp4l-${iface}.log 2>/dev/null || true
echo "[INFO] Recent phc2sys log lines:" && tail -n 10 /run/ptp/phc2sys-${iface}.log 2>/dev/null || true

if command -v pmc >/dev/null 2>&1; then
  echo "[INFO] pmc query (clock status):" && pmc -u -b 0 'GET TIME_STATUS_NP' || true
fi


