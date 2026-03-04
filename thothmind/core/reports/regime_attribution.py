from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _to_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def _norm_text(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
        .str.strip()
        .str.lower()
        .str.replace("-", "_", regex=False)
        .str.replace(" ", "_", regex=False)
    )


def label_regimes(df_feat: pd.DataFrame) -> pd.DataFrame:
    """
    Build a regimes table: date -> trend/vol/regime.

    Preference order:
      1) market_regime (already computed in feature pipeline)
      2) trend_state + vol_state
      3) fallback from sma_ratio_200 + vol_z_20

    IMPORTANT: We assume these regime features are computed without lookahead
    (rolling + shift inside feature engineering). We do NOT add extra shift here
    to avoid misalignment with y (forward return).
    """
    df = df_feat.copy()
    if "date" not in df.columns:
        raise KeyError("df_feat must contain 'date' column.")
    df["date"] = _to_dt(df["date"])
    df = df.sort_values("date").dropna(subset=["date"])

    # 1) market_regime
    if "market_regime" in df.columns:
        mr = _norm_text(df["market_regime"])
        if mr.notna().any() and (mr != "nan").any():
            # Try to parse common patterns: "bull_low", "bear_high", etc.
            regime = mr.replace("nan", np.nan)
            trend = regime.str.split("_").str[0]
            vol = regime.str.split("_").str[1] if regime.str.contains("_").any() else pd.Series([""] * len(df))
            out = pd.DataFrame({"date": df["date"], "trend": trend, "vol": vol, "regime": regime})
            out["trend"] = out["trend"].fillna("")
            out["vol"] = out["vol"].fillna("")
            out["regime"] = out["regime"].fillna("")
            return out

    # 2) trend_state + vol_state
    if "trend_state" in df.columns and "vol_state" in df.columns:
        trend = _norm_text(df["trend_state"])
        vol = _norm_text(df["vol_state"])
        regime = trend + "_" + vol
        return pd.DataFrame({"date": df["date"], "trend": trend, "vol": vol, "regime": regime})

    # 3) fallback
    if "sma_ratio_200" not in df.columns or "vol_z_20" not in df.columns:
        raise KeyError(
            "Cannot label regimes: expected market_regime OR (trend_state+vol_state) "
            "OR (sma_ratio_200+vol_z_20)."
        )

    sma_ratio = pd.to_numeric(df["sma_ratio_200"], errors="coerce").fillna(1.0)
    vol_z = pd.to_numeric(df["vol_z_20"], errors="coerce").fillna(0.0)

    trend = np.where(sma_ratio >= 1.0, "bull", "bear")
    vol = np.where(vol_z >= 0.0, "high", "low")
    regime = pd.Series(trend).astype(str) + "_" + pd.Series(vol).astype(str)

    return pd.DataFrame({"date": df["date"], "trend": trend, "vol": vol, "regime": regime})


def _add_drawdown(sim_df: pd.DataFrame) -> pd.DataFrame:
    df = sim_df.copy()
    if "equity" not in df.columns:
        raise KeyError("sim_df must contain 'equity'.")
    eq = pd.to_numeric(df["equity"], errors="coerce").astype(float).fillna(method="ffill")
    peak = np.maximum.accumulate(eq.to_numpy(dtype=float))
    peak = np.where(peak <= 0.0, 1.0, peak)
    dd = (eq.to_numpy(dtype=float) / peak) - 1.0
    df["drawdown"] = dd
    return df


