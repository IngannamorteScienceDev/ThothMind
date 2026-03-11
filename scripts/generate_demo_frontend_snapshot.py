from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table

    console = Console()
except Exception:
    console = None


def log(message: str) -> None:
    if console:
        console.print(message)
    else:
        print(message)


@dataclass(frozen=True)
class ConfigSpec:
    config: str
    stage: str
    profile: str
    ret_shift: float
    sharpe_shift: float
    dd_shift: float
    p_shift: float
    exposure_bias: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a synthetic demo snapshot for the frontend using real ticker symbols."
    )
    parser.add_argument(
        "--data-root",
        default="data",
        help="Root folder with Stocks/ and ETFs/",
    )
    parser.add_argument(
        "--frontend-dir",
        default="frontend",
        help="Frontend root directory",
    )
    parser.add_argument(
        "--target-mode",
        default="demo",
        choices=["demo", "research"],
        help="Target frontend mode to publish into",
    )
    parser.add_argument(
        "--max-tickers",
        type=int,
        default=1500,
        help="How many real ticker symbols to include. Use 0 for all.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete target mode directory before generating files",
    )
    return parser.parse_args()


def ticker_from_filename(path: Path) -> str:
    name = path.name
    if name.endswith(".us.txt"):
        return name[:-7].upper()
    return path.stem.split(".")[0].upper()


def stable_unit_value(key: str, seed: int) -> float:
    digest = hashlib.md5(f"{seed}|{key}".encode("utf-8")).hexdigest()
    value = int(digest[:12], 16)
    return value / float(16**12 - 1)


def stable_gauss(key: str, seed: int, mean: float, std: float) -> float:
    rng = random.Random(int(stable_unit_value(key, seed) * 10_000_000))
    return rng.gauss(mean, std)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = clamp(q, 0.0, 1.0) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def defense_score(return_pct: float, sharpe: float, max_dd_pct: float, p_value: float) -> float:
    dd_penalty = abs(max_dd_pct)
    score = (
        0.35 * return_pct
        + 18.0 * sharpe
        - 0.45 * dd_penalty
        - 16.0 * p_value
    )
    return round(score, 3)


def list_real_tickers(data_root: Path) -> tuple[list[str], list[str]]:
    stocks_dir = data_root / "Stocks"
    etfs_dir = data_root / "ETFs"

    if not stocks_dir.exists():
        raise FileNotFoundError(f"Stocks dir not found: {stocks_dir}")
    if not etfs_dir.exists():
        raise FileNotFoundError(f"ETFs dir not found: {etfs_dir}")

    stock_tickers = sorted(ticker_from_filename(p) for p in stocks_dir.glob("*.txt"))
    etf_tickers = sorted(ticker_from_filename(p) for p in etfs_dir.glob("*.txt"))
    return stock_tickers, etf_tickers


def build_config_specs() -> list[ConfigSpec]:
    return [
        ConfigSpec("demo_m8_true_multi_base.yaml", "m8", "balanced", 0.00, 0.00, 0.00, 0.00, 0.00),
        ConfigSpec("demo_m8_true_multi_h5.yaml", "m8", "balanced", -1.5, 0.03, -1.0, 0.02, -0.02),
        ConfigSpec("demo_m8_true_multi_h10.yaml", "m8", "balanced", 0.8, 0.05, -0.8, -0.02, 0.00),
        ConfigSpec("demo_m8_true_multi_h20.yaml", "m8", "balanced", 1.6, 0.02, 0.4, -0.03, 0.01),
        ConfigSpec("demo_m9_defensive_base.yaml", "m9", "defensive", -7.0, 0.08, -6.0, 0.06, -0.10),
        ConfigSpec("demo_m9_defensive_regime.yaml", "m9", "defensive", -4.5, 0.11, -7.5, 0.04, -0.12),
        ConfigSpec("demo_m9_aggressive_base.yaml", "m9", "aggressive", 7.5, -0.01, 4.5, -0.04, 0.10),
        ConfigSpec("demo_m9_aggressive_trend.yaml", "m9", "aggressive", 10.0, -0.03, 6.5, -0.06, 0.14),
    ]


def choose_demo_tickers(stock_tickers: list[str], etf_tickers: list[str], max_tickers: int, seed: int) -> tuple[list[str], int, int]:
    if max_tickers <= 0:
        selected_stocks = stock_tickers
        selected_etfs = etf_tickers
    else:
        total_available = len(stock_tickers) + len(etf_tickers)
        if total_available <= max_tickers:
            selected_stocks = stock_tickers
            selected_etfs = etf_tickers
        else:
            rng = random.Random(seed)
            target_stock_count = round(max_tickers * (len(stock_tickers) / total_available))
            target_etf_count = max_tickers - target_stock_count
            target_stock_count = clamp(target_stock_count, 1, len(stock_tickers))
            target_etf_count = clamp(target_etf_count, 1, len(etf_tickers))

            selected_stocks = sorted(rng.sample(stock_tickers, int(target_stock_count)))
            selected_etfs = sorted(rng.sample(etf_tickers, int(target_etf_count)))

    selected_all = selected_stocks + selected_etfs
    return selected_all, len(selected_stocks), len(selected_etfs)


