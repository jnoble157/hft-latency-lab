#!/usr/bin/make -f

# neuro-hft-fpga Makefile
#
# Quick reference:
#   make deploy          - Copy bitstream to Pynq
#   make validate        - End-to-end smoke test (100 packets)
#   make validate-quick  - Quick test (assumes server running)
#   make latency-test    - Full multi-rate latency measurement
#   make tune/untune     - System latency tuning


ROOT := $(CURDIR)
PYNQ_IP ?= 192.168.10.2
PYNQ_USER ?= xilinx
SSH ?= ssh
SCP ?= scp
SUDO ?= sudo

VIVADO_PROJ := $(ROOT)/fpga/feature_pipe/vivado/vivado_proj
BUILD_DIR   := $(ROOT)/fpga/feature_pipe/vivado/build
BIT_DEFAULT := $(VIVADO_PROJ)/feature_overlay.runs/impl_1/overlay_wrapper.bit
HWH_DEFAULT := $(VIVADO_PROJ)/feature_overlay.gen/sources_1/bd/overlay/hw_handoff/overlay.hwh

# ============================================================================
# FPGA Build & Deploy
# ============================================================================

.PHONY: reports
reports:
	@mkdir -p $(BUILD_DIR)
	vivado -mode batch -source fpga/feature_pipe/vivado/scripts/report.tcl
	@echo "Reports written to $(BUILD_DIR)"

.PHONY: deploy
deploy:
	@echo "Deploying overlay to $(PYNQ_USER)@$(PYNQ_IP)"
	$(SCP) $(BIT_DEFAULT) $(PYNQ_USER)@$(PYNQ_IP):/home/$(PYNQ_USER)/feature_overlay.bit
	$(SCP) $(HWH_DEFAULT) $(PYNQ_USER)@$(PYNQ_IP):/home/$(PYNQ_USER)/feature_overlay.hwh
	@echo "✓ Deployed"

# ============================================================================
# PYNQ Server Control
# ============================================================================

.PHONY: echo-start
echo-start:
	@echo "Starting PYNQ server at $(PYNQ_IP):4000"
	$(SSH) $(PYNQ_USER)@$(PYNQ_IP) 'sudo -n /usr/bin/pkill -f "[p]ython3 .*feature_echo_mt.py" || true'
	$(SSH) $(PYNQ_USER)@$(PYNQ_IP) 'nohup sudo -E env PYNQ_XRT=0 /usr/local/share/pynq-venv/bin/python3 -u /home/$(PYNQ_USER)/feature_echo_mt.py --bit /home/$(PYNQ_USER)/feature_overlay.bit --dma axi_dma_0 --enable-timing > /tmp/feature_echo.log 2>&1 &'
	@sleep 2
	@echo "✓ Server started (check with 'make echo-status')"

.PHONY: echo-stop
echo-stop:
	@echo "Stopping PYNQ server"
	$(SSH) $(PYNQ_USER)@$(PYNQ_IP) 'sudo -n /usr/bin/pkill -f "[p]ython3 .*feature_echo_mt.py" || true'
	@echo "✓ Server stopped"

.PHONY: echo-status
echo-status:
	@echo "=== PYNQ Server Status ==="
	$(SSH) $(PYNQ_USER)@$(PYNQ_IP) 'pgrep -fa "feature_echo_mt.py" || echo "Not running"; /usr/bin/ss -uln | grep ":4000" || echo "Not listening on :4000"; echo ""; echo "=== Recent logs ==="; tail -n 20 /tmp/feature_echo.log 2>/dev/null || echo "No logs"'

# ============================================================================
# Validation & Testing
# ============================================================================

.PHONY: validate
validate: deploy echo-start
	@echo ""
	@echo "=== Running end-to-end smoke test ==="
	@echo "Waiting for server to bind..."
	@sleep 3
	@echo "Sending 100 packets at 100 Hz..."
	python3 $(ROOT)/host/udp/test_lob_stream.py 100 --max-packets 100
	@echo ""
	@echo "✓ Validation complete"

.PHONY: validate-quick
validate-quick:
	@echo "=== Quick validation (assumes server running) ==="
	python3 $(ROOT)/host/udp/test_lob_stream.py 100 --max-packets 100

.PHONY: latency-test
latency-test:
	@echo "=== Full latency measurement (50/100/125 Hz) ==="
	@echo "This will take several minutes..."
	cd $(ROOT)/host/udp && ./run_latency_tests.sh
	@echo "✓ Results in latency_analysis/"

# ============================================================================
# System Tuning & Infrastructure
# ============================================================================

.PHONY: tune untune verify-tune

tune:
	$(SUDO) infra/tuning/apply.sh

untune:
	$(SUDO) infra/tuning/revert.sh

verify-tune:
	infra/tuning/verify.sh

.PHONY: dpdk-bind dpdk-unbind ptp-start ptp-stop

dpdk-bind:
	@test -n "$(PCI)" || (echo "Usage: make dpdk-bind PCI=0000:05:00.0 DRIVER=vfio-pci" && exit 1)
	$(SUDO) infra/dpdk/bind.sh $(PCI) --driver=$(or $(DRIVER),vfio-pci)

dpdk-unbind:
	@test -n "$(PCI)" || (echo "Usage: make dpdk-unbind PCI=0000:05:00.0 DRIVER=i40e" && exit 1)
	$(SUDO) infra/dpdk/unbind.sh $(PCI) --driver=$(or $(DRIVER),i40e)

ptp-start:
	@test -n "$(IF)" || (echo "Usage: make ptp-start IF=eth0" && exit 1)
	$(SUDO) infra/ptp/ptp-start.sh $(IF) $(or $(PROFILE),oc)

ptp-stop:
	$(SUDO) infra/ptp/ptp-stop.sh
