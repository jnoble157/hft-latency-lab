Low-latency Linux tuning scripts

Usage:
1) Edit `infra/tuning/config.sh` to set CPU sets and hugepage counts
2) Apply changes (requires sudo):
   - `sudo infra/tuning/apply.sh`
3) Reboot for GRUB kernel args to take effect
4) Verify after reboot:
   - `infra/tuning/verify.sh`

Revert (requires sudo):
- `sudo infra/tuning/revert.sh` then reboot

Notes:
- Scripts are idempotent and safe to re-run
- GRUB file is backed up before modification
- Hugepages mount at `/dev/hugepages` is respected if already present


