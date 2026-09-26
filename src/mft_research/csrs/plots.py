"""Compact descriptive plots for CSRS research summaries."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _lines(frame, value, ylabel, title, path):
    fig, ax = plt.subplots(figsize=(8, 5))
    for formation, group in frame.groupby("formation_horizon", sort=True):
        group = group.sort_values("future_horizon")
        ax.plot(group.future_horizon, group[value], marker="o", label=f"Formation {formation}")
    ax.axhline(0, color="black", linewidth=.8)
    ax.set(xlabel="Future outcome horizon (sessions)", ylabel=ylabel, title=title)
    ax.legend(ncol=2, fontsize=8)
    ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def make_plots(report_dir: Path, horizon: pd.DataFrame, quantiles: pd.DataFrame,
               yearly: pd.DataFrame) -> None:
    plot_dir = report_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    _lines(horizon, "mean_ic", "Mean daily rank IC", "CSRS rank IC by outcome horizon",
           plot_dir / "rank_ic_by_horizon.png")
    _lines(horizon, "top_bottom_spread", "D10 minus D1 mean outcome", "CSRS signal decay",
           plot_dir / "signal_decay.png")
    _lines(horizon, "top_bottom_spread", "D10 minus D1 mean outcome", "Top-bottom outcome spread",
           plot_dir / "top_bottom_spread.png")

    selected = quantiles[(quantiles.group.str.match(r"D\d+$")) & (quantiles.future_horizon == 5)].copy()
    fig, ax = plt.subplots(figsize=(8, 5))
    for formation, group in selected.groupby("formation_horizon", sort=True):
        ax.plot(group.decile, group.mean_future_return, marker="o", label=f"Formation {formation}")
    ax.set(xlabel="CSRS decile (D10 strongest)", ylabel="Mean 5-session outcome",
           title="Decile monotonicity at the 5-session outcome")
    ax.grid(alpha=.25); ax.legend(ncol=2, fontsize=8); fig.tight_layout()
    fig.savefig(plot_dir / "quantile_monotonicity.png", dpi=150); plt.close(fig)

    by_year = yearly.groupby(["year", "formation_horizon"], as_index=False).mean_ic.mean()
    fig, ax = plt.subplots(figsize=(8, 5))
    for formation, group in by_year.groupby("formation_horizon", sort=True):
        ax.plot(group.year, group.mean_ic, marker="o", label=f"Formation {formation}")
    ax.axhline(0, color="black", linewidth=.8)
    ax.set(xlabel="Signal year", ylabel="Mean IC averaged across outcome horizons",
           title="Yearly CSRS rank IC")
    ax.grid(alpha=.25); ax.legend(ncol=2, fontsize=8); fig.tight_layout()
    fig.savefig(plot_dir / "yearly_ic.png", dpi=150); plt.close(fig)