def _summary_by_regime(sim_df: pd.DataFrame, regimes: pd.DataFrame, variant: str) -> pd.DataFrame:
    df = sim_df.copy()
    df["date"] = _to_dt(df["date"])
    df = df.sort_values("date").dropna(subset=["date"])

    regs = regimes.copy()
    regs["date"] = _to_dt(regs["date"])
    regs = regs.sort_values("date").dropna(subset=["date"])

    df = df.merge(regs[["date", "trend", "vol", "regime"]], on="date", how="left")
    df["regime"] = df["regime"].fillna("unknown")

    # ensure numeric
    for c in ["net_ret", "gross_ret", "turnover", "total_cost", "exposure", "commission_cost", "slippage_cost", "drawdown"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "net_ret" not in df.columns:
        raise KeyError("sim_df must contain 'net_ret' for regime attribution.")

    # log-returns contribution
    net = df["net_ret"].astype(float).fillna(0.0).to_numpy(dtype=float)
    logret = np.log1p(net)
    df["log_ret"] = logret

    grp = df.groupby("regime", dropna=False)

    out = pd.DataFrame(
        {
            "variant": variant,
            "regime": grp.size().index,
            "n_days": grp.size().values,
            "mean_net_ret": grp["net_ret"].mean().values,
            "vol_net_ret": grp["net_ret"].std(ddof=1).values,
            "mean_log_ret": grp["log_ret"].mean().values,
            "sum_log_ret": grp["log_ret"].sum().values,
            "avg_exposure": grp["exposure"].mean().values if "exposure" in df.columns else np.nan,
            "avg_turnover": grp["turnover"].mean().values if "turnover" in df.columns else np.nan,
            "avg_total_cost": grp["total_cost"].mean().values if "total_cost" in df.columns else np.nan,
            "avg_drawdown": grp["drawdown"].mean().values if "drawdown" in df.columns else np.nan,
            "worst_drawdown": grp["drawdown"].min().values if "drawdown" in df.columns else np.nan,
        }
    )

    # sharpe (daily)
    out["sharpe"] = np.where(
        out["vol_net_ret"].to_numpy(dtype=float) > 1e-12,
        np.sqrt(252.0) * (out["mean_net_ret"].to_numpy(dtype=float) / out["vol_net_ret"].to_numpy(dtype=float)),
        np.nan,
    )

    out["total_rel_return"] = np.expm1(out["sum_log_ret"].to_numpy(dtype=float))

    total_sum = float(np.nansum(out["sum_log_ret"].to_numpy(dtype=float)))
    if abs(total_sum) < 1e-12:
        out["share_log_ret"] = np.nan
    else:
        out["share_log_ret"] = out["sum_log_ret"].to_numpy(dtype=float) / total_sum

    return out.sort_values("regime").reset_index(drop=True)


def _exposure_distribution(sim_df: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    df = sim_df.copy()
    df["date"] = _to_dt(df["date"])
    df = df.sort_values("date").dropna(subset=["date"])
    regs = regimes.copy()
    regs["date"] = _to_dt(regs["date"])
    regs = regs.sort_values("date").dropna(subset=["date"])

    df = df.merge(regs[["date", "regime"]], on="date", how="left")
    df["regime"] = df["regime"].fillna("unknown")

    if "exposure" not in df.columns:
        return pd.DataFrame()

    df["exposure"] = pd.to_numeric(df["exposure"], errors="coerce")
    piv = (
        df.groupby(["regime", "exposure"])
        .size()
        .reset_index(name="n_days")
        .sort_values(["regime", "exposure"])
    )
    # share within regime
    denom = piv.groupby("regime")["n_days"].transform("sum").astype(float)
    piv["share"] = np.where(denom > 0, piv["n_days"].astype(float) / denom, np.nan)
    return piv


def _plot_regime_counts(regimes: pd.DataFrame, out_path: Path) -> None:
    vc = regimes["regime"].value_counts().sort_index()
    plt.figure()
    vc.plot(kind="bar")
    plt.title("Regime counts (days)")
    plt.xlabel("regime")
    plt.ylabel("days")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def _plot_mean_net_ret(summary_wide: pd.DataFrame, out_path: Path) -> None:
    df = summary_wide.sort_values("regime")
    x = np.arange(len(df))
    w = 0.4

    plt.figure()
    plt.bar(x - w / 2, df["mean_net_ret_strategy"], width=w, label="strategy")
    plt.bar(x + w / 2, df["mean_net_ret_buyhold"], width=w, label="buy&hold")
    plt.xticks(x, df["regime"], rotation=45, ha="right")
    plt.title("Mean daily net return by regime")
    plt.xlabel("regime")
    plt.ylabel("mean net_ret")
    plt.legend()
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def _plot_avg_exposure(summary_wide: pd.DataFrame, out_path: Path) -> None:
    df = summary_wide.sort_values("regime")
    plt.figure()
    plt.bar(df["regime"], df["avg_exposure_strategy"])
    plt.xticks(rotation=45, ha="right")
    plt.title("Average exposure (strategy) by regime")
    plt.xlabel("regime")
    plt.ylabel("avg exposure")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def build_regime_attribution_report(
    df_feat: pd.DataFrame,
    sim_strategy: pd.DataFrame,
    sim_buyhold: pd.DataFrame,
    out_dir: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Creates a regime attribution report for strategy vs buy&hold.

    Writes:
      out_dir/regimes.csv
      out_dir/regime_summary_long.csv
      out_dir/regime_summary_wide.csv
      out_dir/exposure_distribution_strategy.csv
      out_dir/exposure_distribution_buyhold.csv
      out_dir/plots/*.png

    Returns:
      (summary_wide, summary_long)
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    regimes = label_regimes(df_feat)
    regimes.to_csv(out_dir / "regimes.csv", index=False)

    strat = _add_drawdown(sim_strategy)
    bh = _add_drawdown(sim_buyhold)

    s_long = _summary_by_regime(strat, regimes, variant="strategy")
    b_long = _summary_by_regime(bh, regimes, variant="buyhold")
    long_df = pd.concat([s_long, b_long], ignore_index=True)
    long_df.to_csv(out_dir / "regime_summary_long.csv", index=False)

    # wide + deltas
    s = s_long.set_index("regime")
    b = b_long.set_index("regime")
    wide = pd.DataFrame(index=sorted(set(s.index) | set(b.index))).reset_index().rename(columns={"index": "regime"})

    def _col(df, name):
        return df.reindex(wide["regime"]).reset_index(drop=True)[name].to_numpy()

    for c in ["n_days", "mean_net_ret", "vol_net_ret", "sharpe", "sum_log_ret", "total_rel_return",
              "avg_exposure", "avg_turnover", "avg_total_cost", "avg_drawdown", "worst_drawdown"]:
        wide[f"{c}_strategy"] = _col(s, c) if c in s.columns else np.nan
        wide[f"{c}_buyhold"] = _col(b, c) if c in b.columns else np.nan

    wide["delta_mean_net_ret"] = wide["mean_net_ret_strategy"] - wide["mean_net_ret_buyhold"]
    wide["delta_sharpe"] = wide["sharpe_strategy"] - wide["sharpe_buyhold"]
    wide["delta_total_rel_return"] = wide["total_rel_return_strategy"] - wide["total_rel_return_buyhold"]
    wide["delta_worst_drawdown"] = wide["worst_drawdown_strategy"] - wide["worst_drawdown_buyhold"]

    wide = wide.sort_values("regime").reset_index(drop=True)
    wide.to_csv(out_dir / "regime_summary_wide.csv", index=False)

    # exposure distributions
    exp_s = _exposure_distribution(strat, regimes)
    exp_b = _exposure_distribution(bh, regimes)
    if not exp_s.empty:
        exp_s.to_csv(out_dir / "exposure_distribution_strategy.csv", index=False)
    if not exp_b.empty:
        exp_b.to_csv(out_dir / "exposure_distribution_buyhold.csv", index=False)

    # plots
    plots_dir = out_dir / "plots"
    _plot_regime_counts(regimes, plots_dir / "regime_counts.png")
    _plot_mean_net_ret(wide, plots_dir / "regime_mean_net_ret.png")
    if "avg_exposure_strategy" in wide.columns:
        _plot_avg_exposure(wide, plots_dir / "regime_avg_exposure_strategy.png")

    return wide, long_df
