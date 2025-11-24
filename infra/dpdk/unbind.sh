#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${script_dir}/env.sh"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Must run as root: sudo ${BASH_SOURCE[0]} <pci> [<pci> ...] [--driver=i40e]" >&2
  exit 1
fi

driver="i40e"
args=()
for a in "$@"; do
  case "$a" in
    --driver=*) driver="${a#--driver=}" ;;
    *) args+=("$a") ;;
  esac
done

if [[ ${#args[@]} -lt 1 ]]; then
  echo "[USAGE] sudo ${BASH_SOURCE[0]} 0000:05:00.0 [0000:05:00.1] [--driver=i40e]" >&2
  exit 2
fi

modprobe "$driver" || true

unbind_sysfs() {
  local pci="$1"
  local devpath="/sys/bus/pci/devices/${pci}"
  [[ -e "$devpath" ]] || { echo "[ERR] ${pci} not found"; return 1; }
  if [[ -e "$devpath/driver/unbind" ]]; then echo "$pci" >"$devpath/driver/unbind"; fi
  echo "$driver" >"$devpath/driver_override"
  echo "$pci" >"/sys/bus/pci/drivers/${driver}/bind"
}

for pci in "${args[@]}"; do
  if [[ -n "${DPDK_DEVBIND}" ]]; then
    "${DPDK_DEVBIND}" --bind "$driver" "$pci"
  else
    unbind_sysfs "$pci"
  fi
  echo "[OK] Rebound ${pci} to ${driver}"
done

if [[ -n "${DPDK_DEVBIND}" ]]; then
  "${DPDK_DEVBIND}" --status
fi


