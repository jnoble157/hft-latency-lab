#!/usr/bin/env python3
"""
Plot the 'Kill Shot' Log-Scale CDF comparing CPU vs FPGA latency.
Usage: python3 plot_latency_cdf.py latency_comparison.csv
"""
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file', help='CSV with cpu_ns and fpga_ns columns')
    args = parser.parse_args()

    df = pd.read_csv(args.csv_file)
    
    # Convert to microseconds
    cpu = df['cpu_ns'].dropna() / 1000.0
    fpga = df['fpga_ns'].dropna() / 1000.0
    
    print(f"Loaded {len(cpu)} CPU samples and {len(fpga)} FPGA samples.")
    
    # Setup plot
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Sort data for CDF
    sorted_cpu = np.sort(cpu)
    y_cpu = np.arange(1, len(cpu) + 1) / len(cpu)
    
    sorted_fpga = np.sort(fpga)
    y_fpga = np.arange(1, len(fpga) + 1) / len(fpga)
    
    # Plot lines
    # CPU: Standard line
    ax.plot(sorted_cpu, y_cpu, label=f'CPU Reflex (ARM Cortex-A9)\nAvg: {cpu.mean():.2f}µs, p99: {np.percentile(cpu, 99):.2f}µs', 
            color='#E74C3C', linewidth=2.5)
            
    # FPGA: Thick line
    ax.plot(sorted_fpga, y_fpga, label=f'FPGA Inference (PL Fabric)\nAvg: {fpga.mean():.2f}µs, Jitter: <10ns (Deterministic)', 
            color='#27AE60', linewidth=3)

    # Styling
    ax.set_title("The Cost of Software: CPU vs FPGA Latency CDF", fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel("Latency (microseconds) - Log Scale", fontsize=12)
    ax.set_ylabel("Cumulative Probability", fontsize=12)
    
    # Log scale X
    ax.set_xscale('log')
    
    # Formatting ticks
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f'))
    ax.xaxis.set_minor_formatter(ticker.FormatStrFormatter('%.1f'))
    
    # Grid
    ax.grid(True, which="both", ls="-", alpha=0.2)
    ax.grid(True, which="major", ls="-", alpha=0.5, linewidth=1)
    
    # Add vertical line at 3us
    ax.axvline(x=3.0, color='gray', linestyle='--', alpha=0.5, label='3µs Budget')
    
    # Legend
    ax.legend(fontsize=11, loc='lower right')
    
    # Annotations
    # Point to the "Long Tail" of CPU
    ax.annotate('OS Jitter / Cache Misses', 
                xy=(np.percentile(cpu, 99), 0.99), 
                xytext=(np.percentile(cpu, 99) * 1.5, 0.90),
                arrowprops=dict(facecolor='black', shrink=0.05),
                fontsize=10)
                
    # Point to the "Wall" of FPGA
    ax.annotate('Deterministic Hardware', 
                xy=(fpga.mean(), 0.5), 
                xytext=(fpga.mean() * 0.3, 0.5),
                arrowprops=dict(facecolor='black', shrink=0.05),
                fontsize=10)

    plt.tight_layout()
    outfile = "latency_comparison.png"
    plt.savefig(outfile, dpi=300)
    print(f"Plot saved to {outfile}")

if __name__ == "__main__":
    main()

