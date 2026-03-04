from __future__ import annotations

from pathlib import Path
from typing import Dict

# --- Matplotlib backend safety ---
# Prevent TkAgg-related crashes on Windows when running with Rich live rendering.
import matplotlib

try:
    matplotlib.use("Agg")
except Exception:
    pass

import matplotlib.pyplot as plt
import pandas as pd


def _ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"])
    return out


def _ensure_drawdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure drawdown column exists based on equity curve.
    drawdown = equity / cummax(equity) - 1
    """
    out = df.copy()
    if "drawdown" not in out.columns:
        if "equity" not in out.columns:
            raise KeyError("Expected 'equity' to compute drawdown.")
        eq = out["equity"].astype(float)
        peak = eq.cummax()
        out["drawdown"] = eq / peak - 1.0
    return out


def plot_equity(sim_df: pd.DataFrame, out_path: Path, title: str = "Equity") -> None:
    """
    Plot equity curve from simulation dataframe.
    Requires columns: date, equity
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = _ensure_datetime(sim_df)

    if "equity" not in df.columns:
        raise KeyError("plot_equity expects 'equity' column.")
    if "date" not in df.columns:
        raise KeyError("plot_equity expects 'date' column.")

    plt.figure()
    plt.plot(df["date"], df["equity"])
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_drawdown(sim_df: pd.DataFrame, out_path: Path, title: str = "Drawdown") -> None:
    """
    Plot drawdown curve. If 'drawdown' is missing, compute it from equity.
    Requires columns: date and (drawdown or equity).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = _ensure_datetime(sim_df)
    df = _ensure_drawdown(df)

    if "date" not in df.columns:
        raise KeyError("plot_drawdown expects 'date' column.")

    plt.figure()
    plt.plot(df["date"], df["drawdown"])
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_multi_equity(equity_map: Dict[str, pd.DataFrame], out_path: Path, title: str = "Equity (Multiple)") -> None:
    """
    Plot multiple equity curves on one chart.
    equity_map: {label: sim_df}
    Each sim_df must have date, equity
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure()

    for label, sim_df in equity_map.items():
        df = _ensure_datetime(sim_df)
        if "date" not in df.columns or "equity" not in df.columns:
            continue
        plt.plot(df["date"], df["equity"], label=label)

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_bootstrap_distribution(values, actual_value: float, out_path: Path, title: str) -> None:
    """
    Plot histogram of bootstrap values with a vertical line for the actual value.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure()
    plt.hist(values, bins=40)
    plt.axvline(actual_value)
    plt.title(title)
    plt.xlabel("Bootstrap value")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
