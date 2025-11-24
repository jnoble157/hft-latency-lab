#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
source "${repo_root}/infra/tuning/config.sh"

ok=1

echo "[INFO] Hugepages status:"
grep -H . /sys/kernel/mm/hugepages/hugepages-*/nr_hugepages || true

if mount | grep -q " on ${HUGEPAGES_MOUNT} type hugetlbfs"; then
  echo "[PASS] hugetlbfs mounted at ${HUGEPAGES_MOUNT}"
else
  echo "[FAIL] hugetlbfs not mounted at ${HUGEPAGES_MOUNT}"; ok=0
fi

exit $ok


