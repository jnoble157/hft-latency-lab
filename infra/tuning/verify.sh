#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${script_dir}/config.sh"

pass=true

check_cmdline_contains() {
  local key="$1" val="$2"
  [[ -z "$val" ]] && return 0
  if grep -q "${key}=${val}" /proc/cmdline; then
    echo "[PASS] /proc/cmdline has ${key}=${val}"
  else
    echo "[FAIL] Missing ${key}=${val} in /proc/cmdline"; pass=false
  fi
}

trim() { sed -e 's/^ *//' -e 's/ *$//'; }

check_governor() {
  local any=0 bad=0
  for gov in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    [[ -f "$gov" ]] || continue
    any=1
    if [[ "$(cat "$gov" | tr -d '\n' | trim)" == "performance" ]]; then
      :
    else
      echo "[WARN] Governor not performance: $gov -> $(cat "$gov")"; bad=1
    fi
  done
  if [[ $any -eq 0 ]]; then
    echo "[WARN] No cpufreq governors exposed; skipping governor check"
  elif [[ $bad -eq 0 ]]; then
    echo "[PASS] CPU governors set to performance"
  fi
}

check_hugepages() {
  local ok=1
  if [[ -n "$HUGEPAGES_2M" && "$HUGEPAGES_2M" != "0" ]]; then
    local cur2m
    cur2m=$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages 2>/dev/null || echo 0)
    if [[ "$cur2m" == "$HUGEPAGES_2M" ]]; then
      echo "[PASS] 2M hugepages = $cur2m"
    else
      echo "[FAIL] 2M hugepages = $cur2m (expected $HUGEPAGES_2M)"; ok=0
    fi
  fi
  if [[ -n "$HUGEPAGES_1G" && "$HUGEPAGES_1G" != "0" ]]; then
    local cur1g
    cur1g=$(cat /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages 2>/dev/null || echo 0)
    if [[ "$cur1g" == "$HUGEPAGES_1G" ]]; then
      echo "[PASS] 1G hugepages = $cur1g"
    else
      echo "[FAIL] 1G hugepages = $cur1g (expected $HUGEPAGES_1G)"; ok=0
    fi
  fi
  if mount | grep -q " on ${HUGEPAGES_MOUNT} type hugetlbfs"; then
    echo "[PASS] hugetlbfs mounted at ${HUGEPAGES_MOUNT}"
  else
    echo "[FAIL] hugetlbfs not mounted at ${HUGEPAGES_MOUNT}"; ok=0
  fi
  [[ $ok -eq 1 ]] || pass=false
}

check_cmdline_contains isolcpus "$ISOL_CPUS"
check_cmdline_contains nohz_full "$NOHZ_FULL_CPUS"
check_cmdline_contains rcu_nocbs "$RCU_NOCBS_CPUS"
check_governor
check_hugepages

$pass && { echo "[DONE] Verification passed"; exit 0; } || { echo "[DONE] Verification failed"; exit 1; }


