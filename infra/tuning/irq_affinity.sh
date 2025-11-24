#!/usr/bin/env bash
set -euo pipefail

# Pin NIC/MSI-X IRQs away from isolated CPUs.
# Usage: sudo ./irq_affinity.sh <iface-or-pci-identifier>

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${script_dir}/config.sh"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Must run as root: sudo ${BASH_SOURCE[0]} <iface-or-pci>" >&2
  exit 1
fi

target="${1:-}"
if [[ -z "$target" ]]; then
  echo "[USAGE] sudo ${BASH_SOURCE[0]} <iface-or-pci>" >&2
  exit 2
fi

# Build CPU list for IRQs: prefer NON_ISOL_IRQ_CPUS, else infer complement of ISOL_CPUS
cpu_list_for_irqs() {
  if [[ -n "${NON_ISOL_IRQ_CPUS}" ]]; then
    printf '%s\n' "${NON_ISOL_IRQ_CPUS}"
    return 0
  fi
  if [[ -z "${ISOL_CPUS}" ]]; then
    # fallback: all CPUs
    awk -F: '/^processor/{print $2}' /proc/cpuinfo | sort -n | paste -sd, -
    return 0
  fi
  # derive complement using Python (easier ranges)
  python3 - "$ISOL_CPUS" <<'PY'
import os,sys
isol=sys.argv[1]
def expand(s):
  out=set()
  for part in s.split(','):
    if '-' in part:
      a,b=part.split('-'); out.update(range(int(a),int(b)+1))
    else:
      out.add(int(part))
  return sorted(out)
all_cpus=list(range(os.cpu_count()))
isol=expand(isol)
rest=[c for c in all_cpus if c not in isol]
def compress(lst):
  if not lst: return ''
  ranges=[]; start=prev=lst[0]
  for x in lst[1:]:
    if x==prev+1: prev=x; continue
    ranges.append((start,prev)); start=prev=x
  ranges.append((start,prev))
  out=[]
  for a,b in ranges:
    out.append(str(a) if a==b else f"{a}-{b}")
  print(','.join(out))
compress(rest)
PY
}

affinity_list="$(cpu_list_for_irqs)"
echo "[INFO] Using IRQ CPU list: ${affinity_list}"

# Find IRQs related to interface or PCI id
grep -E "${target}" /proc/interrupts || true
mapfile -t irqs < <(grep -En "${target}" /proc/interrupts | awk -F: '{print $1}')
if [[ ${#irqs[@]} -eq 0 ]]; then
  echo "[WARN] No IRQs found matching '${target}' in /proc/interrupts" >&2
  exit 0
fi

for irq in "${irqs[@]}"; do
  irq=$(echo "$irq" | xargs)
  path="/proc/irq/${irq}/smp_affinity_list"
  if [[ -w "$path" ]]; then
    echo "$affinity_list" > "$path"
    echo "[OK] IRQ ${irq} -> CPUs ${affinity_list}"
  else
    echo "[WARN] Cannot write $path"
  fi
done