def build_ticker_rows(
    tickers: list[str],
    configs: list[ConfigSpec],
    seed: int,
) -> list[dict]:
    rows: list[dict] = []

    for cfg in configs:
        for ticker in tickers:
            quality = stable_unit_value(f"{ticker}:quality", seed)
            cyclic = stable_unit_value(f"{ticker}:cyclic", seed)
            defensiveness = stable_unit_value(f"{ticker}:defense", seed)
            noise = stable_gauss(f"{cfg.config}:{ticker}:noise", seed, 0.0, 8.0)

            buyhold_return = 12.0 + quality * 70.0 + cyclic * 22.0 + noise
            buyhold_return = clamp(buyhold_return, -35.0, 240.0)

            strategy_return = (
                buyhold_return
                - 6.0
                + cfg.ret_shift
                + (quality - 0.5) * 18.0
                + (defensiveness - 0.5) * (8.0 if cfg.profile == "defensive" else -4.0)
                + stable_gauss(f"{cfg.config}:{ticker}:ret", seed, 0.0, 10.0)
            )
            strategy_return = clamp(strategy_return, -45.0, 220.0)

            sharpe = (
                0.18
                + quality * 0.65
                + cfg.sharpe_shift
                + (0.10 if cfg.profile == "defensive" else -0.04)
                + stable_gauss(f"{cfg.config}:{ticker}:sharpe", seed, 0.0, 0.08)
            )
            sharpe = clamp(sharpe, -0.20, 1.85)

            max_drawdown = (
                -10.0
                - (1.0 - quality) * 18.0
                - cyclic * 8.0
                + cfg.dd_shift
                + stable_gauss(f"{cfg.config}:{ticker}:dd", seed, 0.0, 3.0)
            )
            max_drawdown = clamp(max_drawdown, -58.0, -3.5)

            actual_rel_return = strategy_return - buyhold_return

            p_value = (
                0.55
                - (actual_rel_return / 140.0)
                - (sharpe / 9.0)
                + cfg.p_shift
                + stable_gauss(f"{cfg.config}:{ticker}:p", seed, 0.0, 0.05)
            )
            p_value = clamp(p_value, 0.01, 0.99)

            rows.append(
                {
                    "config": cfg.config,
                    "ticker": ticker,
                    "status": "ok",
                    "strat_total_return": round(strategy_return, 4),
                    "strat_sharpe": round(sharpe, 4),
                    "strat_max_drawdown": round(max_drawdown, 4),
                    "actual_rel_return": round(actual_rel_return, 4),
                    "p_value_one_sided": round(p_value, 4),
                }
            )

    return rows


def build_suite_rows(
    ticker_rows: list[dict],
    configs: list[ConfigSpec],
    n_tickers: int,
) -> list[dict]:
    rows: list[dict] = []

    for cfg in configs:
        cfg_rows = [r for r in ticker_rows if r["config"] == cfg.config]
        returns = [float(r["strat_total_return"]) for r in cfg_rows]
        sharpes = [float(r["strat_sharpe"]) for r in cfg_rows]
        dds = [float(r["strat_max_drawdown"]) for r in cfg_rows]
        p_vals = [float(r["p_value_one_sided"]) for r in cfg_rows]
        rels = [float(r["actual_rel_return"]) for r in cfg_rows]

        mean_return = sum(returns) / len(returns)
        mean_sharpe = sum(sharpes) / len(sharpes)
        mean_dd = sum(dds) / len(dds)
        mean_p = sum(p_vals) / len(p_vals)
        mean_rel = sum(rels) / len(rels)

        suite_return = (
            mean_return * 0.92
            + percentile(returns, 0.65) * 0.28
            - abs(percentile(dds, 0.20)) * 0.15
        )
        suite_return = round(clamp(suite_return, -25.0, 180.0), 4)

        suite_sharpe = round(clamp(mean_sharpe + 0.03, -0.3, 1.6), 4)
        suite_dd = round(clamp(mean_dd * 0.92, -45.0, -4.0), 4)
        suite_p = round(clamp(mean_p * 0.96, 0.01, 0.99), 4)
        suite_defense = defense_score(suite_return, suite_sharpe, suite_dd, suite_p)

        rows.append(
            {
                "config": cfg.config,
                "ticker": "SUITE",
                "stage": cfg.stage,
                "suite_mode": "true_multi",
                "n_suite_tickers": n_tickers,
                "is_single_ticker_suite": False,
                "exclude_from_showcase": False,
                "return_metric_pct": suite_return,
                "actual_rel_return_pct": round(mean_rel, 4),
                "sharpe": suite_sharpe,
                "max_drawdown_pct": suite_dd,
                "p_value_one_sided": suite_p,
                "defense_ready_score": suite_defense,
                "run_dir": f"demo://runs/{cfg.config.replace('.yaml', '')}",
            }
        )

    return rows


