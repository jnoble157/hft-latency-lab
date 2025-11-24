#!/usr/bin/env bash
set -euo pipefail

# Quick sanity using cyclictest if available.
# Usage: ./tests/tuning/cyclictest_smoke.sh <cpu> [duration_sec]

cpu="${1:-0}"
dur="${2:-10}"

if ! command -v cyclictest >/dev/null 2>&1; then
  echo "[WARN] cyclictest not found. Install: sudo apt-get install -y rt-tests" >&2
  exit 0
fi

echo "[INFO] Running cyclictest on CPU ${cpu} for ${dur}s (rtprio=99)"
sudo cyclictest -q -p 99 -t1 -a "${cpu}" -i 1000 -m -N -D "${dur}"


