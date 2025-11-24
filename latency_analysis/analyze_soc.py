#!/usr/bin/env python3
"""
Host-side analysis for SoC latency experiments.

Consumes:
  - latency_analysis/latency_comparison.csv
      (from run_cycle_bench.py: CPU vs full FPGA lane, in ns)
  - latency_analysis/soc_full.log
  - latency_analysis/soc_mlp_only.log
  - latency_analysis/soc_nodma.log
  - latency_analysis/soc_core.log

Produces:
  - latency_analysis/plots/cdf_cpu_vs_fpga.png
  - latency_analysis/plots/soc_overlay_bar_avg_latency.png
  - latency_analysis/soc_summaries.csv   (parsed summary blocks from logs)
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
PLOTS_DIR = HERE / "plots"


@dataclass
class SummaryRecord:
    overlay: str          # full, mlp_only, nodma, core
    label: str            # raw header label from log (e.g. "delay_cycles=0 num_words=4 :: Fabric")
    metric: str           # short metric name (e.g. Fabric, MLP, MLP_only, MLP_timer)
    samples: int
    cycles_avg: float
    cycles_median: float
    cycles_min: int
    cycles_max: int
    cycles_stdev: float

    @property
    def latency_avg_ns(self) -> float:
        # 125 MHz fabric clock → 8 ns per cycle
        return self.cycles_avg * 8.0

    @property
    def latency_avg_us(self) -> float:
        return self.latency_avg_ns / 1e3


def load_latency_comparison(path: Path) -> tuple[np.ndarray, np.ndarray]:
    cpu_ns: List[int] = []
    fpga_ns: List[int] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = (row.get("cpu_ns") or "").strip()
            g = (row.get("fpga_ns") or "").strip()
            if c:
                try:
                    cpu_ns.append(int(c))
                except ValueError:
                    pass
            if g:
                try:
                    fpga_ns.append(int(g))
                except ValueError:
                    pass
    return np.array(cpu_ns, dtype=np.int64), np.array(fpga_ns, dtype=np.int64)


def plot_cdf_from_ns(
    samples_ns: np.ndarray,
    label: str,
    ax: plt.Axes,
    color: Optional[str] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Plot an empirical CDF for the given samples (in ns) on `ax`, returning the
    sorted x values (µs) and CDF y values. Caller can use this to annotate
    p50/p99 markers.
    """
    if samples_ns.size == 0:
        return np.array([]), np.array([])
    xs = np.sort(samples_ns.astype(np.float64)) / 1e3  # convert to microseconds
    ys = np.linspace(0.0, 1.0, xs.size, endpoint=False)
    ax.step(xs, ys, where="post", label=label, color=color)
    return xs, ys


def make_cpu_vs_fpga_cdf(latency_csv: Path) -> None:
    cpu_ns, fpga_ns = load_latency_comparison(latency_csv)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 4))

    cpu_x, _ = plot_cdf_from_ns(cpu_ns, "CPU reflex", ax, color="tab:blue")
    fpga_x, _ = plot_cdf_from_ns(fpga_ns, "FPGA full lane", ax, color="tab:orange")

    # Annotate p50 / p99 for each curve (if we have enough samples)
    def annotate_percentiles(samples: np.ndarray, label: str, color: str) -> None:
        if samples.size == 0:
            return
        p50, p99 = np.percentile(samples, [50, 99])
        for p, name, dy in [(p50, "p50", 0.02), (p99, "p99", -0.08)]:
            ax.axvline(p, color=color, alpha=0.25, linestyle="--", linewidth=1)
            ax.scatter([p], [0.5 if name == "p50" else 0.99], color=color, s=10)
            ax.text(
                p,
                0.5 + dy if name == "p50" else 0.99 + dy,
                f"{label} {name}\n{p:.0f} µs",
                color=color,
                fontsize=7,
                ha="center",
                va="center",
            )

    annotate_percentiles(cpu_x, "CPU", "tab:blue")
    annotate_percentiles(fpga_x, "FPGA", "tab:orange")

    # Use log-scale on the x-axis to make the wide FPGA tail visible while
    # keeping the CPU bump readable.
    ax.set_xscale("log")

    ax.set_xlabel("Latency (µs, log scale)")
    ax.set_ylabel("CDF")
    ax.set_title("CPU vs FPGA Latency (SoC benchmark @125 MHz)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()

    out_path = PLOTS_DIR / "cdf_cpu_vs_fpga.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")


