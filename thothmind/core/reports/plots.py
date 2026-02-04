from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd


def plot_equity(sim_df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure()
    plt.plot(sim_df["date"], sim_df["equity"])
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.title("Equity Curve")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_drawdown(sim_df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure()
    plt.plot(sim_df["date"], sim_df["drawdown"])
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.title("Drawdown")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
