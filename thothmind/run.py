# thothmind/run.py
import argparse
from typing import Any, Callable, Dict

from .config import load_config, save_json
from .registry import make_run_id, init_run_dir, write_run_artifacts


def _read_costs(cfg: Dict[str, Any]) -> Dict[str, float]:
    """
    Read trading cost params from config.

    Supports BOTH schemas:
      - New (recommended):
          costs:
            commission_bps: 2.0
            slippage_bps: 1.0
            slippage_vol_k: 10.0

      - Legacy:
          costs:
            commission_bps: 2.0
            slippage_k: 0.15
    """
    cost_cfg = cfg.get("costs", {}) or {}
    commission_bps = float(cost_cfg.get("commission_bps", 2.0))

    # New schema
    slippage_bps = float(cost_cfg.get("slippage_bps", 1.0))
    slippage_vol_k = float(cost_cfg.get("slippage_vol_k", 10.0))

    # Legacy schema (kept for backward compatibility)
    slippage_k_legacy = float(cost_cfg.get("slippage_k", 0.15))

    return {
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "slippage_vol_k": slippage_vol_k,
        "slippage_k_legacy": slippage_k_legacy,
    }


def _read_execution_lag(cfg: Dict[str, Any]) -> int:
    """
    Read execution lag from config.

    sim:
      execution_lag: 0 or 1 (recommended 1 for lookahead-safe execution)
    """
    sim_cfg = cfg.get("sim", {}) or {}
    try:
        lag = int(sim_cfg.get("execution_lag", 0))
    except Exception:
        lag = 0
    if lag < 0:
        lag = 0
    return lag


def _simulate_daily_adapter(
    df_feat,
    signals_df,
    *,
    commission_bps: float,
    slippage_bps: float,
    slippage_vol_k: float,
    slippage_k_legacy: float,
    initial_equity: float,
    execution_lag: int,
):
    """
    Call simulator in a way that works with both old/new simulate_daily signatures.
    """
    from thothmind.core.backtest.simulator import simulate_daily

    lag = int(execution_lag)
    if lag < 0:
        lag = 0

    try:
        # New simulator signature (recommended)
        return simulate_daily(
            df_feat=df_feat,
            signals_df=signals_df,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            slippage_vol_k=slippage_vol_k,
            initial_equity=initial_equity,
            execution_lag=lag,
        )
    except TypeError:
        # Legacy simulator signature (older)
        return simulate_daily(
            df_feat=df_feat,
            signals_df=signals_df,
            commission_bps=commission_bps,
            slippage_k=slippage_k_legacy,
            initial_equity=initial_equity,
        )


def _call_with_costs_adapter(func: Callable, kwargs: Dict[str, Any], costs: Dict[str, float]):
    """
    Call core functions that may accept either:
      - (commission_bps, slippage_bps, slippage_vol_k)
      - OR legacy (commission_bps, slippage_k)

    We try new kwargs first, then fallback to legacy.
    """
    try:
        return func(**kwargs)
    except TypeError:
        # Drop new params and pass legacy slippage_k if needed
        kwargs2 = dict(kwargs)
        kwargs2.pop("slippage_bps", None)
        kwargs2.pop("slippage_vol_k", None)
        if "slippage_k" not in kwargs2:
            kwargs2["slippage_k"] = costs["slippage_k_legacy"]
        return func(**kwargs2)


