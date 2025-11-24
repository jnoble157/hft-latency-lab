#!/usr/bin/env python3
"""
Latency analysis script for neuro-hft-fpga system.
Reads CSV log from test_lob_stream.py and generates statistics + plots.
"""
import argparse
import csv
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend


def load_latency_data(csv_path):
    """Load latency CSV and return as numpy arrays."""
    data = {
        'seq': [], 't1_host_ns': [], 't5_host_ns': [], 'rtt_ns': [],
        't2_pynq_ns': [], 't3_pynq_ns': [], 't4_pynq_ns': [], 
        't5_pynq_ns': [], 't6_pynq_ns': [],
        'pynq_total_ns': [], 'dma_ns': [], 'net_est_ns': [],
        'ofi': [], 'imb_q15': [], 'burst_q16': [], 'vol_q16': []
    }
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in data.keys():
                val = row.get(key)
                if val == '' or val is None:
                    data[key].append(None)
                else:
                    try:
                        data[key].append(int(val) if key in ['seq', 'ofi', 'imb_q15', 'burst_q16', 'vol_q16'] or '_ns' in key else float(val))
                    except:
                        data[key].append(None)
    
    # Convert to numpy arrays, filtering out None values for numeric fields
    result = {}
    for key, values in data.items():
        if key in ['seq', 'ofi', 'imb_q15', 'burst_q16', 'vol_q16']:
            result[key] = np.array([v for v in values if v is not None])
        else:
            result[key] = np.array([v for v in values if v is not None], dtype=np.float64)
    
    return result


def compute_percentiles(data_ns, percentiles=[50, 90, 95, 99, 99.9]):
    """Compute percentiles for a latency metric in nanoseconds."""
    if len(data_ns) == 0:
        return {p: None for p in percentiles}
    return {p: np.percentile(data_ns, p) for p in percentiles}


def print_latency_summary(data, outfile=None):
    """Print latency statistics summary."""
    lines = []
    lines.append("=" * 80)
    lines.append("LATENCY SUMMARY")
    lines.append("=" * 80)
    lines.append(f"Total packets: {len(data['rtt_ns'])}")
    lines.append("")
    
    # RTT statistics
    if len(data['rtt_ns']) > 0:
        lines.append("Round-Trip Time (RTT):")
        rtt_us = data['rtt_ns'] / 1000.0
        pcts = compute_percentiles(rtt_us, [50, 90, 95, 99, 99.9])
        lines.append(f"  p50:  {pcts[50]:.2f} µs")
        lines.append(f"  p90:  {pcts[90]:.2f} µs")
        lines.append(f"  p95:  {pcts[95]:.2f} µs")
        lines.append(f"  p99:  {pcts[99]:.2f} µs")
        lines.append(f"  p999: {pcts[99.9]:.2f} µs")
        lines.append(f"  mean: {np.mean(rtt_us):.2f} µs")
        lines.append(f"  std:  {np.std(rtt_us):.2f} µs")
        lines.append("")
    
    # PYNQ processing time
    if len(data['pynq_total_ns']) > 0 and data['pynq_total_ns'][0] is not None:
        lines.append("PYNQ Total Processing Time:")
        pynq_us = data['pynq_total_ns'] / 1000.0
        pcts = compute_percentiles(pynq_us, [50, 90, 95, 99])
        lines.append(f"  p50:  {pcts[50]:.2f} µs")
        lines.append(f"  p90:  {pcts[90]:.2f} µs")
        lines.append(f"  p95:  {pcts[95]:.2f} µs")
        lines.append(f"  p99:  {pcts[99]:.2f} µs")
        lines.append(f"  mean: {np.mean(pynq_us):.2f} µs")
        lines.append("")
    
    # DMA time
    if len(data['dma_ns']) > 0 and data['dma_ns'][0] is not None:
        lines.append("DMA Processing Time (including PL):")
        dma_us = data['dma_ns'] / 1000.0
        pcts = compute_percentiles(dma_us, [50, 90, 95, 99])
        lines.append(f"  p50:  {pcts[50]:.2f} µs")
        lines.append(f"  p90:  {pcts[90]:.2f} µs")
        lines.append(f"  p95:  {pcts[95]:.2f} µs")
        lines.append(f"  p99:  {pcts[99]:.2f} µs")
        lines.append(f"  mean: {np.mean(dma_us):.2f} µs")
        lines.append("")
    
    # Network time estimate
    if len(data['net_est_ns']) > 0 and data['net_est_ns'][0] is not None:
        lines.append("Network Time (estimated by subtraction):")
        net_us = data['net_est_ns'] / 1000.0
        pcts = compute_percentiles(net_us, [50, 90, 95, 99])
        lines.append(f"  p50:  {pcts[50]:.2f} µs")
        lines.append(f"  p90:  {pcts[90]:.2f} µs")
        lines.append(f"  p95:  {pcts[95]:.2f} µs")
        lines.append(f"  p99:  {pcts[99]:.2f} µs")
        lines.append(f"  mean: {np.mean(net_us):.2f} µs")
        lines.append("")
    
    lines.append("=" * 80)
    
    output = '\n'.join(lines)
    print(output)
    
    if outfile:
        with open(outfile, 'w') as f:
            f.write(output)
        print(f"\nSummary written to {outfile}")


