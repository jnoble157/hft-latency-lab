#!/bin/bash
# Automated latency testing script for neuro-hft-fpga
# Runs tests at multiple packet rates and generates analysis reports

set -e

# Configuration
PYNQ_HOST="192.168.10.2"
PYNQ_USER="xilinx"
PYNQ_VENV="/usr/local/share/pynq-venv/bin/python3"
BITSTREAM_PATH="/home/xilinx/feature_overlay.bit"
SERVER_SCRIPT="/home/xilinx/feature_echo_mt.py"

# Test parameters
RATES=(10 50 100)
PACKETS_PER_TEST=1000
OUTPUT_DIR="latency_results_$(date +%Y%m%d_%H%M%S)"

echo "=========================================="
echo "Latency Testing Suite"
echo "=========================================="
echo "Output directory: $OUTPUT_DIR"
echo "Tests to run: ${RATES[@]} Hz"
echo "Packets per test: $PACKETS_PER_TEST"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to check if PYNQ is reachable
check_pynq() {
    echo "Checking PYNQ connectivity..."
    if ping -c 1 -W 2 $PYNQ_HOST > /dev/null 2>&1; then
        echo "✓ PYNQ is reachable at $PYNQ_HOST"
        return 0
    else
        echo "✗ Cannot reach PYNQ at $PYNQ_HOST"
        return 1
    fi
}

# Function to start server on PYNQ
start_pynq_server() {
    echo ""
    echo "Starting PYNQ server with timing enabled..."
    
    # Kill any existing servers
    ssh ${PYNQ_USER}@${PYNQ_HOST} "sudo pkill -9 -f feature_echo" 2>/dev/null || true
    sleep 1
    
    # Start server in background with timing enabled
    ssh ${PYNQ_USER}@${PYNQ_HOST} \
        "sudo -E env PYNQ_XRT=0 nohup ${PYNQ_VENV} -u ${SERVER_SCRIPT} \
        --bit ${BITSTREAM_PATH} \
        --dma axi_dma_0 \
        --enable-timing \
        --log-interval 5 \
        > /tmp/feature_echo.log 2>&1 &"
    
    # Wait for server to start
    echo "Waiting for server to initialize..."
    sleep 3
    
    # Check if server is running
    if ssh ${PYNQ_USER}@${PYNQ_HOST} "pgrep -f feature_echo" > /dev/null; then
        echo "✓ PYNQ server started successfully"
        return 0
    else
        echo "✗ Failed to start PYNQ server"
        ssh ${PYNQ_USER}@${PYNQ_HOST} "tail -20 /tmp/feature_echo.log"
        return 1
    fi
}

# Function to stop server on PYNQ
stop_pynq_server() {
    echo ""
    echo "Stopping PYNQ server..."
    ssh ${PYNQ_USER}@${PYNQ_HOST} "sudo pkill -2 -f feature_echo" 2>/dev/null || true
    sleep 1
}

# Function to run a single test
run_test() {
    local rate=$1
    local csv_file="$OUTPUT_DIR/latency_${rate}hz.csv"
    
    echo ""
    echo "=========================================="
    echo "Running test at $rate Hz"
    echo "=========================================="
    
    # Run test
    python3 test_lob_stream.py $rate \
        --log-csv "$csv_file" \
        --max-packets $PACKETS_PER_TEST
    
    # Check if CSV was created
    if [ -f "$csv_file" ]; then
        local lines=$(wc -l < "$csv_file")
        echo "✓ Test completed: $lines data points logged to $csv_file"
        
        # Generate analysis
        echo "Generating analysis..."
        python3 analyze_latency.py "$csv_file" \
            --outdir "$OUTPUT_DIR/${rate}hz" \
            --summary "$OUTPUT_DIR/${rate}hz_summary.txt"
        
        return 0
    else
        echo "✗ Test failed: no data logged"
        return 1
    fi
}

# Main execution
main() {
    # Pre-flight checks
    if ! check_pynq; then
        echo "Error: Cannot reach PYNQ. Check network configuration."
        exit 1
    fi
    
    # Start PYNQ server
    if ! start_pynq_server; then
        echo "Error: Failed to start PYNQ server"
        exit 1
    fi
    
    # Run tests at each rate
    local failed=0
    for rate in "${RATES[@]}"; do
        if ! run_test $rate; then
            echo "Warning: Test at $rate Hz failed"
            failed=$((failed + 1))
        fi
        
        # Cool-down between tests
        if [ $rate != ${RATES[-1]} ]; then
            echo ""
            echo "Cooling down for 5 seconds..."
            sleep 5
        fi
    done
    
    # Stop server
    stop_pynq_server
    
    # Generate combined report
    echo ""
    echo "=========================================="
    echo "Generating combined report..."
    echo "=========================================="
    
    {
        echo "Latency Test Report"
        echo "==================="
        echo "Date: $(date)"
        echo "Test Configuration:"
        echo "  - Packet rates: ${RATES[@]} Hz"
        echo "  - Packets per test: $PACKETS_PER_TEST"
        echo ""
        
        for rate in "${RATES[@]}"; do
            local summary_file="$OUTPUT_DIR/${rate}hz_summary.txt"
            if [ -f "$summary_file" ]; then
                echo ""
                echo "--- $rate Hz Test Results ---"
                cat "$summary_file"
            fi
        done
    } > "$OUTPUT_DIR/REPORT.txt"
    
    echo "✓ Combined report saved to $OUTPUT_DIR/REPORT.txt"
    
    # Summary
    echo ""
    echo "=========================================="
    echo "Test Suite Complete"
    echo "=========================================="
    echo "Results directory: $OUTPUT_DIR"
    echo "Tests run: ${#RATES[@]}"
    echo "Tests failed: $failed"
    echo ""
    echo "View results:"
    echo "  cat $OUTPUT_DIR/REPORT.txt"
    echo "  ls $OUTPUT_DIR/"
    echo ""
    
    if [ $failed -eq 0 ]; then
        echo "✓ All tests passed!"
        return 0
    else
        echo "⚠ Some tests failed"
        return 1
    fi
}

# Run main function
main

