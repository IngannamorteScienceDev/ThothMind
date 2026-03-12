from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table

    console = Console()
except Exception:
    console = None


DEMO_CONFIGS: list[dict[str, object]] = [
    {
        "config": "demo_m8_true_multi_base.yaml",
        "stage": "m8",
        "suite_mode": "true_multi",
        "return_bias": 0.0,
        "sharpe_bias": 0.00,
        "drawdown_bias": 0.0,
        "gap_bias": -2.0,
        "p_value_bias": 0.18,
    },
    {
        "config": "demo_m8_true_multi_h5.yaml",
        "stage": "m8",
        "suite_mode": "true_multi",
        "return_bias": 6.0,
        "sharpe_bias": 0.04,
        "drawdown_bias": -2.0,
        "gap_bias": -1.0,
        "p_value_bias": 0.12,
    },
    {
        "config": "demo_m8_true_multi_h10.yaml",
        "stage": "m8",
        "suite_mode": "true_multi",
        "return_bias": 11.0,
        "sharpe_bias": 0.08,
        "drawdown_bias": -3.0,
        "gap_bias": 0.2,
        "p_value_bias": 0.08,
    },
    {
        "config": "demo_m8_true_multi_h20.yaml",
        "stage": "m8",
        "suite_mode": "true_multi",
        "return_bias": 8.0,
        "sharpe_bias": 0.06,
        "drawdown_bias": -1.0,
        "gap_bias": -0.2,
        "p_value_bias": 0.10,
    },
    {
        "config": "demo_m9_defensive_base.yaml",
        "stage": "m9",
        "suite_mode": "true_multi",
        "return_bias": 2.0,
        "sharpe_bias": 0.10,
        "drawdown_bias": -8.0,
        "gap_bias": -4.0,
        "p_value_bias": 0.20,
    },
    {
        "config": "demo_m9_defensive_regime.yaml",
        "stage": "m9",
        "suite_mode": "true_multi",
        "return_bias": 4.0,
        "sharpe_bias": 0.14,
        "drawdown_bias": -10.0,
        "gap_bias": -3.0,
        "p_value_bias": 0.17,
    },
    {
        "config": "demo_m9_aggressive_base.yaml",
        "stage": "m9",
        "suite_mode": "true_multi",
        "return_bias": 15.0,
        "sharpe_bias": -0.02,
        "drawdown_bias": 4.0,
        "gap_bias": 2.0,
        "p_value_bias": 0.14,
    },
    {
        "config": "demo_m9_aggressive_trend.yaml",
        "stage": "m9",
        "suite_mode": "true_multi",
        "return_bias": 22.0,
        "sharpe_bias": 0.01,
        "drawdown_bias": 6.0,
        "gap_bias": 4.0,
        "p_value_bias": 0.09,
    },
]


def log(message: str) -> None:
    if console:
        console.print(message)
    else:
        print(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a synthetic frontend interface snapshot on top of real ticker symbols."
        )
    )
    parser.add_argument(
        "--frontend-dir",
        default="frontend",
        help="Frontend root directory",
    )
    parser.add_argument(
        "--data-root",
        default="data",
        help="Root folder with Stocks/ and ETFs/",
    )
    parser.add_argument(
        "--stocks-dir",
        default="Stocks",
        help="Stocks subfolder name inside data-root",
    )
    parser.add_argument(
        "--etfs-dir",
        default="ETFs",
        help="ETFs subfolder name inside data-root",
    )
    parser.add_argument(
        "--target-mode",
        default="demo",
        choices=["demo", "research"],
        help="Frontend data mode to write into. Default is demo.",
    )
    parser.add_argument(
        "--max-tickers",
        type=int,
        default=500,
        help=(
            "Maximum number of real tickers to include. "
            "Use 0 to include all available tickers."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic sampling seed",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete target mode directory before writing new demo files",
    )
    return parser.parse_args()


def stable_seed(*parts: object) -> int:
    raw = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16)


