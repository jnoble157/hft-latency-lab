#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "${script_dir}/config.sh"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Must run as root: sudo ${BASH_SOURCE[0]}" >&2
  exit 1
fi

echo "[INFO] Reverting low-latency tuning..."

restore_grub() {
  local latest
  latest="$(ls -1t "${GRUB_FILE}".lowlatency.bak-* 2>/dev/null | head -n1 || true)"
  if [[ -n "$latest" && -f "$latest" ]]; then
    cp -f "$latest" "${GRUB_FILE}"
    echo "[OK] Restored GRUB from backup: $latest"
  else
    echo "[WARN] No GRUB backup found; leaving ${GRUB_FILE} as-is"
  fi
  if command -v update-grub >/dev/null 2>&1; then
    update-grub >/dev/null
  elif command -v grub-mkconfig >/dev/null 2>&1; then
    grub-mkconfig -o /boot/grub/grub.cfg >/dev/null
  fi
}

remove_sysctl() {
  rm -f "${SYSCTL_DROPIN}" || true
  sysctl --system >/dev/null || true
  echo "[OK] Removed sysctl drop-in"
}

remove_systemd_service() {
  systemctl disable --now disable-cstates.service >/dev/null 2>&1 || true
  rm -f "${SYSTEMD_SERVICE}" || true
  systemctl daemon-reload
  echo "[OK] Removed systemd governor service"
}

# Optional: clear hugepages by setting counts to 0 (comment if undesired)
clear_hugepages() {
  HUGEPAGES_2M="0" HUGEPAGES_1G="0" "${script_dir}/hugepages.sh" apply || true
}

restore_grub
remove_sysctl
remove_systemd_service
clear_hugepages || true

echo "[DONE] Revert complete. Please reboot to fully undo kernel cmdline changes."


