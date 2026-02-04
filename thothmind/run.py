import argparse

from .config import load_config
from .registry import make_run_id, init_run_dir, write_run_artifacts


def run_experiment(config_path: str) -> str:
    cfg = load_config(config_path)

    run_id = make_run_id(cfg)
    output_dir = cfg.get("run", {}).get("output_dir", "reports/runs")
    run_dir = init_run_dir(run_id, output_root=output_dir)
    write_run_artifacts(run_dir, cfg)

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