def stable_rng(*parts: object) -> random.Random:
    return random.Random(stable_seed(*parts))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def ticker_from_filename(path: Path) -> str:
    name = path.name
    if name.endswith(".us.txt"):
        return name[:-7]
    if name.endswith(".txt"):
        return name[:-4]
    return path.stem


def collect_tickers(data_root: Path, stocks_dir_name: str, etfs_dir_name: str) -> tuple[list[str], list[str]]:
    stocks_dir = data_root / stocks_dir_name
    etfs_dir = data_root / etfs_dir_name

    if not stocks_dir.exists():
        raise FileNotFoundError(f"Stocks dir not found: {stocks_dir}")
    if not etfs_dir.exists():
        raise FileNotFoundError(f"ETFs dir not found: {etfs_dir}")

    stocks = sorted(
        {
            ticker_from_filename(path)
            for path in stocks_dir.glob("*.txt")
            if path.is_file()
        }
    )
    etfs = sorted(
        {
            ticker_from_filename(path)
            for path in etfs_dir.glob("*.txt")
            if path.is_file()
        }
    )

    if not stocks and not etfs:
        raise FileNotFoundError(
            "No ticker files were found in the provided raw dataset folders."
        )

    return stocks, etfs


def sample_tickers(
    stocks: list[str],
    etfs: list[str],
    max_tickers: int,
    seed: int,
) -> tuple[list[str], list[str]]:
    total_available = len(stocks) + len(etfs)
    if total_available == 0:
        return [], []

    if max_tickers < 0:
        raise ValueError("--max-tickers must be >= 0")

    if max_tickers == 0 or max_tickers >= total_available:
        return stocks[:], etfs[:]

    rng = random.Random(seed)

    target_stocks = round(max_tickers * len(stocks) / total_available)
    target_etfs = max_tickers - target_stocks

    target_stocks = min(target_stocks, len(stocks))
    target_etfs = min(target_etfs, len(etfs))

    picked = target_stocks + target_etfs
    if picked < max_tickers:
        remaining = max_tickers - picked

        extra_stocks = min(len(stocks) - target_stocks, remaining)
        target_stocks += extra_stocks
        remaining -= extra_stocks

        extra_etfs = min(len(etfs) - target_etfs, remaining)
        target_etfs += extra_etfs

    selected_stocks = sorted(rng.sample(stocks, target_stocks)) if target_stocks else []
    selected_etfs = sorted(rng.sample(etfs, target_etfs)) if target_etfs else []

    return selected_stocks, selected_etfs