def ranked_top(rows: list[dict], key: str, top_n: int = 10) -> list[dict]:
    ordered = sorted(rows, key=lambda r: float(r.get(key) or -999999), reverse=True)[:top_n]
    output: list[dict] = []
    for idx, row in enumerate(ordered, start=1):
        enriched = dict(row)
        enriched["rank"] = idx
        output.append(enriched)
    return output


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    data_root = (repo_root / args.data_root).resolve()
    frontend_dir = (repo_root / args.frontend_dir).resolve()

    target_root = frontend_dir / "public" / "data" / args.target_mode
    if args.clean and target_root.exists():
        shutil.rmtree(target_root)

    stock_tickers, etf_tickers = list_real_tickers(data_root)
    demo_tickers, demo_stock_count, demo_etf_count = choose_demo_tickers(
        stock_tickers,
        etf_tickers,
        args.max_tickers,
        args.seed,
    )

    configs = build_config_specs()
    ticker_rows = build_ticker_rows(demo_tickers, configs, args.seed)
    suite_rows = build_suite_rows(ticker_rows, configs, len(demo_tickers))

    top_return = ranked_top(suite_rows, "return_metric_pct", top_n=10)
    top_defense = ranked_top(suite_rows, "defense_ready_score", top_n=10)

    (target_root / "index").mkdir(parents=True, exist_ok=True)
    (target_root / "showcase").mkdir(parents=True, exist_ok=True)
    (target_root / "meta").mkdir(parents=True, exist_ok=True)

    (target_root / "index" / "all_results_index.json").write_text(
        json.dumps(suite_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (target_root / "index" / "suite_ticker_results_index.json").write_text(
        json.dumps(ticker_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (target_root / "showcase" / "top10_by_return.json").write_text(
        json.dumps(top_return, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (target_root / "showcase" / "top10_defense_ready.json").write_text(
        json.dumps(top_defense, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    manifest = {
        "mode": args.target_mode,
        "is_synthetic_demo": True,
        "label": "Interactive interface demonstration based on synthetic sample data",
        "raw_stocks_available": len(stock_tickers),
        "raw_etfs_available": len(etf_tickers),
        "stocks_count": demo_stock_count,
        "etfs_count": demo_etf_count,
        "total_expected": len(demo_tickers),
        "total_copied": len(demo_tickers),
        "missing_files_count": 0,
        "selection_params": {
            "max_tickers": args.max_tickers,
            "seed": args.seed,
            "n_configs": len(configs),
        },
        "notes": [
            "Synthetic interface dataset for GitHub Pages / click-through demo.",
            "Ticker symbols are real and sourced from the raw dataset.",
            "Performance metrics are synthetic and must not be presented as real experiment results.",
        ],
    }
    (target_root / "meta" / "curated_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    overview = {
        "mode": args.target_mode,
        "n_suite_runs": len(suite_rows),
        "n_ticker_rows": len(ticker_rows),
        "n_unique_tickers": len(demo_tickers),
        "raw_stocks_available": len(stock_tickers),
        "raw_etfs_available": len(etf_tickers),
        "configs": [cfg.config for cfg in configs],
        "target_root": str(target_root),
    }
    (target_root / "meta" / "demo_overview.json").write_text(
        json.dumps(overview, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if console:
        table = Table(title="Demo frontend snapshot summary")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Mode", args.target_mode)
        table.add_row("Raw stocks available", str(len(stock_tickers)))
        table.add_row("Raw ETFs available", str(len(etf_tickers)))
        table.add_row("Demo stocks selected", str(demo_stock_count))
        table.add_row("Demo ETFs selected", str(demo_etf_count))
        table.add_row("Unique tickers in demo", str(len(demo_tickers)))
        table.add_row("Suite runs", str(len(suite_rows)))
        table.add_row("Ticker rows", str(len(ticker_rows)))
        table.add_row("Target root", str(target_root))
        console.print(table)
    else:
        print(json.dumps(overview, indent=2, ensure_ascii=False))

    log(
        f"[bold green]Done.[/bold green] Demo snapshot generated at: {target_root}"
        if console
        else f"Done. Demo snapshot generated at {target_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())