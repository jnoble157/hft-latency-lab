#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Run as root" >&2; exit 1
fi

for f in /run/ptp/ptp4l.pid /run/ptp/phc2sys.pid; do
  if [[ -f "$f" ]]; then
    pid=$(cat "$f" || true)
    [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
    rm -f "$f"
  fi
done

echo "[OK] Stopped ptp4l/phc2sys"


