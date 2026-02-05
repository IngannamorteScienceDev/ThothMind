from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np


def run_multiticker_suite(cfg: dict[str, Any], run_dir: Path) -> pd.DataFrame:
    """
    Runs Conformal(90%) WF strategy + Buy&Hold WF baseline + bootstrap significance
    across multiple tickers, saves per-ticker artifacts under:
      run_dir / "tickers" / <TICKER> /

    Produces:
      - run_dir / "suite_summary.csv"
      - run_dir / "suite_summary.json"
    """
    from thothmind.config import save_json
    from thothmind.core.pipeline_m1 import build_df_feat
    from thothmind.core.features.pipeline import infer_feature_columns
    from thothmind.core.splits.walkforward import generate_walkforward_splits
    from thothmind.core.backtest.walkforward_ml_conformal import run_walkforward_ml_conformal_oos
    from thothmind.core.backtest.walkforward import run_walkforward_oos
    from thothmind.core.backtest.baseline_policy import BuyHoldPolicy
    from thothmind.core.reports.plots import plot_equity, plot_drawdown, plot_bootstrap_distribution
    from thothmind.core.stats.significance import bootstrap_oos_outperformance

    suite_cfg = cfg.get("suite", {})
    tickers = suite_cfg.get("tickers") or [cfg.get("data", {}).get("ticker", "SPY")]
    tickers = [str(t).upper().strip() for t in tickers if str(t).strip()]

    if not tickers:
        raise ValueError("No tickers provided for suite. Set suite.tickers in config.")

    tickers_root = run_dir / "tickers"
    tickers_root.mkdir(parents=True, exist_ok=True)

    # Shared configs
    wf_cfg = cfg.get("walkforward", {})
    train_size = int(wf_cfg.get("train_size", 756))
    test_size = int(wf_cfg.get("test_size", 63))
    step = int(wf_cfg.get("step", 63))

    # --- Costs (NEW schema) ---
    cost_cfg = cfg.get("costs", {}) or {}
    commission_bps = float(cost_cfg.get("commission_bps", 2.0))
    slippage_bps = float(cost_cfg.get("slippage_bps", 1.0))
    slippage_vol_k = float(cost_cfg.get("slippage_vol_k", 10.0))

    initial_equity = float(cfg.get("sim", {}).get("initial_equity", 1.0))

    model_cfg = cfg.get("model", {}) or {}
    conformal_cfg = cfg.get("conformal", {"alpha": 0.10}) or {"alpha": 0.10}

    boot_cfg = cfg.get("bootstrap", {}) or {}
    n_boot = int(boot_cfg.get("n_boot", 2000))  # suite default (можно увеличить в конфиге)
    block_len = int(boot_cfg.get("block_len", 20))
    ci_alpha = float(boot_cfg.get("ci_alpha", 0.05))
    seed = int(boot_cfg.get("seed", int(cfg.get("run", {}).get("seed", 42))))

    results: list[dict[str, Any]] = []

    for ticker in tickers:
        t_dir = tickers_root / ticker
        (t_dir / "plots").mkdir(parents=True, exist_ok=True)

        row: dict[str, Any] = {"ticker": ticker, "status": "ok", "error": ""}

        try:
            # --- Build df_feat for this ticker ---
            cfg_t = copy.deepcopy(cfg)
            cfg_t.setdefault("data", {})
            cfg_t["data"]["ticker"] = ticker

            df_feat, snapshot = build_df_feat(cfg_t)

            df_feat.to_csv(t_dir / "df_feat.csv", index=False)
            save_json(snapshot, t_dir / "data_snapshot.json")

            # --- Splits ---
            splits = generate_walkforward_splits(
                n_rows=len(df_feat),
                train_size=train_size,
                test_size=test_size,
                step=step,
            )

            feature_cols = infer_feature_columns(df_feat)
            save_json({"feature_cols": feature_cols}, t_dir / "feature_cols.json")

            # --- Strategy: conformal 90% WF OOS (NEW cost args) ---
            sim_oos_strat, window_metrics_strat, preds_oos, sigs_oos, run_metrics_strat = (
                run_walkforward_ml_conformal_oos(
                    df_feat=df_feat,
                    feature_cols=feature_cols,
                    splits=splits,
                    model_cfg=model_cfg,
                    conformal_cfg=conformal_cfg,
                    commission_bps=commission_bps,
                    slippage_bps=slippage_bps,
                    slippage_vol_k=slippage_vol_k,
                    initial_equity=initial_equity,
                )
            )

            preds_oos.to_csv(t_dir / "predictions_oos.csv", index=False)
            sigs_oos.to_csv(t_dir / "signals_oos.csv", index=False)
            sim_oos_strat.to_csv(t_dir / "sim_oos.csv", index=False)
            window_metrics_strat.to_csv(t_dir / "window_metrics.csv", index=False)
            save_json(run_metrics_strat, t_dir / "run_metrics.json")

            plot_equity(sim_oos_strat, t_dir / "plots" / "wf_equity.png")
            plot_drawdown(sim_oos_strat, t_dir / "plots" / "wf_drawdown.png")

            # --- Baseline: Buy&Hold under SAME WF protocol (NEW cost args) ---
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
            )
            sim_oos_bh.to_csv(t_dir / "sim_oos_buyhold.csv", index=False)
            save_json(bh_metrics, t_dir / "run_metrics_buyhold.json")

            # --- Bootstrap significance: strategy vs buyhold ---
            sig_summary, boot_df = bootstrap_oos_outperformance(
                sim_strategy=sim_oos_strat,
                sim_buyhold=sim_oos_bh,
                n_boot=n_boot,
                block_len=block_len,
                ci_alpha=ci_alpha,
                seed=seed,
            )
            save_json(sig_summary, t_dir / "oos_significance.json")
            boot_df.to_csv(t_dir / "bootstrap_samples.csv", index=False)

            plot_bootstrap_distribution(
                values=boot_df["boot_rel_return"].to_numpy(),
                actual_value=float(sig_summary["actual_rel_return"]),
                out_path=t_dir / "plots" / "bootstrap_rel_return_hist.png",
                title=f"{ticker}: Bootstrap OOS Outperformance vs Buy&Hold (Relative Return)",
            )

            # --- Summary row ---
            row.update(
                {
                    "n_days_aligned": int(sig_summary.get("n_days_aligned", 0)),
                    "actual_rel_return": float(sig_summary.get("actual_rel_return", 0.0)),
                    "p_value_one_sided": float(sig_summary.get("p_value_one_sided", 1.0)),
                    "ci_rel_return_low": float(sig_summary.get("ci_rel_return_low", 0.0)),
                    "ci_rel_return_high": float(sig_summary.get("ci_rel_return_high", 0.0)),
                    "prob_outperform": float(sig_summary.get("prob_outperform", 0.0)),
                }
            )

        except Exception as e:
            row["status"] = "error"
            row["error"] = repr(e)

        results.append(row)

    summary_df = pd.DataFrame(results)

    # Ensure required columns exist even if some/all tickers failed
    for col in [
        "ticker",
        "status",
        "actual_rel_return",
        "p_value_one_sided",
        "ci_rel_return_low",
        "ci_rel_return_high",
        "prob_outperform",
    ]:
        if col not in summary_df.columns:
            summary_df[col] = np.nan

    # Make status sortable: ok first, then error
    try:
        status_dtype = pd.CategoricalDtype(categories=["ok", "error"], ordered=True)
        summary_df["status"] = summary_df["status"].astype(status_dtype)
    except Exception:
        pass

    # Safe sort (NaNs last)
    summary_df = summary_df.sort_values(
        ["status", "p_value_one_sided", "ticker"],
        ascending=[True, True, True],
        na_position="last",
    ).reset_index(drop=True)

    summary_df.to_csv(run_dir / "suite_summary.csv", index=False)
    save_json({"rows": summary_df.to_dict(orient="records")}, run_dir / "suite_summary.json")

    return summary_df
