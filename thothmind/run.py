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

    # Milestone 1: build df_feat + snapshot
    df_feat = None
    if stage in ("m1", "m2", "all"):
        from thothmind.core.pipeline_m1 import build_df_feat

        df_feat, snapshot = build_df_feat(cfg)

        df_feat.to_csv(run_dir / "df_feat.csv", index=False)
        save_json(snapshot, run_dir / "data_snapshot.json")

        print(f"[ThothMind] saved df_feat.csv ({len(df_feat)} rows)")
        print(f"[ThothMind] saved data_snapshot.json")

    # Milestone 2: baseline signals + simulator + metrics + plots
    if stage in ("m2", "all"):
        from thothmind.core.backtest.baseline_policy import SMATrendPolicy
        from thothmind.core.backtest.simulator import simulate_daily
        from thothmind.core.backtest.metrics import compute_metrics
        from thothmind.core.reports.plots import plot_equity, plot_drawdown

        if df_feat is None:
            raise RuntimeError("df_feat is required for m2, but was not built.")

        # Baseline policy config
        pol_cfg = cfg.get("baseline_policy", {})
        sma_window = int(pol_cfg.get("sma_window", 200))

        policy = SMATrendPolicy(sma_window=sma_window)
        signals_df = policy.compute_signals(df_feat)

        # Costs config
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