def parse_log_summaries(path: Path, overlay: str) -> list[SummaryRecord]:
    """
    Parse summary blocks of the form:

      [delay_cycles=0 num_words=4 :: Fabric]
        Samples        : 50
        Cycles (avg)   : 142970.5
               median  : 124000.5
               min/max : 95872 / 998450
               stdev   : 123746.0

    Works for:
      - soc_full.log         (labels like "[delay_cycles=0 num_words=8]")
      - soc_mlp_only.log     (labels like "[delay_cycles=0 num_words=4 :: MLP]")
      - soc_nodma.log        (labels like "[delay_cycles=0 num_words=4 :: Fabric]")
      - soc_core.log         (labels like "[num_words=4]" and "[TRACE summary ...]")
    """
    header_re = re.compile(r"^\[(.+)]\s*$")
    samples_re = re.compile(r"Samples\s*:\s*(\d+)")
    avg_re = re.compile(r"Cycles \(avg\)\s*:\s*([0-9.]+)")
    median_re = re.compile(r"median\s*:\s*([0-9.]+)")
    minmax_re = re.compile(r"min/max\s*:\s*([0-9.]+)\s*/\s*([0-9.]+)")
    stdev_re = re.compile(r"stdev\s*:\s*([0-9.]+)")

    records: list[SummaryRecord] = []
    current_label: Optional[str] = None
    buf: list[str] = []

    lines = path.read_text().splitlines()

    def flush_block() -> None:
        nonlocal current_label, buf
        if not current_label or not buf:
            current_label = None
            buf = []
            return
        text = "\n".join(buf)
        m_samples = samples_re.search(text)
        m_avg = avg_re.search(text)
        m_median = median_re.search(text)
        m_minmax = minmax_re.search(text)
        m_stdev = stdev_re.search(text)
        if not (m_samples and m_avg and m_median and m_minmax and m_stdev):
            current_label = None
            buf = []
            return
        try:
            samples = int(m_samples.group(1))
            cycles_avg = float(m_avg.group(1))
            cycles_median = float(m_median.group(1))
            cycles_min = int(float(m_minmax.group(1)))
            cycles_max = int(float(m_minmax.group(2)))
            cycles_stdev = float(m_stdev.group(1))
        except ValueError:
            current_label = None
            buf = []
            return

        # Derive a short metric name from the label
        metric = derive_metric_name(current_label)
        rec = SummaryRecord(
            overlay=overlay,
            label=current_label,
            metric=metric,
            samples=samples,
            cycles_avg=cycles_avg,
            cycles_median=cycles_median,
            cycles_min=cycles_min,
            cycles_max=cycles_max,
            cycles_stdev=cycles_stdev,
        )
        records.append(rec)
        current_label = None
        buf = []

    for line in lines:
        m_h = header_re.match(line)
        if m_h:
            # New header: flush any pending block
            flush_block()
            current_label = m_h.group(1).strip()
            buf = []
            continue
        if current_label is not None:
            if line.strip() == "":
                # blank line → end of block
                flush_block()
            else:
                buf.append(line)
    # Flush last block
    flush_block()

    return records