def plot_rtt_histogram(data, outdir):
    """Generate RTT histogram with percentile markers."""
    if len(data['rtt_ns']) == 0:
        print("No RTT data to plot")
        return
    
    rtt_us = data['rtt_ns'] / 1000.0
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Histogram
    n, bins, patches = ax.hist(rtt_us, bins=50, alpha=0.7, color='steelblue', edgecolor='black')
    
    # Percentile lines
    pcts = compute_percentiles(rtt_us, [50, 99, 99.9])
    colors = {'50': 'green', '99': 'orange', '99.9': 'red'}
    for p, val in pcts.items():
        if val is not None:
            label = f'p{int(p) if p == int(p) else p}: {val:.2f} µs'
            ax.axvline(val, color=colors.get(str(p), 'black'), linestyle='--', linewidth=2, label=label)
    
    ax.set_xlabel('Round-Trip Time (µs)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('RTT Histogram with Percentiles', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    outfile = Path(outdir) / 'rtt_histogram.png'
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()
    print(f"Saved: {outfile}")


def plot_latency_breakdown(data, outdir):
    """Generate stacked bar chart showing latency breakdown."""
    if len(data['pynq_total_ns']) == 0 or data['pynq_total_ns'][0] is None:
        print("No PYNQ timing data for breakdown plot")
        return
    
    # Compute mean times in microseconds
    rtt_mean = np.mean(data['rtt_ns']) / 1000.0
    pynq_mean = np.mean(data['pynq_total_ns']) / 1000.0
    dma_mean = np.mean(data['dma_ns']) / 1000.0
    net_mean = np.mean(data['net_est_ns']) / 1000.0
    
    # Breakdown components
    pynq_overhead = pynq_mean - dma_mean  # Python processing time on PYNQ
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Single stacked bar
    categories = ['End-to-End']
    network = [net_mean]
    pynq_proc = [pynq_overhead]
    dma_pl = [dma_mean]
    
    x = np.arange(len(categories))
    width = 0.5
    
    p1 = ax.bar(x, network, width, label=f'Network (~{net_mean:.1f} µs)', color='lightcoral')
    p2 = ax.bar(x, pynq_proc, width, bottom=network, label=f'PYNQ Overhead (~{pynq_overhead:.1f} µs)', color='lightskyblue')
    p3 = ax.bar(x, dma_pl, width, bottom=np.array(network)+np.array(pynq_proc), label=f'DMA+PL (~{dma_mean:.1f} µs)', color='lightgreen')
    
    ax.set_ylabel('Latency (µs)', fontsize=12)
    ax.set_title(f'Latency Breakdown (Total RTT: {rtt_mean:.1f} µs)', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.grid(True, axis='y', alpha=0.3)
    
    outfile = Path(outdir) / 'latency_breakdown.png'
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()
    print(f"Saved: {outfile}")


def plot_time_series(data, outdir):
    """Generate time series plot of RTT over packet sequence."""
    if len(data['rtt_ns']) == 0:
        print("No RTT data for time series")
        return
    
    rtt_us = data['rtt_ns'] / 1000.0
    seq = data['seq']
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.plot(seq, rtt_us, linewidth=0.5, alpha=0.7, color='steelblue')
    ax.set_xlabel('Packet Sequence Number', fontsize=12)
    ax.set_ylabel('Round-Trip Time (µs)', fontsize=12)
    ax.set_title('RTT Time Series', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Add p50 and p99 reference lines
    p50 = np.percentile(rtt_us, 50)
    p99 = np.percentile(rtt_us, 99)
    ax.axhline(p50, color='green', linestyle='--', linewidth=1, label=f'p50: {p50:.2f} µs', alpha=0.7)
    ax.axhline(p99, color='red', linestyle='--', linewidth=1, label=f'p99: {p99:.2f} µs', alpha=0.7)
    ax.legend()
    
    outfile = Path(outdir) / 'rtt_timeseries.png'
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()
    print(f"Saved: {outfile}")


def plot_latency_cdf(data, outdir):
    """Generate cumulative distribution function plot for RTT."""
    if len(data['rtt_ns']) == 0:
        print("No RTT data for CDF plot")
        return
    
    rtt_us = data['rtt_ns'] / 1000.0
    sorted_rtt = np.sort(rtt_us)
    cdf = np.arange(1, len(sorted_rtt) + 1) / len(sorted_rtt)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(sorted_rtt, cdf * 100, linewidth=2, color='steelblue')
    ax.set_xlabel('Round-Trip Time (µs)', fontsize=12)
    ax.set_ylabel('Cumulative Probability (%)', fontsize=12)
    ax.set_title('RTT Cumulative Distribution Function', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Mark key percentiles
    pcts = [50, 90, 95, 99, 99.9]
    for p in pcts:
        val = np.percentile(rtt_us, p)
        ax.plot(val, p, 'ro', markersize=6)
        ax.text(val, p + 1, f'p{int(p) if p == int(p) else p}', fontsize=9)
    
    outfile = Path(outdir) / 'rtt_cdf.png'
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()
    print(f"Saved: {outfile}")


def main():
    parser = argparse.ArgumentParser(description='Analyze latency measurements from test_lob_stream.py')
    parser.add_argument('csv_file', type=str, help='CSV file with latency data')
    parser.add_argument('--outdir', type=str, default='.', help='Output directory for plots and summary')
    parser.add_argument('--summary', type=str, default='summary.txt', help='Summary filename (saved in outdir)')
    args = parser.parse_args()
    
    # Create output directory
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Load data
    print(f"Loading data from {args.csv_file}...")
    data = load_latency_data(args.csv_file)
    
    # Print summary (place in output directory)
    summary_path = outdir / args.summary if args.summary else None
    print_latency_summary(data, summary_path)
    
    # Generate plots
    print("\nGenerating plots...")
    plot_rtt_histogram(data, outdir)
    plot_latency_breakdown(data, outdir)
    plot_time_series(data, outdir)
    plot_latency_cdf(data, outdir)
    
    print(f"\nAnalysis complete! Plots saved to {outdir}/")


if __name__ == '__main__':
    main()