def build_ticker_row(ticker: str, config_profile: dict[str, object]) -> dict[str, object]:
    config_name = str(config_profile["config"])

    base_rng = stable_rng("ticker-base", ticker)
    cfg_rng = stable_rng("ticker-config", ticker, config_name)

    base_return = -5 + base_rng.random() * 85
    base_sharpe = -0.25 + base_rng.random() * 1.15
    base_drawdown = 12 + base_rng.random() * 28
    base_gap = -18 + base_rng.random() * 22

    return_value = (
        base_return
        + float(config_profile["return_bias"])
        + (-18 + cfg_rng.random() * 18)
    )
    return_value = clamp(return_value, -35, 180)

    sharpe_value = (
        base_sharpe
        + float(config_profile["sharpe_bias"])
        + (-0.18 + cfg_rng.random() * 0.22)
    )
    sharpe_value = clamp(sharpe_value, -0.55, 1.85)

    drawdown_value = -(
        base_drawdown
        + float(config_profile["drawdown_bias"])
        + (-6 + cfg_rng.random() * 8)
    )
    drawdown_value = clamp(drawdown_value, -65, -4)

    gap_value = (
        base_gap
        + float(config_profile["gap_bias"])
        + (-7 + cfg_rng.random() * 8)
    )
    gap_value = clamp(gap_value, -60, 40)

    p_value = (
        0.65
        - (gap_value / 120.0)
        - (sharpe_value / 8.0)
        + float(config_profile["p_value_bias"])
        + cfg_rng.random() * 0.12
    )
    p_value = clamp(p_value, 0.02, 0.98)

    return {
        "config": config_name,
        "ticker": ticker,
        "status": "ok",
        "strat_total_return": round(return_value, 4),
        "strat_sharpe": round(sharpe_value, 4),
        "strat_max_drawdown": round(drawdown_value, 4),
        "actual_rel_return": round(gap_value, 4),
        "p_value_one_sided": round(p_value, 4),
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_suite_row(
    config_profile: dict[str, object],
    ticker_rows_for_config: list[dict[str, object]],
    n_suite_tickers: int,
) -> dict[str, object]:
    returns = [float(row["strat_total_return"]) for row in ticker_rows_for_config]
    sharpes = [float(row["strat_sharpe"]) for row in ticker_rows_for_config]
    drawdowns = [float(row["strat_max_drawdown"]) for row in ticker_rows_for_config]
    gaps = [float(row["actual_rel_return"]) for row in ticker_rows_for_config]
    p_values = [float(row["p_value_one_sided"]) for row in ticker_rows_for_config]

    avg_return = mean(returns)
    avg_sharpe = mean(sharpes)
    avg_drawdown = mean(drawdowns)
    avg_gap = mean(gaps)
    avg_p_value = mean(p_values)

    composite_score = (
        50.0
        + avg_return * 0.28
        + avg_sharpe * 18.0
        - abs(avg_drawdown) * 0.55
        - avg_p_value * 18.0
        + avg_gap * 0.45
    )
    composite_score = clamp(composite_score, 0.0, 100.0)

    config_name = str(config_profile["config"])
    return {
        "config": config_name,
        "ticker": "SUITE",
        "stage": str(config_profile["stage"]),
        "suite_mode": str(config_profile["suite_mode"]),
        "n_suite_tickers": n_suite_tickers,
        "is_single_ticker_suite": False,
        "exclude_from_showcase": False,
        "return_metric_pct": round(avg_return, 4),
        "actual_rel_return_pct": round(avg_gap, 4),
        "sharpe": round(avg_sharpe, 4),
        "max_drawdown_pct": round(avg_drawdown, 4),
        "p_value_one_sided": round(avg_p_value, 4),
        # kept for frontend/backward compatibility
        "defense_ready_score": round(composite_score, 3),
        "run_dir": f"demo://runs/{config_name.replace('.yaml', '')}",
    }


def add_ranks(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    ranked: list[dict[str, object]] = []
    for idx, row in enumerate(rows, start=1):
        copy_row = dict(row)
        copy_row["rank"] = idx
        ranked.append(copy_row)
    return ranked


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    frontend_dir = (repo_root / args.frontend_dir).resolve()
    data_root = (repo_root / args.data_root).resolve()

    if not frontend_dir.exists():
        raise FileNotFoundError(f"Frontend dir not found: {frontend_dir}")
    if not data_root.exists():
        raise FileNotFoundError(f"Data root not found: {data_root}")

    stocks, etfs = collect_tickers(data_root, args.stocks_dir, args.etfs_dir)
    selected_stocks, selected_etfs = sample_tickers(
        stocks=stocks,
        etfs=etfs,
        max_tickers=args.max_tickers,
        seed=args.seed,
    )
    selected_all = selected_stocks + selected_etfs

    if not selected_all:
        raise RuntimeError("No tickers were selected for the demo snapshot.")

    target_root = frontend_dir / "public" / "data" / args.target_mode
    if args.clean and target_root.exists():
        shutil.rmtree(target_root)

    ticker_rows: list[dict[str, object]] = []
    suite_rows: list[dict[str, object]] = []

    for profile in DEMO_CONFIGS:
        rows_for_config = [
            build_ticker_row(ticker=ticker, config_profile=profile)
            for ticker in selected_all
        ]
        ticker_rows.extend(rows_for_config)
        suite_rows.append(
            build_suite_row(
                config_profile=profile,
                ticker_rows_for_config=rows_for_config,
                n_suite_tickers=len(selected_all),
            )
        )

    top_by_return = add_ranks(
        sorted(
            suite_rows,
            key=lambda row: float(row["return_metric_pct"]),
            reverse=True,
        )[:10]
    )
    top_by_score = add_ranks(
        sorted(
            suite_rows,
            key=lambda row: float(row["defense_ready_score"]),
            reverse=True,
        )[:10]
    )

    manifest = {
        "mode": args.target_mode,
        "is_synthetic_demo": True,
        "label": "Interactive interface demonstration based on synthetic sample data",
        "raw_stocks_available": len(stocks),
        "raw_etfs_available": len(etfs),
        "stocks_count": len(selected_stocks),
        "etfs_count": len(selected_etfs),
        "total_expected": len(selected_all),
        "total_copied": len(selected_all),
        "missing_files_count": 0,
        "selection_params": {
            "max_tickers": args.max_tickers,
            "seed": args.seed,
            "n_configs": len(DEMO_CONFIGS),
            "data_root": str(data_root),
            "selection_source": "real ticker symbols from raw dataset",
        },
        "notes": [
            "Synthetic interface dataset for GitHub Pages / click-through demo.",
            "Ticker symbols are real and sourced from the raw dataset.",
            "Performance metrics are synthetic and must not be presented as real experiment results.",
        ],
    }

    overview = {
        "mode": args.target_mode,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_suite_runs": len(suite_rows),
        "n_ticker_rows": len(ticker_rows),
        "n_unique_tickers": len(selected_all),
        "raw_stocks_available": len(stocks),
        "raw_etfs_available": len(etfs),
        "configs": [str(profile["config"]) for profile in DEMO_CONFIGS],
        "target_root": str(target_root),
    }

    selected_preview = {
        "stocks": selected_stocks[:50],
        "etfs": selected_etfs[:50],
        "all_count": len(selected_all),
    }

    write_json(target_root / "index" / "all_results_index.json", suite_rows)
    write_json(target_root / "index" / "suite_ticker_results_index.json", ticker_rows)
    write_json(target_root / "showcase" / "top10_by_return.json", top_by_return)
    write_json(target_root / "showcase" / "top10_defense_ready.json", top_by_score)
    write_json(target_root / "meta" / "curated_manifest.json", manifest)
    write_json(target_root / "meta" / "demo_overview.json", overview)
    write_json(target_root / "meta" / "selected_tickers_preview.json", selected_preview)

    if console:
        table = Table(title="Synthetic frontend demo snapshot summary")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Mode", args.target_mode)
        table.add_row("Target root", str(target_root))
        table.add_row("Raw stocks available", str(len(stocks)))
        table.add_row("Raw ETFs available", str(len(etfs)))
        table.add_row("Selected stocks", str(len(selected_stocks)))
        table.add_row("Selected ETFs", str(len(selected_etfs)))
        table.add_row("Selected total", str(len(selected_all)))
        table.add_row("Suite rows", str(len(suite_rows)))
        table.add_row("Ticker rows", str(len(ticker_rows)))
        table.add_row("Configs", str(len(DEMO_CONFIGS)))
        console.print(table)
    else:
        print(
            json.dumps(
                {
                    "mode": args.target_mode,
                    "selected_total": len(selected_all),
                    "suite_rows": len(suite_rows),
                    "ticker_rows": len(ticker_rows),
                    "target_root": str(target_root),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    log(
        f"[bold green]Done.[/bold green] Generated synthetic frontend snapshot at: {target_root}"
        if console
        else f"Done. Generated synthetic frontend snapshot at: {target_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())