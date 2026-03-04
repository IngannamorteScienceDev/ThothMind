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


DELTA_COLS = [
    "delta_mean_net_ret",
    "delta_sharpe",
    "delta_total_rel_return",
    "delta_worst_drawdown",
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


def build_suite_regime_summary(
    tickers_dir: Path,
    out_dir: Path,
) -> pd.DataFrame:
    """
    Aggregate per-ticker regime attribution reports into a suite-level summary.

    Expects per-ticker files:
      tickers/<TICKER>/regime/regime_summary_wide.csv

    Writes:
      out_dir/suite_regime_summary.csv
      out_dir/suite_regime_delta_worst_drawdown.png
      out_dir/suite_regime_delta_mean_net_ret.png
      out_dir/suite_regime_delta_total_rel_return.png
      out_dir/suite_regime_delta_sharpe.png

    Returns:
      summary_df
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

    # Keep only what we need
    keep = ["ticker", "regime"]
    if "n_days_strategy" in allw.columns:
        keep.append("n_days_strategy")
    for c in DELTA_COLS:
        if c in allw.columns:
            keep.append(c)
    allw = allw[keep].copy()

    # weights by #days in that regime for that ticker (if available)
    if "n_days_strategy" in allw.columns:
        allw["weight"] = pd.to_numeric(allw["n_days_strategy"], errors="coerce").fillna(0.0).astype(float)
    else:
        allw["weight"] = 1.0

    # Regime index
    regimes = sorted(allw["regime"].astype(str).unique())
    out = pd.DataFrame({"regime": regimes}).set_index("regime")

    # n_tickers and weights
    out["n_tickers"] = allw.groupby("regime")["ticker"].nunique().reindex(regimes).fillna(0).astype(int)
    out["total_weight_days"] = allw.groupby("regime")["weight"].sum().reindex(regimes).fillna(0.0).astype(float)

    def _share_pos(series: pd.Series, regime_series: pd.Series) -> pd.Series:
        x = pd.to_numeric(series, errors="coerce")
        m = x.notna()
        pos = (x > 0) & m
        npos = pos.groupby(regime_series).sum()
        nobs = m.groupby(regime_series).sum()
        return (npos / nobs).reindex(regimes)

    # Aggregate each delta column without groupby.apply (no FutureWarning)
    for col in DELTA_COLS:
        if col not in allw.columns:
            continue

        x = pd.to_numeric(allw[col], errors="coerce")
        g = allw["regime"].astype(str)
        w = pd.to_numeric(allw["weight"], errors="coerce").fillna(0.0)

        # simple mean/median (pandas ignores NaN)
        out[f"{col}_mean"] = x.groupby(g).mean().reindex(regimes)
        out[f"{col}_median"] = x.groupby(g).median().reindex(regimes)

        # weighted mean: sum(w*x) / sum(w), with NaN-safe masking
        m = x.notna() & (w > 0)
        w_eff = w.where(m, 0.0)
        wx = (x.fillna(0.0) * w_eff)

        wsum = w_eff.groupby(g).sum().reindex(regimes)
        wsumx = wx.groupby(g).sum().reindex(regimes)
        out[f"{col}_wmean"] = np.where((wsum.to_numpy() > 0), (wsumx.to_numpy() / wsum.to_numpy()), np.nan)

        # share of tickers/days with positive delta (NaN-safe)
        out[f"{col}_share_pos"] = _share_pos(x, g)

    out = out.reset_index().sort_values("regime").reset_index(drop=True)
    out.to_csv(out_dir / "suite_regime_summary.csv", index=False)

    # plots: prefer weighted mean for stability
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