def derive_metric_name(label: str) -> str:
    """
    Map raw label strings to short metric names.
    """
    # Examples:
    #  "delay_cycles=0 num_words=4 :: Fabric"
    #  "delay_cycles=0 num_words=4 :: MLP"
    #  "delay_cycles=0 num_words=4 :: MLP_only"
    #  "delay_cycles=0 num_words=4"
    #  "num_words=4"
    #  "TRACE summary num_words=4"
    if "::" in label:
        # suffix after '::' is the metric name
        metric = label.split("::", 1)[1].strip()
        return metric
    if label.startswith("TRACE summary"):
        return "TRACE"
    if "num_words" in label or "delay_cycles" in label:
        return "MLP_timer"
    return "summary"


def write_soc_summaries_csv(records: Iterable[SummaryRecord], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "overlay",
                "label",
                "metric",
                "samples",
                "cycles_avg",
                "cycles_median",
                "cycles_min",
                "cycles_max",
                "cycles_stdev",
                "latency_avg_ns",
                "latency_avg_us",
            ]
        )
        for r in records:
            writer.writerow(
                [
                    r.overlay,
                    r.label,
                    r.metric,
                    r.samples,
                    f"{r.cycles_avg:.3f}",
                    f"{r.cycles_median:.3f}",
                    r.cycles_min,
                    r.cycles_max,
                    f"{r.cycles_stdev:.3f}",
                    f"{r.latency_avg_ns:.3f}",
                    f"{r.latency_avg_us:.3f}",
                ]
            )
    print(f"wrote {out_path}")


def pick_representative_records(records: list[SummaryRecord]) -> list[SummaryRecord]:
    """
    Pick one representative record per overlay for the "main" configuration:
      - full      : delay_cycles=0 num_words=4  (MLP timer)
      - mlp_only  : delay_cycles=0 num_words=4 :: MLP_only
      - nodma     : delay_cycles=0 num_words=4 :: Fabric
      - core      : num_words=4  (TRACE summary if available, else num_words=4)
    """
    chosen: list[SummaryRecord] = []

    def find(predicate):
        for r in records:
            if predicate(r):
                return r
        return None

    full = find(
        lambda r: r.overlay == "full"
        and "delay_cycles=0" in r.label
        and "num_words=4" in r.label
    )
    if full is None:
        # Fallback: any delay=0 summary
        full = find(lambda r: r.overlay == "full" and "delay_cycles=0" in r.label)

    mlp_only = find(
        lambda r: r.overlay == "mlp_only"
        and "delay_cycles=0" in r.label
        and "num_words=4" in r.label
        and r.metric.lower().startswith("mlp")
    )

    nodma = find(
        lambda r: r.overlay == "nodma"
        and "delay_cycles=0" in r.label
        and "num_words=4" in r.label
        and r.metric == "Fabric"
    )

    # Prefer TRACE summary num_words=4 if present, else the plain num_words=4 block
    core = find(
        lambda r: r.overlay == "core"
        and "num_words=4" in r.label
        and r.metric == "TRACE"
    )
    if core is None:
        core = find(
            lambda r: r.overlay == "core" and "num_words=4" in r.label
        )

    for name, rec in [
        ("full", full),
        ("mlp_only", mlp_only),
        ("nodma", nodma),
        ("core", core),
    ]:
        if rec is None:
            print(f"warning: no representative record found for overlay={name}")
        else:
            chosen.append(rec)
    return chosen


def make_overlay_bar_plot(records: list[SummaryRecord]) -> None:
    """
    Make a simple bar chart comparing average latency for the representative
    configuration of each overlay (all at 125 MHz).
    """
    if not records:
        print("no records to plot for overlay bar chart")
        return

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    label_map = {
        "full": "Full (features+MLP+DMA)",
        "mlp_only": "MLP-only (DMA)",
        "nodma": "No-DMA (fabric only)",
        "core": "Core probe (minimal)",
    }

    # Sort in a stable, meaningful order
    order = ["core", "nodma", "mlp_only", "full"]
    ordered_records = []
    for o in order:
        for r in records:
            if r.overlay == o:
                ordered_records.append(r)
                break

    names = [label_map.get(r.overlay, r.overlay) for r in ordered_records]
    lat_us = [r.latency_avg_us for r in ordered_records]

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(names))
    bars = ax.bar(x, lat_us, color="tab:orange")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, ha="right")
    ax.set_ylabel("Average latency (µs)")
    ax.set_title("SoC fabric latency by overlay (delay=0, num_words=4, 125 MHz)")
    ax.grid(True, axis="y", alpha=0.3)

    # Add numeric labels on top of each bar for easier reading in screenshots.
    for bar, value in zip(bars, lat_us):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{value:.0f} µs",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.tight_layout()

    out_path = PLOTS_DIR / "soc_overlay_bar_avg_latency.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")


