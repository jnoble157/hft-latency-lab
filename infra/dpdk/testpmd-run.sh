#!/usr/bin/env bash
set -euo pipefail

# Usage: infra/dpdk/testpmd-run.sh <pci0> <pci1> [duration_sec]

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
root_dir="$(cd "${script_dir}/../.." && pwd)"
source "${script_dir}/env.sh"
source "${root_dir}/infra/tuning/config.sh"

pci0="${1:-}"
pci1="${2:-}"
duration="${3:-60}"

if [[ -z "${DPDK_TESTPMD}" ]]; then
  echo "[ERROR] dpdk testpmd not found. Install dpdk packages." >&2
  exit 1
fi

if [[ -z "$pci0" || -z "$pci1" ]]; then
  echo "[USAGE] ${BASH_SOURCE[0]} <pci0> <pci1> [duration_sec]" >&2
  exit 2
fi

expand_cpulist() {
  python3 - "$1" <<'PY'
import sys
def expand(s):
  out=[]
  for p in s.split(','):
    if '-' in p:
      a,b=p.split('-'); out+=list(range(int(a),int(b)+1))
    elif p.strip():
      out.append(int(p))
  print(' '.join(map(str,out)))
expand(sys.argv[1])
PY
}

# choose first two isolated CPUs
cpus=( )
if [[ -n "${ISOL_CPUS}" ]]; then
  read -r -a cpus <<<"$(expand_cpulist "${ISOL_CPUS}")"
fi
if [[ ${#cpus[@]} -lt 2 ]]; then
  echo "[WARN] Not enough isolated CPUs; falling back to 2 default CPUs"
  cpus=(4 5)
fi
lcores="${cpus[0]},${cpus[1]}"

echo "[INFO] Running testpmd on lcores ${lcores} with ports ${pci0}, ${pci1} for ${duration}s"

cmd=("${DPDK_TESTPMD}" \
  -l "${lcores}" -n 4 \
  -a "${pci0}" -a "${pci1}" \
  --file-prefix x710 --log-level=pmd.net.i40e:notice \
  -- \
  --nb-cores=1 --rxq=1 --txq=1 --rxd=1024 --txd=1024 \
  --port-topology=chained --forward-mode=io --auto-start \
  --stats-period=1 --disable-link-check)

"${cmd[@]}" &
pid=$!
sleep "${duration}" || true
kill -INT "$pid" >/dev/null 2>&1 || true
wait "$pid" || true


