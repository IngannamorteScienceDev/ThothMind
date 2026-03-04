from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from thothmind.config import save_json
from thothmind.core.backtest.baseline_policy import BuyHoldPolicy
from thothmind.core.backtest.walkforward import run_walkforward_oos
from thothmind.core.backtest.walkforward_ml_conformal import run_walkforward_ml_conformal_oos
from thothmind.core.features.pipeline import infer_feature_columns
from thothmind.core.pipeline_m1 import build_df_feat
from thothmind.core.reports.plots import (
    plot_bootstrap_distribution,
    plot_drawdown,
    plot_equity,
)
from thothmind.core.splits.walkforward import generate_walkforward_splits
from thothmind.core.stats.significance import bootstrap_oos_outperformance
from thothmind.core.utils.richkit import console, make_progress


def _compute_sim_stats(sim: pd.DataFrame) -> Dict[str, float]:
    """Lightweight stats used in suite_summary.csv."""
    if sim is None or sim.empty:
        return {
            "n_days": 0,
            "last_equity": np.nan,
            "mean_net_ret": np.nan,
            "avg_exposure": np.nan,
            "avg_turnover": np.nan,
            "total_cost_sum": np.nan,
            "worst_drawdown": np.nan,
        }

    df = sim.copy()
    df["equity"] = pd.to_numeric(df.get("equity"), errors="coerce")
    df = df.dropna(subset=["equity"])
    if df.empty:
        return {
            "n_days": 0,
            "last_equity": np.nan,
            "mean_net_ret": np.nan,
            "avg_exposure": np.nan,
            "avg_turnover": np.nan,
            "total_cost_sum": np.nan,
            "worst_drawdown": np.nan,
        }

    eq = df["equity"].astype(float)
    peak = eq.cummax()
    dd = (eq / peak) - 1.0

    def _mean(col: str) -> float:
        if col not in df.columns:
            return float(np.nan)
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).mean())

    def _sum(col: str) -> float:
        if col not in df.columns:
            return float(np.nan)
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).sum())

    return {
        "n_days": int(len(df)),
        "last_equity": float(eq.iloc[-1]),
        "mean_net_ret": _mean("net_ret"),
        "avg_exposure": _mean("exposure"),
        "avg_turnover": _mean("turnover"),
        "total_cost_sum": _sum("total_cost"),
        "worst_drawdown": float(dd.min()),
    }


def _read_allocation_cfg(cfg: dict) -> dict | None:
    """Same semantics as run.py: new schema allocation: {...}, fallback to conformal keys."""
    allocation_cfg = cfg.get("allocation")
    if isinstance(allocation_cfg, dict) and len(allocation_cfg) > 0:
        return allocation_cfg

    conformal_cfg = cfg.get("conformal", {}) or {}
    if not isinstance(conformal_cfg, dict):
        return None

    alloc_keys = {"low_exposure", "mid_exposure", "high_exposure", "y_pred_thr", "width_max", "min_hold_days"}
    if any(k in conformal_cfg for k in alloc_keys):
        return {k: conformal_cfg[k] for k in alloc_keys if k in conformal_cfg}
    return None


