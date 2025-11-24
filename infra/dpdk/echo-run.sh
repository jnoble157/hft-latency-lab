#!/usr/bin/env bash
set -euo pipefail

# Usage: infra/dpdk/echo-run.sh <pci0> <pci1> [lcores]

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
root_dir="$(cd "${script_dir}/../.." && pwd)"

pci0="${1:-}"
pci1="${2:-}"
lcores="${3:-4,5}"

if [[ -z "$pci0" || -z "$pci1" ]]; then
  echo "[USAGE] ${BASH_SOURCE[0]} <pci0> <pci1> [lcores]" >&2
  exit 2
fi

make -C "${root_dir}/host/dpdk/echo-io" -s

sudo "${root_dir}/host/dpdk/echo-io/echo-io" \
  -l "$lcores" -n 4 -a "$pci0" -a "$pci1"


