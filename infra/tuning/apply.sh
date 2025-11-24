#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${script_dir}/config.sh"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Must run as root: sudo ${BASH_SOURCE[0]}" >&2
  exit 1
fi

echo "[INFO] Applying low-latency tuning..."

grub_backup() {
  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  if [[ -f "${GRUB_FILE}" ]]; then
    cp -n "${GRUB_FILE}" "${GRUB_FILE}.lowlatency.bak-${ts}" || true
    echo "[OK] Backed up GRUB to ${GRUB_FILE}.lowlatency.bak-${ts}"
  fi
}

ensure_grub_var() {
  local var="$1"
  if ! grep -qE "^${var}=" "${GRUB_FILE}"; then
    echo "${var}=\"\"" >>"${GRUB_FILE}"
  fi
}

merge_cmdline_args() {
  local var="GRUB_CMDLINE_LINUX_DEFAULT"
  ensure_grub_var "${var}"
  local current
  current="$(sed -nE "s/^${var}=\"(.*)\"/\1/p" "${GRUB_FILE}")"
  local new="$current"
  shift || true
  for arg in "$@"; do
    [[ -z "$arg" ]] && continue
    if [[ "$new" != *"$arg"* ]]; then
      new+=" $arg"
    fi
  done
  new="${new## }"; new="${new%% }"
  # shellcheck disable=SC2001
  local escaped
  escaped="$(printf '%s' "$new" | sed -e 's/[\&/]/\\&/g')"
  sed -i -E "s|^${var}=\".*\"|${var}=\"${escaped}\"|" "${GRUB_FILE}"
  echo "[OK] Updated ${var}"
}

build_kernel_args() {
  local args=()
  local isol="$ISOL_CPUS" nohz="$NOHZ_FULL_CPUS" rcu="$RCU_NOCBS_CPUS"
  if [[ -n "$isol" ]]; then
    args+=("isolcpus=${isol}")
    [[ -z "$nohz" ]] && nohz="$isol"
    [[ -z "$rcu" ]] && rcu="$isol"
  fi
  [[ -n "$nohz" ]] && args+=("nohz_full=${nohz}")
  [[ -n "$rcu" ]] && args+=("rcu_nocbs=${rcu}")
  # Persist hugepages at boot if requested in config
  if [[ -n "${HUGEPAGES_2M}" && "${HUGEPAGES_2M}" != "0" ]]; then
    args+=("hugepagesz=2M" "hugepages=${HUGEPAGES_2M}")
  fi
  if [[ -n "${HUGEPAGES_1G}" && "${HUGEPAGES_1G}" != "0" ]]; then
    # Some kernels require specifying 1G first; still append both tokens
    args+=("default_hugepagesz=1G" "hugepagesz=1G" "hugepages=${HUGEPAGES_1G}")
  fi
  args+=("idle=poll" "processor.max_cstate=0" "intel_pstate=disable")
  printf '%s\n' "${args[@]}"
}

install_sysctl() {
  install -D -m 0644 "${script_dir}/sysctl.d/90-lowlatency.conf" "${SYSCTL_DROPIN}"
  sysctl --system >/dev/null || true
  echo "[OK] Installed sysctl drop-in"
}

install_systemd_service() {
  install -D -m 0644 "${script_dir}/systemd/disable-cstates.service" "${SYSTEMD_SERVICE}"
  systemctl daemon-reload
  systemctl enable --now disable-cstates.service || true
  echo "[OK] Enabled systemd governor service"
}

apply_hugepages() {
  "${script_dir}/hugepages.sh" apply || true
}

install_hugetlbfs_fstab() {
  mkdir -p "${HUGEPAGES_MOUNT}"
  getent group hugepages >/dev/null 2>&1 || groupadd -f hugepages || true
  if grep -qE "[[:space:]]${HUGEPAGES_MOUNT}[[:space:]].*hugetlbfs" /etc/fstab; then
    sed -i -E "s|^([^#].*[[:space:]]${HUGEPAGES_MOUNT}[[:space:]]hugetlbfs).*$|hugetlbfs ${HUGEPAGES_MOUNT} hugetlbfs mode=1770,gid=hugepages,pagesize=2M 0 0|" /etc/fstab
  else
    echo "hugetlbfs ${HUGEPAGES_MOUNT} hugetlbfs mode=1770,gid=hugepages,pagesize=2M 0 0" >> /etc/fstab
  fi
  mount -a || true
  echo "[OK] Ensured hugetlbfs fstab entry at ${HUGEPAGES_MOUNT}"
}

update_grub_cfg() {
  if command -v update-grub >/dev/null 2>&1; then
    update-grub >/dev/null
  elif command -v grub-mkconfig >/dev/null 2>&1; then
    grub-mkconfig -o /boot/grub/grub.cfg >/dev/null
  fi
  echo "[OK] Regenerated GRUB config (reboot required)"
}

# -- main --
grub_backup
touch "${GRUB_FILE}"
mapfile -t kargs < <(build_kernel_args)
merge_cmdline_args GRUB_CMDLINE_LINUX_DEFAULT "${kargs[@]}"

install_sysctl
install_systemd_service
apply_hugepages
install_hugetlbfs_fstab
update_grub_cfg

echo "[DONE] Low-latency tuning applied. Please reboot and run infra/tuning/verify.sh."