def run_multiticker_suite(cfg: dict, run_dir: Path) -> pd.DataFrame:
    """Milestone 8: multi-ticker suite.

    For each ticker we run:
      - m1 (df_feat + snapshot)
      - WF strategy (ML + conformal intervals + allocation)
      - WF buy&hold under same protocol
      - moving-block bootstrap significance (strategy vs buy&hold)

    Writes per-ticker artifacts into:
      reports/runs/<run_id>/tickers/<TICKER>/...

    And a suite-level summary:
      reports/runs/<run_id>/suite_summary.csv

    Notes on console stability:
      - Avoid nested Live renders (e.g., console.status inside Progress).
      - Use Progress task descriptions instead.
    """
    log = logging.getLogger("thothmind")

    suite_cfg = cfg.get("suite", {}) or {}
    tickers = list(suite_cfg.get("tickers", []) or [])
    if not tickers:
        raise ValueError("suite.tickers is empty. Provide at least one ticker.")

    wf_cfg = cfg.get("walkforward", {}) or {}
    train_size = int(wf_cfg.get("train_size", 756))
    test_size = int(wf_cfg.get("test_size", 63))
    step = int(wf_cfg.get("step", 63))

    model_cfg = cfg.get("model", {}) or {}
    conformal_cfg = cfg.get("conformal", {"alpha": 0.10}) or {"alpha": 0.10}
    allocation_cfg = _read_allocation_cfg(cfg)

    boot_cfg = cfg.get("bootstrap", {}) or {}
    n_boot = int(boot_cfg.get("n_boot", 2000))
    block_len = int(boot_cfg.get("block_len", 20))
    ci_alpha = float(boot_cfg.get("ci_alpha", 0.05))
    seed = int(boot_cfg.get("seed", int(cfg.get("run", {}).get("seed", 42))))
    show_bootstrap_progress = bool(suite_cfg.get("show_bootstrap_progress", False))

    costs = cfg.get("costs", {}) or {}
    commission_bps = float(costs.get("commission_bps", 2.0))
    slippage_bps = float(costs.get("slippage_bps", 1.0))
    slippage_vol_k = float(costs.get("slippage_vol_k", 10.0))

    sim_cfg = cfg.get("sim", {}) or {}
    initial_equity = float(sim_cfg.get("initial_equity", 1.0))
    execution_lag = int(sim_cfg.get("execution_lag", 0))

    tickers_dir = run_dir / "tickers"
    tickers_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    console.print(f"[bold]m8[/] suite tickers = {tickers}")

    with make_progress() as p:
        t_task = p.add_task("m8: tickers", total=len(tickers))
        s_task = p.add_task("m8: step", total=4, visible=False)

        for ticker in tickers:
            p.update(t_task, description=f"m8: {ticker}")
            p.update(s_task, completed=0, total=4, visible=True, description=f"{ticker} • build_df_feat")

            ticker_dir = tickers_dir / str(ticker)
            (ticker_dir / "plots").mkdir(parents=True, exist_ok=True)

            ticker_cfg = copy.deepcopy(cfg)
            ticker_cfg.setdefault("data", {})
            ticker_cfg["data"]["ticker"] = str(ticker)
            save_json(ticker_cfg, ticker_dir / "config_ticker.json")

            try:
                # Step 1: build df_feat
                df_feat, snapshot = build_df_feat(ticker_cfg)
                df_feat.to_csv(ticker_dir / "df_feat.csv", index=False)
                save_json(snapshot, ticker_dir / "data_snapshot.json")
                p.advance(s_task, 1)

                # Prepare splits
                feature_cols = infer_feature_columns(df_feat)
                splits = generate_walkforward_splits(
                    n_rows=len(df_feat),
                    train_size=train_size,
                    test_size=test_size,
                    step=step,
                )

                # Step 2: WF strategy
                p.update(s_task, description=f"{ticker} • WF strategy")
                sim_oos_strat, window_metrics_strat, preds_oos, sig_oos, run_metrics_strat = (
                    run_walkforward_ml_conformal_oos(
                        df_feat=df_feat,
                        feature_cols=feature_cols,
                        splits=splits,
                        model_cfg=model_cfg,
                        conformal_cfg=conformal_cfg,
                        allocation_cfg=allocation_cfg,
                        commission_bps=commission_bps,
                        slippage_bps=slippage_bps,
                        slippage_vol_k=slippage_vol_k,
                        initial_equity=initial_equity,
                        execution_lag=execution_lag,
                    )
                )

                preds_oos.to_csv(ticker_dir / "predictions_oos.csv", index=False)
                sig_oos.to_csv(ticker_dir / "signals_oos.csv", index=False)
                sim_oos_strat.to_csv(ticker_dir / "sim_oos.csv", index=False)
                window_metrics_strat.to_csv(ticker_dir / "window_metrics.csv", index=False)
                save_json(run_metrics_strat, ticker_dir / "run_metrics.json")

                plot_equity(sim_oos_strat, ticker_dir / "plots" / "wf_equity.png")
                plot_drawdown(sim_oos_strat, ticker_dir / "plots" / "wf_drawdown.png")
                p.advance(s_task, 1)

                # Step 3: WF buy&hold
                p.update(s_task, description=f"{ticker} • WF buy&hold")
                bh_policy = BuyHoldPolicy()
                bh_signals_full = bh_policy.compute_signals(df_feat)
                sim_oos_bh, _, bh_metrics = run_walkforward_oos(
                    df_feat=df_feat,
                    signals_full=bh_signals_full,
                    splits=splits,
                    commission_bps=commission_bps,
                    slippage_bps=slippage_bps,
                    slippage_vol_k=slippage_vol_k,
                    initial_equity=initial_equity,
                    execution_lag=execution_lag,
                )

                sim_oos_bh.to_csv(ticker_dir / "sim_oos_buyhold.csv", index=False)
                save_json(bh_metrics, ticker_dir / "run_metrics_buyhold.json")
                p.advance(s_task, 1)

                # Step 4: bootstrap
                p.update(s_task, description=f"{ticker} • bootstrap")
                sig_summary, boot_df = bootstrap_oos_outperformance(
                    sim_strategy=sim_oos_strat,
                    sim_buyhold=sim_oos_bh,
                    n_boot=n_boot,
                    block_len=block_len,
                    ci_alpha=ci_alpha,
                    seed=seed,
                    show_progress=show_bootstrap_progress,
                )

                save_json(sig_summary, ticker_dir / "oos_significance.json")
                boot_df.to_csv(ticker_dir / "bootstrap_samples.csv", index=False)

                plot_bootstrap_distribution(
                    values=boot_df["boot_rel_return"].to_numpy(),
                    actual_value=float(sig_summary["actual_rel_return"]),
                    out_path=ticker_dir / "plots" / "bootstrap_rel_return_hist.png",
                    title=f"{ticker}: Bootstrap OOS Outperformance vs Buy&Hold (Relative Return)",
                )
                p.advance(s_task, 1)

                s_stats = _compute_sim_stats(sim_oos_strat)
                b_stats = _compute_sim_stats(sim_oos_bh)

                row = {
                    "ticker": str(ticker),
                    "status": "ok",
                    "strat_last_equity": s_stats["last_equity"],
                    "strat_mean_net_ret": s_stats["mean_net_ret"],
                    "strat_avg_exposure": s_stats["avg_exposure"],
                    "strat_avg_turnover": s_stats["avg_turnover"],
                    "strat_total_cost_sum": s_stats["total_cost_sum"],
                    "strat_worst_drawdown": s_stats["worst_drawdown"],
                    "strat_total_return": float((run_metrics_strat or {}).get("total_return", np.nan)),
                    "strat_sharpe": float((run_metrics_strat or {}).get("sharpe", np.nan)),
                    "strat_max_drawdown": float((run_metrics_strat or {}).get("max_drawdown", np.nan)),
                    "bh_last_equity": b_stats["last_equity"],
                    "bh_mean_net_ret": b_stats["mean_net_ret"],
                    "bh_avg_exposure": b_stats["avg_exposure"],
                    "bh_avg_turnover": b_stats["avg_turnover"],
                    "bh_total_cost_sum": b_stats["total_cost_sum"],
                    "bh_worst_drawdown": b_stats["worst_drawdown"],
                    "bh_total_return": float((bh_metrics or {}).get("total_return", np.nan)),
                    "bh_sharpe": float((bh_metrics or {}).get("sharpe", np.nan)),
                    "bh_max_drawdown": float((bh_metrics or {}).get("max_drawdown", np.nan)),
                    "actual_rel_return": float(sig_summary.get("actual_rel_return", np.nan)),
                    "prob_outperform": float(sig_summary.get("prob_outperform", np.nan)),
                    "p_value_one_sided": float(sig_summary.get("p_value_one_sided", np.nan)),
                    "ci_rel_return_low": float(sig_summary.get("ci_rel_return_low", np.nan)),
                    "ci_rel_return_high": float(sig_summary.get("ci_rel_return_high", np.nan)),
                }
                summary_rows.append(row)

                log.info(
                    f"[m8] {ticker}: done (rel_return={row['actual_rel_return']:.4f}, p={row['p_value_one_sided']:.4f})"
                )

            except Exception as e:
                console.print(f"[red]{ticker} failed:[/] {e}")
                summary_rows.append({"ticker": str(ticker), "status": "error", "error": str(e)})

            # hide step bar between tickers (clean output)
            p.update(s_task, visible=False)
            p.advance(t_task, 1)

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty and {"ticker", "status"}.issubset(summary_df.columns):
        rank = {"ok": 0, "error": 1}
        summary_df["_status_rank"] = summary_df["status"].map(rank).fillna(9)
        summary_df = summary_df.sort_values(["_status_rank", "ticker"], ascending=[True, True]).drop(
            columns=["_status_rank"]
        )

    summary_df.to_csv(run_dir / "suite_summary.csv", index=False)
    return summary_df


# Backward-compat re-export (older code might import bootstrap from this module)
def bootstrap_oos_outperformance_legacy(*args, **kwargs) -> Tuple[Dict[str, Any], pd.DataFrame]:
    return bootstrap_oos_outperformance(*args, **kwargs)
