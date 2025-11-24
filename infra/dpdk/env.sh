#!/usr/bin/env bash
set -euo pipefail

# Locate dpdk-devbind.py and testpmd binaries

find_devbind() {
  for p in \
    /usr/local/share/dpdk/usertools/dpdk-devbind.py \
    /usr/share/dpdk/usertools/dpdk-devbind.py \
    $(command -v dpdk-devbind.py 2>/dev/null || true)
  do
    [[ -n "$p" && -x "$p" ]] && echo "$p" && return 0
  done
  echo ""; return 1
}

find_testpmd() {
  for b in dpdk-testpmd testpmd; do
    if command -v "$b" >/dev/null 2>&1; then echo "$b"; return 0; fi
  done
  echo ""; return 1
}

export DPDK_DEVBIND="${DPDK_DEVBIND:-$(find_devbind || true)}"
export DPDK_TESTPMD="${DPDK_TESTPMD:-$(find_testpmd || true)}"

if [[ -z "${DPDK_DEVBIND}" ]]; then
  echo "[WARN] dpdk-devbind.py not found. Bind scripts will fallback to sysfs."
fi
if [[ -z "${DPDK_TESTPMD}" ]]; then
  echo "[WARN] dpdk testpmd not found. Install dpdk packages (dpdk, dpdk-dev)."
fi