def run_experiment(config_path: str) -> str:
    cfg = load_config(config_path)

    run_id = make_run_id(cfg)
    output_dir = cfg.get("run", {}).get("output_dir", "reports/runs")
    run_dir = init_run_dir(run_id, output_root=output_dir)

    # Always write base artifacts (Milestone 0)
    write_run_artifacts(run_dir, cfg)

    stage = cfg.get("pipeline", {}).get("stage", "m0")

    # Costs (supports old/new)
    costs = _read_costs(cfg)
    commission_bps = costs["commission_bps"]
    slippage_bps = costs["slippage_bps"]
    slippage_vol_k = costs["slippage_vol_k"]
    slippage_k_legacy = costs["slippage_k_legacy"]

    # Sim init
    initial_equity = float(cfg.get("sim", {}).get("initial_equity", 1.0))
    execution_lag = _read_execution_lag(cfg)

    # Save execution settings for reproducibility
    save_json(
        {"initial_equity": float(initial_equity), "execution_lag": int(execution_lag)},
        run_dir / "sim_config.json",
    )

    # Milestone 1/2/3/4/5/6/7 require a single df_feat
    df_feat = None
    if stage in ("m1", "m2", "m3", "m4", "m5", "m6", "m7", "all"):
        from thothmind.core.pipeline_m1 import build_df_feat

        df_feat, snapshot = build_df_feat(cfg)

        df_feat.to_csv(run_dir / "df_feat.csv", index=False)
        save_json(snapshot, run_dir / "data_snapshot.json")

        print(f"[ThothMind] saved df_feat.csv ({len(df_feat)} rows)")
        print("[ThothMind] saved data_snapshot.json")

    # Milestone 2: baseline signals + simulator + metrics + plots
    if stage in ("m2", "all"):
        from thothmind.core.backtest.baseline_policy import SMATrendPolicy
        from thothmind.core.backtest.metrics import compute_metrics
        from thothmind.core.reports.plots import plot_equity, plot_drawdown

        if df_feat is None:
            raise RuntimeError("df_feat is required for m2, but was not built.")

        pol_cfg = cfg.get("baseline_policy", {}) or {}
        sma_window = int(pol_cfg.get("sma_window", 200))

        policy = SMATrendPolicy(sma_window=sma_window)
        signals_df = policy.compute_signals(df_feat)

        sim_df = _simulate_daily_adapter(
            df_feat,
            signals_df,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            slippage_vol_k=slippage_vol_k,
            slippage_k_legacy=slippage_k_legacy,
            initial_equity=initial_equity,
            execution_lag=execution_lag,
        )

        sim_df.to_csv(run_dir / "sim.csv", index=False)
        metrics = compute_metrics(sim_df)
        save_json(metrics, run_dir / "run_metrics.json")

        plot_equity(sim_df, run_dir / "plots" / "equity_curve.png")
        plot_drawdown(sim_df, run_dir / "plots" / "drawdown.png")

        print("[ThothMind] saved sim.csv + run_metrics.json + plots/")

    # Milestone 3: baselines suite + sanity checks + multi-equity plot
    if stage in ("m3", "all"):
        from thothmind.core.backtest.baseline_policy import (
            BuyHoldPolicy,
            FlatPolicy,
            SMATrendPolicy,
            RandomPolicy,
        )
        from thothmind.core.backtest.metrics import compute_metrics
        from thothmind.core.backtest.sanity import (
            sanity_buyhold_matches_theory,
            sanity_flat_has_no_pnl,
        )
        from thothmind.core.reports.plots import plot_multi_equity

        if df_feat is None:
            raise RuntimeError("df_feat is required for m3, but was not built.")

        base_cfg = cfg.get("baselines", {}) or {}
        sma_window = int(base_cfg.get("sma_window", 200))
        rand_seed = int(base_cfg.get("random_seed", int(cfg.get("run", {}).get("seed", 42))))
        rand_p_long = float(base_cfg.get("random_p_long", 0.5))
        random_n_runs = int(base_cfg.get("random_n_runs", 1))

        policies = {
            "buyhold": BuyHoldPolicy(),
            "flat": FlatPolicy(),
            f"sma_{sma_window}": SMATrendPolicy(sma_window=sma_window),
        }

        if random_n_runs <= 1:
            policies[f"random_s{rand_seed}"] = RandomPolicy(seed=rand_seed, p_long=rand_p_long)
        else:
            for i in range(random_n_runs):
                policies[f"random_{i+1:02d}"] = RandomPolicy(seed=rand_seed + i, p_long=rand_p_long)

        metrics_all = {}
        equity_map = {}
        sanity_results = []

        for label, policy in policies.items():
            signals_df = policy.compute_signals(df_feat)

            sim_df = _simulate_daily_adapter(
                df_feat,
                signals_df,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
                slippage_vol_k=slippage_vol_k,
                slippage_k_legacy=slippage_k_legacy,
                initial_equity=initial_equity,
                execution_lag=execution_lag,
            )

            sim_df.to_csv(run_dir / f"sim_{label}.csv", index=False)
            metrics_all[label] = compute_metrics(sim_df)

            if (
                label in ("buyhold", "flat", f"sma_{sma_window}")
                or label.startswith("random_01")
                or label.startswith("random_s")
            ):
                equity_map[label] = sim_df

            if label == "buyhold":
                sanity_results.append(sanity_buyhold_matches_theory(sim_df))
            if label == "flat":
                sanity_results.append(sanity_flat_has_no_pnl(sim_df))

        save_json(metrics_all, run_dir / "baselines_metrics.json")
        save_json(sanity_results, run_dir / "sanity_checks.json")
        plot_multi_equity(equity_map, run_dir / "plots" / "baselines_equity.png")

        print(
            "[ThothMind] saved baselines sims + baselines_metrics.json + "
            "sanity_checks.json + baselines_equity.png"
        )

    # Milestone 4: walk-forward (outer loop) OOS evaluation
    if stage in ("m4", "all"):
        from thothmind.core.backtest.baseline_policy import (
            BuyHoldPolicy,
            FlatPolicy,
            SMATrendPolicy,
            RandomPolicy,
        )
        from thothmind.core.splits.walkforward import generate_walkforward_splits
        from thothmind.core.backtest.walkforward import run_walkforward_oos
        from thothmind.core.reports.plots import plot_equity, plot_drawdown

        if df_feat is None:
            raise RuntimeError("df_feat is required for m4, but was not built.")

        wf_cfg = cfg.get("walkforward", {}) or {}
        train_size = int(wf_cfg.get("train_size", 756))
        test_size = int(wf_cfg.get("test_size", 63))
        step = int(wf_cfg.get("step", 63))

        pol_cfg = cfg.get("wf_policy", {}) or {}
        policy_type = str(pol_cfg.get("type", "sma")).lower()

        if policy_type == "buyhold":
            policy = BuyHoldPolicy()
        elif policy_type == "flat":
            policy = FlatPolicy()
        elif policy_type == "random":
            seed = int(pol_cfg.get("seed", int(cfg.get("run", {}).get("seed", 42))))
            p_long = float(pol_cfg.get("p_long", 0.5))
            policy = RandomPolicy(seed=seed, p_long=p_long)
        else:
            sma_window = int(pol_cfg.get("sma_window", 200))
            policy = SMATrendPolicy(sma_window=sma_window)

        signals_full = policy.compute_signals(df_feat)

        splits = generate_walkforward_splits(
            n_rows=len(df_feat),
            train_size=train_size,
            test_size=test_size,
            step=step,
        )

        kwargs = dict(
            df_feat=df_feat,
            signals_full=signals_full,
            splits=splits,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            slippage_vol_k=slippage_vol_k,
            initial_equity=initial_equity,
            execution_lag=execution_lag,
        )
        sim_oos_df, window_metrics_df, run_metrics = _call_with_costs_adapter(
            run_walkforward_oos, kwargs, costs
        )

        sim_oos_df.to_csv(run_dir / "sim_oos.csv", index=False)
        window_metrics_df.to_csv(run_dir / "window_metrics.csv", index=False)
        save_json(run_metrics, run_dir / "run_metrics.json")

        plot_equity(sim_oos_df, run_dir / "plots" / "wf_equity.png")
        plot_drawdown(sim_oos_df, run_dir / "plots" / "wf_drawdown.png")

        print("[ThothMind] saved sim_oos.csv + window_metrics.csv + wf plots")

    # Milestone 5: ML walk-forward (train->predict test) + decision layer (0/50/100)
    if stage in ("m5", "all"):
        from thothmind.core.features.pipeline import infer_feature_columns
        from thothmind.core.splits.walkforward import generate_walkforward_splits
        from thothmind.core.backtest.walkforward_ml import run_walkforward_ml_oos
        from thothmind.core.reports.plots import plot_equity, plot_drawdown

        if df_feat is None:
            raise RuntimeError("df_feat is required for m5, but was not built.")

        feature_cols = infer_feature_columns(df_feat)

        wf_cfg = cfg.get("walkforward", {}) or {}
        train_size = int(wf_cfg.get("train_size", 756))
        test_size = int(wf_cfg.get("test_size", 63))
        step = int(wf_cfg.get("step", 63))

        splits = generate_walkforward_splits(
            n_rows=len(df_feat),
            train_size=train_size,
            test_size=test_size,
            step=step,
        )

        model_cfg = cfg.get("model", {}) or {}
        decision_cfg = cfg.get("decision", {}) or {}

        kwargs = dict(
            df_feat=df_feat,
            feature_cols=feature_cols,
            splits=splits,
            model_cfg=model_cfg,
            decision_cfg=decision_cfg,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            slippage_vol_k=slippage_vol_k,
            initial_equity=initial_equity,
            execution_lag=execution_lag,
        )
        sim_oos_df, window_metrics_df, preds_oos_df, signals_oos_df, run_metrics = _call_with_costs_adapter(
            run_walkforward_ml_oos, kwargs, costs
        )

        preds_oos_df.to_csv(run_dir / "predictions_oos.csv", index=False)
        signals_oos_df.to_csv(run_dir / "signals_oos.csv", index=False)
        sim_oos_df.to_csv(run_dir / "sim_oos.csv", index=False)
        window_metrics_df.to_csv(run_dir / "window_metrics.csv", index=False)
        save_json(run_metrics, run_dir / "run_metrics.json")
        save_json({"feature_cols": feature_cols}, run_dir / "feature_cols.json")

        plot_equity(sim_oos_df, run_dir / "plots" / "wf_equity.png")
        plot_drawdown(sim_oos_df, run_dir / "plots" / "wf_drawdown.png")

        print(
            "[ThothMind] saved predictions_oos.csv + signals_oos.csv + "
            "sim_oos.csv + window_metrics.csv + wf plots"
        )

    # Milestone 6: ML walk-forward with conformal intervals (90%) + uncertainty gating
    if stage in ("m6", "all"):
        from thothmind.core.features.pipeline import infer_feature_columns
        from thothmind.core.splits.walkforward import generate_walkforward_splits
        from thothmind.core.backtest.walkforward_ml_conformal import run_walkforward_ml_conformal_oos
        from thothmind.core.reports.plots import plot_equity, plot_drawdown

        if df_feat is None:
            raise RuntimeError("df_feat is required for m6, but was not built.")

        feature_cols = infer_feature_columns(df_feat)

        wf_cfg = cfg.get("walkforward", {}) or {}
        train_size = int(wf_cfg.get("train_size", 756))
        test_size = int(wf_cfg.get("test_size", 63))
        step = int(wf_cfg.get("step", 63))

        splits = generate_walkforward_splits(
            n_rows=len(df_feat),
            train_size=train_size,
            test_size=test_size,
            step=step,
        )

        model_cfg = cfg.get("model", {}) or {}
        conformal_cfg = cfg.get("conformal", {"alpha": 0.10}) or {"alpha": 0.10}

        kwargs = dict(
            df_feat=df_feat,
            feature_cols=feature_cols,
            splits=splits,
            model_cfg=model_cfg,
            conformal_cfg=conformal_cfg,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            slippage_vol_k=slippage_vol_k,
            initial_equity=initial_equity,
            execution_lag=execution_lag,
        )
        sim_oos_df, window_metrics_df, preds_oos_df, signals_oos_df, run_metrics = _call_with_costs_adapter(
            run_walkforward_ml_conformal_oos, kwargs, costs
        )

        preds_oos_df.to_csv(run_dir / "predictions_oos.csv", index=False)
        signals_oos_df.to_csv(run_dir / "signals_oos.csv", index=False)
        sim_oos_df.to_csv(run_dir / "sim_oos.csv", index=False)
        window_metrics_df.to_csv(run_dir / "window_metrics.csv", index=False)
        save_json(run_metrics, run_dir / "run_metrics.json")
        save_json({"feature_cols": feature_cols}, run_dir / "feature_cols.json")

        plot_equity(sim_oos_df, run_dir / "plots" / "wf_equity.png")
        plot_drawdown(sim_oos_df, run_dir / "plots" / "wf_drawdown.png")

        print("[ThothMind] saved conformal predictions + signals + OOS sim + window metrics + wf plots")

    # Milestone 7: Bootstrap significance on OOS outperformance (strategy vs buy&hold)
    if stage in ("m7", "all"):
        from thothmind.core.features.pipeline import infer_feature_columns
        from thothmind.core.splits.walkforward import generate_walkforward_splits
        from thothmind.core.backtest.walkforward_ml_conformal import run_walkforward_ml_conformal_oos
        from thothmind.core.backtest.walkforward import run_walkforward_oos
        from thothmind.core.backtest.baseline_policy import BuyHoldPolicy
        from thothmind.core.reports.plots import plot_equity, plot_drawdown, plot_bootstrap_distribution
        from thothmind.core.stats.significance import bootstrap_oos_outperformance

        if df_feat is None:
            raise RuntimeError("df_feat is required for m7, but was not built.")

        feature_cols = infer_feature_columns(df_feat)

        wf_cfg = cfg.get("walkforward", {}) or {}
        train_size = int(wf_cfg.get("train_size", 756))
        test_size = int(wf_cfg.get("test_size", 63))
        step = int(wf_cfg.get("step", 63))

        splits = generate_walkforward_splits(
            n_rows=len(df_feat),
            train_size=train_size,
            test_size=test_size,
            step=step,
        )

        model_cfg = cfg.get("model", {}) or {}
        conformal_cfg = cfg.get("conformal", {"alpha": 0.10}) or {"alpha": 0.10}

        kwargs_strat = dict(
            df_feat=df_feat,
            feature_cols=feature_cols,
            splits=splits,
            model_cfg=model_cfg,
            conformal_cfg=conformal_cfg,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            slippage_vol_k=slippage_vol_k,
            initial_equity=initial_equity,
            execution_lag=execution_lag,
        )
        sim_oos_strat, window_metrics_strat, preds_oos, sig_oos, run_metrics_strat = _call_with_costs_adapter(
            run_walkforward_ml_conformal_oos, kwargs_strat, costs
        )

        preds_oos.to_csv(run_dir / "predictions_oos.csv", index=False)
        sig_oos.to_csv(run_dir / "signals_oos.csv", index=False)
        sim_oos_strat.to_csv(run_dir / "sim_oos.csv", index=False)
        window_metrics_strat.to_csv(run_dir / "window_metrics.csv", index=False)
        save_json(run_metrics_strat, run_dir / "run_metrics.json")
        save_json({"feature_cols": feature_cols}, run_dir / "feature_cols.json")

        plot_equity(sim_oos_strat, run_dir / "plots" / "wf_equity.png")
        plot_drawdown(sim_oos_strat, run_dir / "plots" / "wf_drawdown.png")

        # Buy&Hold baseline under SAME WF protocol
        bh_policy = BuyHoldPolicy()
        bh_signals_full = bh_policy.compute_signals(df_feat)

        kwargs_bh = dict(
            df_feat=df_feat,
            signals_full=bh_signals_full,
            splits=splits,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            slippage_vol_k=slippage_vol_k,
            initial_equity=initial_equity,
            execution_lag=execution_lag,
        )
        sim_oos_bh, _, bh_metrics = _call_with_costs_adapter(run_walkforward_oos, kwargs_bh, costs)

        sim_oos_bh.to_csv(run_dir / "sim_oos_buyhold.csv", index=False)
        save_json(bh_metrics, run_dir / "run_metrics_buyhold.json")

        boot_cfg = cfg.get("bootstrap", {}) or {}
        n_boot = int(boot_cfg.get("n_boot", 5000))
        block_len = int(boot_cfg.get("block_len", 20))
        ci_alpha = float(boot_cfg.get("ci_alpha", 0.05))
        seed = int(boot_cfg.get("seed", int(cfg.get("run", {}).get("seed", 42))))

        sig_summary, boot_df = bootstrap_oos_outperformance(
            sim_strategy=sim_oos_strat,
            sim_buyhold=sim_oos_bh,
            n_boot=n_boot,
            block_len=block_len,
            ci_alpha=ci_alpha,
            seed=seed,
        )

        save_json(sig_summary, run_dir / "oos_significance.json")
        boot_df.to_csv(run_dir / "bootstrap_samples.csv", index=False)

        plot_bootstrap_distribution(
            values=boot_df["boot_rel_return"].to_numpy(),
            actual_value=float(sig_summary["actual_rel_return"]),
            out_path=run_dir / "plots" / "bootstrap_rel_return_hist.png",
            title="Bootstrap OOS Outperformance vs Buy&Hold (Relative Return)",
        )

        print("[ThothMind] saved oos_significance.json + bootstrap_samples.csv + sim_oos_buyhold.csv + bootstrap plot")

    # Milestone 8: Multi-ticker OOS suite
    if stage in ("m8", "all"):
        from thothmind.core.suite.multiticker import run_multiticker_suite

        summary_df = run_multiticker_suite(cfg, run_dir)
        print(f"[ThothMind] saved suite_summary.csv for {len(summary_df)} tickers")
        print("[ThothMind] artifacts ->", run_dir / "tickers")

    print(f"[ThothMind] run_id = {run_id}")
    print(f"[ThothMind] artifacts -> {run_dir}")
    return run_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to YAML config")
    args = parser.parse_args()
    run_experiment(args.config)


if __name__ == "__main__":
    main()
