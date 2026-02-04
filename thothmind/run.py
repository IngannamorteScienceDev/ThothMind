import argparse

from .config import load_config, save_json
from .registry import make_run_id, init_run_dir, write_run_artifacts


def run_experiment(config_path: str) -> str:
    cfg = load_config(config_path)

    run_id = make_run_id(cfg)
    output_dir = cfg.get("run", {}).get("output_dir", "reports/runs")
    run_dir = init_run_dir(run_id, output_root=output_dir)

    # Always write base artifacts (Milestone 0)
    write_run_artifacts(run_dir, cfg)

    stage = cfg.get("pipeline", {}).get("stage", "m0")

    # Milestone 1/2/3/4/5 require df_feat
    df_feat = None
    if stage in ("m1", "m2", "m3", "m4", "m5", "all"):
        from thothmind.core.pipeline_m1 import build_df_feat

        df_feat, snapshot = build_df_feat(cfg)

        df_feat.to_csv(run_dir / "df_feat.csv", index=False)
        save_json(snapshot, run_dir / "data_snapshot.json")

        print(f"[ThothMind] saved df_feat.csv ({len(df_feat)} rows)")
        print("[ThothMind] saved data_snapshot.json")

    # Milestone 2: baseline signals + simulator + metrics + plots
    if stage in ("m2", "all"):
        from thothmind.core.backtest.baseline_policy import SMATrendPolicy
        from thothmind.core.backtest.simulator import simulate_daily
        from thothmind.core.backtest.metrics import compute_metrics
        from thothmind.core.reports.plots import plot_equity, plot_drawdown

        if df_feat is None:
            raise RuntimeError("df_feat is required for m2, but was not built.")

        pol_cfg = cfg.get("baseline_policy", {})
        sma_window = int(pol_cfg.get("sma_window", 200))

        policy = SMATrendPolicy(sma_window=sma_window)
        signals_df = policy.compute_signals(df_feat)

        cost_cfg = cfg.get("costs", {})
        commission_bps = float(cost_cfg.get("commission_bps", 2.0))
        slippage_k = float(cost_cfg.get("slippage_k", 0.15))

        sim_df = simulate_daily(
            df_feat=df_feat,
            signals_df=signals_df,
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            initial_equity=float(cfg.get("sim", {}).get("initial_equity", 1.0)),
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
        from thothmind.core.backtest.simulator import simulate_daily
        from thothmind.core.backtest.metrics import compute_metrics
        from thothmind.core.backtest.sanity import (
            sanity_buyhold_matches_theory,
            sanity_flat_has_no_pnl,
        )
        from thothmind.core.reports.plots import plot_multi_equity

        if df_feat is None:
            raise RuntimeError("df_feat is required for m3, but was not built.")

        base_cfg = cfg.get("baselines", {})
        sma_window = int(base_cfg.get("sma_window", 200))
        rand_seed = int(base_cfg.get("random_seed", int(cfg.get("run", {}).get("seed", 42))))
        rand_p_long = float(base_cfg.get("random_p_long", 0.5))
        random_n_runs = int(base_cfg.get("random_n_runs", 1))

        cost_cfg = cfg.get("costs", {})
        commission_bps = float(cost_cfg.get("commission_bps", 2.0))
        slippage_k = float(cost_cfg.get("slippage_k", 0.15))

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

            sim_df = simulate_daily(
                df_feat=df_feat,
                signals_df=signals_df,
                commission_bps=commission_bps,
                slippage_k=slippage_k,
                initial_equity=float(cfg.get("sim", {}).get("initial_equity", 1.0)),
            )

            sim_df.to_csv(run_dir / f"sim_{label}.csv", index=False)

            metrics_all[label] = compute_metrics(sim_df)

            # Keep key curves + first random for plotting
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

        wf_cfg = cfg.get("walkforward", {})
        train_size = int(wf_cfg.get("train_size", 756))
        test_size = int(wf_cfg.get("test_size", 63))
        step = int(wf_cfg.get("step", 63))

        pol_cfg = cfg.get("wf_policy", {})
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

        cost_cfg = cfg.get("costs", {})
        commission_bps = float(cost_cfg.get("commission_bps", 2.0))
        slippage_k = float(cost_cfg.get("slippage_k", 0.15))
        initial_equity = float(cfg.get("sim", {}).get("initial_equity", 1.0))

        splits = generate_walkforward_splits(
            n_rows=len(df_feat),
            train_size=train_size,
            test_size=test_size,
            step=step,
        )

        sim_oos_df, window_metrics_df, run_metrics = run_walkforward_oos(
            df_feat=df_feat,
            signals_full=signals_full,
            splits=splits,
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            initial_equity=initial_equity,
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

        wf_cfg = cfg.get("walkforward", {})
        train_size = int(wf_cfg.get("train_size", 756))
        test_size = int(wf_cfg.get("test_size", 63))
        step = int(wf_cfg.get("step", 63))

        splits = generate_walkforward_splits(
            n_rows=len(df_feat),
            train_size=train_size,
            test_size=test_size,
            step=step,
        )

        cost_cfg = cfg.get("costs", {})
        commission_bps = float(cost_cfg.get("commission_bps", 2.0))
        slippage_k = float(cost_cfg.get("slippage_k", 0.15))
        initial_equity = float(cfg.get("sim", {}).get("initial_equity", 1.0))

        model_cfg = cfg.get("model", {})
        decision_cfg = cfg.get("decision", {})

        sim_oos_df, window_metrics_df, preds_oos_df, signals_oos_df, run_metrics = run_walkforward_ml_oos(
            df_feat=df_feat,
            feature_cols=feature_cols,
            splits=splits,
            model_cfg=model_cfg,
            decision_cfg=decision_cfg,
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            initial_equity=initial_equity,
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