def make_nodma_stacked_plot(records: list[SummaryRecord]) -> None:
    """
    Build a stacked bar for the No-DMA overlay that decomposes fabric latency
    into MLP_internal (64-cycle core) and Overhead (everything else).
    """
    # Find nodma / delay=0 / num_words=4 records
    nodma_fabric = None
    nodma_internal = None
    nodma_overhead = None
    for r in records:
        if r.overlay != "nodma":
            continue
        if "delay_cycles=0" not in r.label or "num_words=4" not in r.label:
            continue
        if r.metric == "Fabric":
            nodma_fabric = r
        elif r.metric == "MLP_internal":
            nodma_internal = r
        elif r.metric == "Overhead":
            nodma_overhead = r

    if nodma_internal is None or nodma_overhead is None:
        print("warning: could not find nodma Fabric/MLP_internal/Overhead summaries; skipping stacked plot")
        return

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    comp_labels = ["MLP_internal", "Overhead"]
    comp_lat_us = [nodma_internal.latency_avg_us, nodma_overhead.latency_avg_us]

    fig, ax = plt.subplots(figsize=(4.5, 4))
    x = np.array([0])
    bottom = 0.0
    colors = ["tab:green", "tab:red"]
    for value, label, color in zip(comp_lat_us, comp_labels, colors):
        ax.bar(x, [value], bottom=bottom, label=label, color=color)
        bottom += value

    ax.set_xticks(x)
    ax.set_xticklabels(["No-DMA overlay"])
    ax.set_ylabel("Average latency (µs)")
    ax.set_title("No-DMA overlay: MLP compute vs fabric overhead\n(delay=0, num_words=4, 125 MHz)")
    ax.grid(True, axis="y", alpha=0.3)

    total_us = nodma_fabric.latency_avg_us if nodma_fabric is not None else bottom
    ax.text(
        0,
        total_us,
        f"Total ≈ {total_us:.0f} µs",
        ha="center",
        va="bottom",
        fontsize=8,
    )

    fig.tight_layout()
    out_path = PLOTS_DIR / "soc_nodma_stacked_overhead.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")


def main() -> None:
    # 1. CPU vs FPGA CDF from latency_comparison.csv
    latency_csv = HERE / "latency_comparison.csv"
    if latency_csv.exists():
        make_cpu_vs_fpga_cdf(latency_csv)
    else:
        print(f"warning: {latency_csv} not found, skipping CPU vs FPGA CDF")

    # 2. Parse SoC logs
    all_records: list[SummaryRecord] = []
    log_specs = [
        ("full", HERE / "soc_full.log"),
        ("mlp_only", HERE / "soc_mlp_only.log"),
        ("nodma", HERE / "soc_nodma.log"),
        ("core", HERE / "soc_core.log"),
    ]
    for overlay, path in log_specs:
        if not path.exists():
            print(f"warning: {path} not found, skipping")
            continue
        recs = parse_log_summaries(path, overlay=overlay)
        print(f"parsed {len(recs)} summary blocks from {path.name}")
        all_records.extend(recs)

    if all_records:
        write_soc_summaries_csv(all_records, HERE / "soc_summaries.csv")
        reps = pick_representative_records(all_records)
        make_overlay_bar_plot(reps)
        make_nodma_stacked_plot(all_records)
    else:
        print("no summary records parsed from any logs; nothing more to do")


if __name__ == "__main__":
    main()


