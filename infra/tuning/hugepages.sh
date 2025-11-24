#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${script_dir}/config.sh"

mode="${1:-apply}"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Must run as root: sudo ${BASH_SOURCE[0]} ${mode}" >&2
  exit 1
fi

ensure_mount() {
  mkdir -p "${HUGEPAGES_MOUNT}"
  if ! mount | grep -q " on ${HUGEPAGES_MOUNT} type hugetlbfs"; then
    mount -t hugetlbfs nodev "${HUGEPAGES_MOUNT}" || true
    echo "[OK] Mounted hugetlbfs at ${HUGEPAGES_MOUNT}"
  else
    echo "[OK] hugetlbfs already mounted at ${HUGEPAGES_MOUNT}"
  fi
}

set_counts() {
  local two_m one_g
  two_m="${HUGEPAGES_2M:-0}"; one_g="${HUGEPAGES_1G:-0}"
  if [[ "$mode" == "apply" ]]; then
    : # use configured values
  elif [[ "$mode" == "clear" ]]; then
    two_m=0; one_g=0
  fi
  if [[ -d /sys/kernel/mm/hugepages/hugepages-2048kB ]]; then
    echo "$two_m" > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages || true
    echo "[OK] Set 2M hugepages: $two_m"
  fi
  if [[ -d /sys/kernel/mm/hugepages/hugepages-1048576kB ]]; then
    echo "$one_g" > /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages || true
    echo "[OK] Set 1G hugepages: $one_g"
  fi
}

ensure_mount
set_counts


