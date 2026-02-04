import argparse
from pathlib import Path

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
    if stage in ("m1", "all"):
        from thothmind.core.pipeline_m1 import build_df_feat

        df_feat, snapshot = build_df_feat(cfg)

        df_feat.to_csv(run_dir / "df_feat.csv", index=False)
        save_json(snapshot, run_dir / "data_snapshot.json")

        print(f"[ThothMind] saved df_feat.csv ({len(df_feat)} rows)")
        print(f"[ThothMind] saved data_snapshot.json")

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
