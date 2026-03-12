from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

# Matplotlib backend safety (Windows + Rich live rendering)
import matplotlib
try:
    matplotlib.use("Agg")
except Exception:
    pass
import matplotlib.pyplot as plt


# Regime delta columns computed by m9 per ticker (strategy - buyhold)
DELTA_COLS = [
    "delta_mean_net_ret",
    "delta_sharpe",
    "delta_total_rel_return",
    "delta_worst_drawdown",
]

# Per-variant absolute columns we want to aggregate (strategy and buyhold)
ABS_COLS = [
    "avg_exposure",
    "avg_turnover",
    "avg_total_cost",
]


def _plot_bar(df: pd.DataFrame, col: str, out_path: Path, title: str, ylabel: str) -> None:
    if df.empty or col not in df.columns:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)

    d = df.sort_values("regime").copy()
    y = pd.to_numeric(d[col], errors="coerce").fillna(0.0)

    plt.figure()
    plt.bar(d["regime"].astype(str), y)
    plt.xticks(rotation=45, ha="right")
    plt.title(title)
    plt.xlabel("regime")
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def _plot_grouped_bar(
    df: pd.DataFrame,
    col_a: str,
    col_b: str,
    out_path: Path,
    title: str,
    ylabel: str,
    label_a: str = "strategy",
    label_b: str = "buy&hold",
) -> None:
    if df.empty or col_a not in df.columns or col_b not in df.columns:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)

    d = df.sort_values("regime").copy()
    a = pd.to_numeric(d[col_a], errors="coerce").fillna(0.0).to_numpy()
    b = pd.to_numeric(d[col_b], errors="coerce").fillna(0.0).to_numpy()

    x = np.arange(len(d))
    w = 0.4

    plt.figure()
    plt.bar(x - w / 2, a, width=w, label=label_a)
    plt.bar(x + w / 2, b, width=w, label=label_b)
    plt.xticks(x, d["regime"].astype(str), rotation=45, ha="right")
    plt.title(title)
    plt.xlabel("regime")
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def build_suite_regime_summary(
    tickers_dir: Path,
    out_dir: Path,
) -> pd.DataFrame:
    """
    Aggregate per-ticker regime attribution reports into a suite-level summary.

    Expects per-ticker files:
      tickers/<TICKER>/regime/regime_summary_wide.csv

    Output (suite-level):
      out_dir/suite_regime_summary.csv
      + suite-level plots (deltas, plus exposure/turnover/cost)

    Scientific intent:
      - Provide a cross-ticker view: where strategy helps/hurts by regime.
      - Provide mechanism: exposure/turnover/cost differences that explain behavior.

    Notes:
      - Weighted means use regime day counts (n_days_strategy) as weights when available.
    """
    tickers_dir = Path(tickers_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[pd.DataFrame] = []
    for tdir in sorted(tickers_dir.glob("*")):
        if not tdir.is_dir():
            continue
        wide_path = tdir / "regime" / "regime_summary_wide.csv"
        if not wide_path.exists():
            continue
        try:
            df = pd.read_csv(wide_path)
        except Exception:
            continue
        if df.empty or "regime" not in df.columns:
            continue
        df = df.copy()
        df["ticker"] = tdir.name
        rows.append(df)

    if not rows:
        empty = pd.DataFrame()
        empty.to_csv(out_dir / "suite_regime_summary.csv", index=False)
        return empty

    allw = pd.concat(rows, ignore_index=True)

    # --- Keep only needed columns (robust to schema changes) ---
    keep = ["ticker", "regime"]
    if "n_days_strategy" in allw.columns:
        keep.append("n_days_strategy")

    # deltas
    for c in DELTA_COLS:
        if c in allw.columns:
            keep.append(c)

    # absolute columns (strategy/buyhold)
    for base in ABS_COLS:
        cs = f"{base}_strategy"
        cb = f"{base}_buyhold"
        if cs in allw.columns:
            keep.append(cs)
        if cb in allw.columns:
            keep.append(cb)

        # also store delta for convenience (if abs columns exist)
        if cs in allw.columns and cb in allw.columns:
            allw[f"delta_{base}"] = pd.to_numeric(allw[cs], errors="coerce") - pd.to_numeric(allw[cb], errors="coerce")
            keep.append(f"delta_{base}")

    allw = allw[keep].copy()

    # weights by #days in that regime for that ticker (if available)
    if "n_days_strategy" in allw.columns:
        allw["weight"] = pd.to_numeric(allw["n_days_strategy"], errors="coerce").fillna(0.0).astype(float)
    else:
        allw["weight"] = 1.0

    regimes = sorted(allw["regime"].astype(str).unique())
    out = pd.DataFrame({"regime": regimes}).set_index("regime")

    # counts and weights
    out["n_tickers"] = allw.groupby("regime")["ticker"].nunique().reindex(regimes).fillna(0).astype(int)
    out["total_weight_days"] = allw.groupby("regime")["weight"].sum().reindex(regimes).fillna(0.0).astype(float)

    def _share_pos(series: pd.Series, regime_series: pd.Series) -> pd.Series:
        x = pd.to_numeric(series, errors="coerce")
        m = x.notna()
        pos = (x > 0) & m
        npos = pos.groupby(regime_series).sum()
        nobs = m.groupby(regime_series).sum()
        return (npos / nobs).reindex(regimes)

    def _weighted_mean(x: pd.Series, w: pd.Series, g: pd.Series) -> np.ndarray:
        x = pd.to_numeric(x, errors="coerce")
        w = pd.to_numeric(w, errors="coerce").fillna(0.0)
        m = x.notna() & (w > 0)
        w_eff = w.where(m, 0.0)
        wx = (x.fillna(0.0) * w_eff)
        wsum = w_eff.groupby(g).sum().reindex(regimes)
        wsumx = wx.groupby(g).sum().reindex(regimes)
        return np.where((wsum.to_numpy() > 0), (wsumx.to_numpy() / wsum.to_numpy()), np.nan)

    g = allw["regime"].astype(str)
    w = allw["weight"]

    # --- delta aggregations ---
    for col in DELTA_COLS:
        if col not in allw.columns:
            continue
        x = allw[col]
        out[f"{col}_mean"] = pd.to_numeric(x, errors="coerce").groupby(g).mean().reindex(regimes)
        out[f"{col}_median"] = pd.to_numeric(x, errors="coerce").groupby(g).median().reindex(regimes)
        out[f"{col}_wmean"] = _weighted_mean(x, w, g)
        out[f"{col}_share_pos"] = _share_pos(x, g)

    # --- absolute metric aggregations (strategy/buyhold) + their deltas ---
    for base in ABS_COLS:
        cs = f"{base}_strategy"
        cb = f"{base}_buyhold"
        cd = f"delta_{base}"

        if cs in allw.columns:
            out[f"{base}_strategy_wmean"] = _weighted_mean(allw[cs], w, g)
        if cb in allw.columns:
            out[f"{base}_buyhold_wmean"] = _weighted_mean(allw[cb], w, g)
        if cd in allw.columns:
            out[f"{cd}_wmean"] = _weighted_mean(allw[cd], w, g)
            out[f"{cd}_share_pos"] = _share_pos(allw[cd], g)

    out = out.reset_index().sort_values("regime").reset_index(drop=True)
    out.to_csv(out_dir / "suite_regime_summary.csv", index=False)

    # --- plots: deltas (weighted mean) ---
    _plot_bar(
        out,
        "delta_worst_drawdown_wmean",
        out_dir / "suite_regime_delta_worst_drawdown.png",
        title="Suite: Δ worst drawdown (strategy - buy&hold) by regime",
        ylabel="Δ worst drawdown",
    )
    _plot_bar(
        out,
        "delta_mean_net_ret_wmean",
        out_dir / "suite_regime_delta_mean_net_ret.png",
        title="Suite: Δ mean daily net return (strategy - buy&hold) by regime",
        ylabel="Δ mean net_ret",
    )
    _plot_bar(
        out,
        "delta_total_rel_return_wmean",
        out_dir / "suite_regime_delta_total_rel_return.png",
        title="Suite: Δ total relative return (strategy - buy&hold) by regime",
        ylabel="Δ total_rel_return",
    )
    _plot_bar(
        out,
        "delta_sharpe_wmean",
        out_dir / "suite_regime_delta_sharpe.png",
        title="Suite: Δ Sharpe (strategy - buy&hold) by regime",
        ylabel="Δ Sharpe",
    )

    # --- plots: mechanism (exposure / turnover / cost) ---
    if "avg_exposure_strategy_wmean" in out.columns and "avg_exposure_buyhold_wmean" in out.columns:
        _plot_grouped_bar(
            out,
            "avg_exposure_strategy_wmean",
            "avg_exposure_buyhold_wmean",
            out_dir / "suite_regime_avg_exposure.png",
            title="Suite: average exposure by regime",
            ylabel="avg exposure",
        )

    if "avg_turnover_strategy_wmean" in out.columns and "avg_turnover_buyhold_wmean" in out.columns:
        _plot_grouped_bar(
            out,
            "avg_turnover_strategy_wmean",
            "avg_turnover_buyhold_wmean",
            out_dir / "suite_regime_avg_turnover.png",
            title="Suite: average turnover by regime",
            ylabel="avg turnover",
        )

    if "avg_total_cost_strategy_wmean" in out.columns and "avg_total_cost_buyhold_wmean" in out.columns:
        _plot_grouped_bar(
            out,
            "avg_total_cost_strategy_wmean",
            "avg_total_cost_buyhold_wmean",
            out_dir / "suite_regime_avg_total_cost.png",
            title="Suite: average total cost by regime",
            ylabel="avg total cost",
        )

    # deltas for mechanism
    if "delta_avg_exposure_wmean" in out.columns:
        _plot_bar(
            out,
            "delta_avg_exposure_wmean",
            out_dir / "suite_regime_delta_avg_exposure.png",
            title="Suite: Δ average exposure (strategy - buy&hold) by regime",
            ylabel="Δ avg exposure",
        )

    if "delta_avg_turnover_wmean" in out.columns:
        _plot_bar(
            out,
            "delta_avg_turnover_wmean",
            out_dir / "suite_regime_delta_avg_turnover.png",
            title="Suite: Δ average turnover (strategy - buy&hold) by regime",
            ylabel="Δ avg turnover",
        )

    if "delta_avg_total_cost_wmean" in out.columns:
        _plot_bar(
            out,
            "delta_avg_total_cost_wmean",
            out_dir / "suite_regime_delta_avg_total_cost.png",
            title="Suite: Δ average total cost (strategy - buy&hold) by regime",
            ylabel="Δ avg total cost",
        )

    return out


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Build suite-level regime summary from per-ticker regime reports.")
    ap.add_argument("--run", type=str, required=True, help="Run directory: reports/runs/<run_id>")
    ap.add_argument("--out", type=str, default="", help="Output directory (default: <run>/suite_regime)")
    args = ap.parse_args()

    run_dir = Path(args.run).expanduser().resolve()
    tickers_dir = run_dir / "tickers"
    out_dir = Path(args.out).expanduser().resolve() if args.out else (run_dir / "suite_regime")

    df = build_suite_regime_summary(tickers_dir=tickers_dir, out_dir=out_dir)
    print(f"[suite_regime] rows={len(df)} -> {out_dir}")


if __name__ == "__main__":
    main()