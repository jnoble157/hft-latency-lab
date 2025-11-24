#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
source "${repo_root}/infra/tuning/config.sh"

if [[ -z "$ISOL_CPUS" ]]; then
  echo "[WARN] ISOL_CPUS not set in config.sh. Nothing to verify."; exit 0
fi

echo "[INFO] Checking for kthreads on isolated CPUs: ${ISOL_CPUS}"
ps -eLo pid,psr,cls,rtprio,pri,ni,comm | awk -v set="${ISOL_CPUS}" '
BEGIN{split(set,a,/,/);for(i in a){if(a[i]~/-/){split(a[i],r,/-/);for(j=r[1];j<=r[2];j++)iso[j]=1}else{iso[a[i]]=1}}}
NR>1{cpu=$2; if(iso[cpu] && $7 ~ /^k.*/){print "[WARN] kthread on isolated CPU:",$0}}'
echo "[INFO] Inspect /proc/interrupts for IRQs landing on isolated CPUs"
cat /proc/interrupts | sed -n '1,5p' && grep -nE ":" /proc/interrupts | head -n 20

echo "[NOTE] Use infra/tuning/irq_affinity.sh <iface> to steer IRQs if needed."


