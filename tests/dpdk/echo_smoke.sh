#!/usr/bin/env bash
set -euo pipefail

# Usage: tests/dpdk/echo_smoke.sh <pci0> <pci1> [seconds]

root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)"
pci0="${1:-}"; pci1="${2:-}"; dur="${3:-15}"

if [[ -z "$pci0" || -z "$pci1" ]]; then
  echo "[USAGE] ${BASH_SOURCE[0]} <pci0> <pci1> [seconds]" >&2
  exit 2
fi

set +e
timeout --preserve-status "${dur}" "${root_dir}/infra/dpdk/echo-run.sh" "$pci0" "$pci1"
code=$?
set -e

echo "[INFO] echo-io exited with code ${code}"
exit 0


