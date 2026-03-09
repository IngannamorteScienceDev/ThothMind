from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.traceback import install


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.smart_loader import get_available_tickers  # noqa: E402
from thothmind.run import run_experiment  # noqa: E402


console = Console()
install(console=console, show_locals=False, width=120)


RETURN_KEYS_PRIORITY = [
    "strategy_total_return_pct",
    "strategy_total_return",
    "strategy_return_pct",
    "strategy_return",
    "total_return_pct",
    "total_return",
    "cumulative_return_pct",
    "cumulative_return",
    "cum_return_pct",
    "cum_return",
    "net_return_pct",
    "net_return",
    "portfolio_return_pct",
    "portfolio_return",
    "return_pct",
    "return",
    "cagr_pct",
    "cagr",
]

SHARPE_KEYS_PRIORITY = [
    "strategy_sharpe",
    "sharpe_ratio",
    "sharpe",
]

MAX_DD_KEYS_PRIORITY = [
    "max_drawdown_pct",
    "max_drawdown",
    "strategy_max_drawdown_pct",
    "strategy_max_drawdown",
    "drawdown_pct",
    "drawdown",
]

WIN_RATE_KEYS_PRIORITY = [
    "win_rate_pct",
    "win_rate",
    "hit_rate_pct",
    "hit_rate",
    "accuracy_pct",
    "accuracy",
]

TRADES_KEYS_PRIORITY = [
    "n_trades",
    "num_trades",
    "trades",
    "trade_count",
]

THRESHOLD_KEYS_PRIORITY = [
    "threshold",
    "decision_threshold",
    "optimal_threshold",
]

HORIZON_KEYS_PRIORITY = [
    "horizon",
    "forecast_horizon",
    "label_horizon",
    "target_horizon",
]

CANDIDATE_METRIC_FILENAMES = [
    "run_metrics.json",
    "run_metrics_buyhold.json",
    "summary.json",
    "metrics.json",
    "performance.json",
    "results.json",
    "report.json",
    "stats.json",
    "backtest_metrics.json",
    "evaluation.json",
    "registry.json",
    "manifest.json",
    "summary.csv",
    "metrics.csv",
    "performance.csv",
    "backtest_metrics.csv",
    "window_metrics.csv",
    "suite_summary.csv",
]


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )


def safe_name(value: str) -> str:
    allowed = []
    for ch in str(value):
        if ch.isalnum() or ch in {"-", "_", "."}:
            allowed.append(ch)
        else:
            allowed.append("_")
    out = "".join(allowed).strip("._")
    while "__" in out:
        out = out.replace("__", "_")
    return out or "NA"


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a top-level mapping: {path}")
    return data


def write_yaml(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, sort_keys=False, allow_unicode=True)


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_cfg_hash(cfg: dict[str, Any]) -> str:
    payload = json.dumps(cfg, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:12]


def load_done_keys(state_path: Path) -> set[str]:
    if not state_path.exists():
        return set()

    done: set[str] = set()
    for line in state_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("status") == "ok" and rec.get("key"):
            done.add(str(rec["key"]))
    return done


def load_state_records(state_path: Path) -> list[dict[str, Any]]:
    if not state_path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in state_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def append_state(state_path: Path, obj: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def newest_run_dir(output_dir: Path, before_names: set[str]) -> Path | None:
    if not output_dir.exists():
        return None

    after_dirs = {p.name for p in output_dir.iterdir() if p.is_dir()}
    new_dirs = sorted(after_dirs - before_names)
    if not new_dirs:
        return None
    if len(new_dirs) == 1:
        return output_dir / new_dirs[0]

    candidates = [output_dir / name for name in new_dirs]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def persist_run_metadata(run_dir: Path | None, effective_cfg: dict[str, Any], batch_record: dict[str, Any]) -> None:
    if run_dir is None or not run_dir.exists():
        return

    write_yaml(run_dir / "_effective_config.yaml", effective_cfg)
    save_json(run_dir / "_batch_meta.json", batch_record)


def normalize_key(key: str) -> str:
    chars = []
    for ch in key.lower():
        if ch.isalnum():
            chars.append(ch)
        else:
            chars.append("_")
    out = "".join(chars)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def try_parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    text = text.replace("%", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def flatten_numeric_json(obj: Any, prefix: str = "", out: dict[str, float] | None = None) -> dict[str, float]:
    if out is None:
        out = {}

    if isinstance(obj, dict):
        for k, v in obj.items():
            new_prefix = f"{prefix}.{k}" if prefix else str(k)
            flatten_numeric_json(v, new_prefix, out)
    elif isinstance(obj, list):
        if len(obj) <= 10:
            for i, v in enumerate(obj):
                new_prefix = f"{prefix}.{i}" if prefix else str(i)
                flatten_numeric_json(v, new_prefix, out)
    else:
        num = try_parse_float(obj)
        if num is not None and prefix:
            out.setdefault(normalize_key(prefix), num)

    return out


def extract_metrics_from_json_file(path: Path) -> dict[str, float]:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            data = json.loads(path.read_text(encoding=encoding))
            return flatten_numeric_json(data)
        except Exception:
            continue
    return {}


def extract_metrics_from_csv_file(path: Path) -> dict[str, float]:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                rows = list(csv.DictReader(f))
            if not rows:
                return {}
            row = rows[-1]
            out: dict[str, float] = {}
            for k, v in row.items():
                num = try_parse_float(v)
                if num is not None:
                    out.setdefault(normalize_key(k), num)
            return out
        except Exception:
            continue
    return {}


def collect_metric_files(run_dir: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    for name in CANDIDATE_METRIC_FILENAMES:
        for p in run_dir.rglob(name):
            if not p.is_file():
                continue
            if p.stat().st_size > 5_000_000:
                continue
            resolved = str(p.resolve())
            if resolved not in seen:
                found.append(p)
                seen.add(resolved)

    if found:
        return found

    for pattern in ("*.json", "*.csv"):
        for p in run_dir.rglob(pattern):
            if not p.is_file():
                continue
            if p.stat().st_size > 5_000_000:
                continue
            resolved = str(p.resolve())
            if resolved not in seen:
                found.append(p)
                seen.add(resolved)
            if len(found) >= 20:
                return found

    return found


def collect_metrics_from_run_dir(run_dir: Path) -> tuple[dict[str, float], list[Path]]:
    metrics: dict[str, float] = {}
    files = collect_metric_files(run_dir)

    for path in files:
        part: dict[str, float] = {}
        if path.suffix.lower() == ".json":
            part = extract_metrics_from_json_file(path)
        elif path.suffix.lower() == ".csv":
            part = extract_metrics_from_csv_file(path)

        for k, v in part.items():
            metrics.setdefault(k, v)

    return metrics, files


def pick_best_metric(metrics: dict[str, float], priority_keys: list[str]) -> tuple[str | None, float | None]:
    for key in priority_keys:
        if key in metrics:
            return key, metrics[key]

    for wanted in priority_keys:
        for actual_key, value in metrics.items():
            if wanted in actual_key or actual_key.endswith(wanted):
                return actual_key, value

    return None, None


def metric_to_pct(value: float | None, key: str | None) -> float | None:
    if value is None:
        return None
    if key and ("pct" in key or "percent" in key):
        return float(value)
    if abs(value) <= 5:
        return float(value) * 100.0
    return float(value)


def save_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def discover_run_dirs(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    return sorted([p for p in output_dir.iterdir() if p.is_dir()])


def guess_config_from_run_dir(run_dir: Path, state_by_dir: dict[str, dict[str, Any]]) -> str | None:
    rec = state_by_dir.get(str(run_dir.resolve()))
    if rec:
        return rec.get("config")
    return None


def build_effective_cfg(base_cfg: dict[str, Any], ticker: str, *, single_ticker_suite: bool) -> dict[str, Any]:
    cfg = deepcopy(base_cfg)
    cfg.setdefault("data", {})
    cfg["data"]["ticker"] = ticker

    if "base_path" not in cfg["data"]:
        cfg["data"]["base_path"] = "data"

    if single_ticker_suite and isinstance(cfg.get("suite"), dict):
        cfg["suite"]["tickers"] = [ticker]

    return cfg


def prepare_jobs(
    configs: list[Path],
    tickers: list[str],
    *,
    resume: bool,
    done_keys: set[str],
    single_ticker_suite: bool,
    group_by_config: bool,
) -> list[dict[str, Any]]:
    base_cfg_cache: dict[Path, dict[str, Any]] = {cfg_path: read_yaml(cfg_path) for cfg_path in configs}
    jobs: list[dict[str, Any]] = []

    if group_by_config:
        iterable: Iterable[tuple[Path, str]] = ((cfg, ticker) for cfg in configs for ticker in tickers)
    else:
        iterable = ((cfg, ticker) for ticker in tickers for cfg in configs)

    for cfg_path, ticker in iterable:
        base_cfg = base_cfg_cache[cfg_path]
        effective_cfg = build_effective_cfg(base_cfg, ticker, single_ticker_suite=single_ticker_suite)
        cfg_hash = compute_cfg_hash(effective_cfg)
        key = f"{cfg_path.name}::{ticker}::{cfg_hash}"

        if resume and key in done_keys:
            continue

        jobs.append(
            {
                "config_path": cfg_path,
                "ticker": ticker,
                "effective_cfg": effective_cfg,
                "cfg_hash": cfg_hash,
                "key": key,
            }
        )

    return jobs


def format_metric(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def print_plan_summary(
    *,
    configs: list[Path],
    tickers: list[str],
    jobs: list[dict[str, Any]],
    output_dir: Path,
    state_path: Path,
    logs_dir: Path,
    index_dir: Path,
    showcase_dir: Path,
    single_ticker_suite: bool,
    resume: bool,
) -> None:
    table = Table(title="Batch universe plan", box=box.MINIMAL_HEAVY_HEAD)
    table.add_column("Item", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Configs matched", str(len(configs)))
    table.add_row("Tickers selected", str(len(tickers)))
    table.add_row("Jobs to run", str(len(jobs)))
    table.add_row("Resume", str(resume))
    table.add_row("Single-ticker suite", str(single_ticker_suite))
    table.add_row("Output dir", str(output_dir))
    table.add_row("Logs dir", str(logs_dir))
    table.add_row("State file", str(state_path))
    table.add_row("Index dir", str(index_dir))
    table.add_row("Showcase dir", str(showcase_dir))
    console.print(table)

    preview_cfgs = ", ".join(p.name for p in configs[:6])
    preview_tickers = ", ".join(tickers[:10])
    console.print(
        Panel(
            f"[bold]Configs:[/bold] {preview_cfgs}{' ...' if len(configs) > 6 else ''}\n"
            f"[bold]Tickers:[/bold] {preview_tickers}{' ...' if len(tickers) > 10 else ''}",
            title="Selection preview",
            border_style="blue",
        )
    )


def extract_run_console_summary(captured_text: str) -> str:
    lines = [line.rstrip() for line in captured_text.splitlines() if line.strip()]
    if not lines:
        return "no internal run output captured"
    tail = lines[-8:]
    return "\n".join(tail)


def run_one_job(
    *,
    job: dict[str, Any],
    output_dir: Path,
    logs_dir: Path,
    state_path: Path,
    tmp_dir: Path,
) -> dict[str, Any]:
    cfg_path: Path = job["config_path"]
    ticker: str = job["ticker"]
    effective_cfg: dict[str, Any] = job["effective_cfg"]
    cfg_hash: str = job["cfg_hash"]
    key: str = job["key"]

    job_slug = f"{cfg_path.stem}__{ticker}__{cfg_hash}"
    tmp_cfg_path = tmp_dir / f"{job_slug}.yaml"
    write_yaml(tmp_cfg_path, effective_cfg)

    logs_dir.mkdir(parents=True, exist_ok=True)
    run_log_path = logs_dir / f"{job_slug}.log"

    before_names = {p.name for p in output_dir.iterdir() if p.is_dir()} if output_dir.exists() else set()
    started_at = time.time()
    captured_io = io.StringIO()

    record_base = {
        "key": key,
        "config": cfg_path.name,
        "ticker": ticker,
        "cfg_hash": cfg_hash,
        "started_ts": started_at,
        "tmp_cfg_path": str(tmp_cfg_path),
    }

    try:
        with redirect_stdout(captured_io), redirect_stderr(captured_io):
            run_id = run_experiment(str(tmp_cfg_path))

        elapsed = round(time.time() - started_at, 3)
        run_dir = newest_run_dir(output_dir, before_names)

        run_log_path.write_text(captured_io.getvalue(), encoding="utf-8")

        record = {
            **record_base,
            "status": "ok",
            "seconds": elapsed,
            "run_id": run_id,
            "run_dir": str(run_dir) if run_dir else None,
            "log_path": str(run_log_path),
        }
        persist_run_metadata(run_dir, effective_cfg, record)
        append_state(state_path, record)

        return {
            "status": "ok",
            "config": cfg_path.name,
            "ticker": ticker,
            "seconds": elapsed,
            "run_dir": str(run_dir) if run_dir else None,
            "log_path": str(run_log_path),
            "tail": extract_run_console_summary(captured_io.getvalue()),
        }

    except Exception as exc:
        elapsed = round(time.time() - started_at, 3)
        captured_text = captured_io.getvalue()
        if captured_text:
            run_log_path.write_text(captured_text + "\n\n" + traceback.format_exc(), encoding="utf-8")
        else:
            run_log_path.write_text(traceback.format_exc(), encoding="utf-8")

        record = {
            **record_base,
            "status": "err",
            "seconds": elapsed,
            "error": repr(exc),
            "traceback": traceback.format_exc(),
            "log_path": str(run_log_path),
        }
        append_state(state_path, record)

        return {
            "status": "err",
            "config": cfg_path.name,
            "ticker": ticker,
            "seconds": elapsed,
            "error": repr(exc),
            "log_path": str(run_log_path),
            "tail": extract_run_console_summary(captured_text),
        }


def render_job_result(job_result: dict[str, Any]) -> None:
    status = job_result["status"]
    title = f"{job_result['config']} • {job_result['ticker']} • {job_result['seconds']:.1f}s"

    if status == "ok":
        body = (
            f"[green]Status:[/green] OK\n"
            f"[bold]Run dir:[/bold] {job_result.get('run_dir') or '-'}\n"
            f"[bold]Log:[/bold] {job_result.get('log_path') or '-'}\n"
            f"[bold]Run tail:[/bold]\n{job_result.get('tail') or '-'}"
        )
        console.print(Panel(body, title=title, border_style="green"))
    else:
        body = (
            f"[red]Status:[/red] ERROR\n"
            f"[bold]Error:[/bold] {job_result.get('error') or '-'}\n"
            f"[bold]Log:[/bold] {job_result.get('log_path') or '-'}\n"
            f"[bold]Run tail:[/bold]\n{job_result.get('tail') or '-'}"
        )
        console.print(Panel(body, title=title, border_style="red"))


def print_final_summary(results: list[dict[str, Any]]) -> None:
    total = len(results)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    err_count = total - ok_count
    total_seconds = sum(float(r.get("seconds", 0.0)) for r in results)

    table = Table(title="Batch execution summary", box=box.MINIMAL_HEAVY_HEAD)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Total jobs", str(total))
    table.add_row("OK", f"[green]{ok_count}[/green]")
    table.add_row("ERR", f"[red]{err_count}[/red]")
    table.add_row("Wall time (sum of jobs)", f"{total_seconds:.1f}s")
    console.print(table)

    failed = [r for r in results if r["status"] != "ok"][:10]
    if failed:
        ft = Table(title="First failed jobs", box=box.MINIMAL_HEAVY_HEAD)
        ft.add_column("Config", style="white")
        ft.add_column("Ticker", style="white")
        ft.add_column("Error", style="red")
        for row in failed:
            ft.add_row(str(row.get("config")), str(row.get("ticker")), str(row.get("error", "-"))[:120])
        console.print(ft)


def build_results_index_and_showcase(
    *,
    output_dir: Path,
    state_path: Path,
    index_dir: Path,
    showcase_dir: Path,
    top_k: int,
) -> dict[str, Any]:
    console.rule("[bold magenta]Post-processing: index + showcase")

    state_records = load_state_records(state_path)
    ok_state_by_run_dir: dict[str, dict[str, Any]] = {}

    for rec in state_records:
        if rec.get("status") != "ok":
            continue
        run_dir = rec.get("run_dir")
        if not run_dir:
            continue
        try:
            ok_state_by_run_dir[str(Path(run_dir).resolve())] = rec
        except Exception:
            continue

    run_dirs = discover_run_dirs(output_dir)
    console.print(f"[cyan]Run dirs detected:[/cyan] {len(run_dirs)}")

    rows_json: list[dict[str, Any]] = []
    rows_csv: list[dict[str, Any]] = []

    for run_dir in run_dirs:
        metrics, metric_files = collect_metrics_from_run_dir(run_dir)

        ret_key, ret_val = pick_best_metric(metrics, RETURN_KEYS_PRIORITY)
        sharpe_key, sharpe_val = pick_best_metric(metrics, SHARPE_KEYS_PRIORITY)
        dd_key, dd_val = pick_best_metric(metrics, MAX_DD_KEYS_PRIORITY)
        win_key, win_val = pick_best_metric(metrics, WIN_RATE_KEYS_PRIORITY)
        trades_key, trades_val = pick_best_metric(metrics, TRADES_KEYS_PRIORITY)
        thr_key, thr_val = pick_best_metric(metrics, THRESHOLD_KEYS_PRIORITY)
        horizon_key, horizon_val = pick_best_metric(metrics, HORIZON_KEYS_PRIORITY)

        row_json = {
            "config": guess_config_from_run_dir(run_dir, ok_state_by_run_dir),
            "ticker": ok_state_by_run_dir.get(str(run_dir.resolve()), {}).get("ticker"),
            "cfg_hash": ok_state_by_run_dir.get(str(run_dir.resolve()), {}).get("cfg_hash"),
            "run_dir": str(run_dir),
            "return_metric_key": ret_key,
            "return_metric_raw": ret_val,
            "return_metric_pct": metric_to_pct(ret_val, ret_key),
            "sharpe_key": sharpe_key,
            "sharpe": sharpe_val,
            "max_drawdown_key": dd_key,
            "max_drawdown_raw": dd_val,
            "max_drawdown_pct": metric_to_pct(dd_val, dd_key),
            "win_rate_key": win_key,
            "win_rate_raw": win_val,
            "win_rate_pct": metric_to_pct(win_val, win_key),
            "trades_key": trades_key,
            "trades": trades_val,
            "threshold_key": thr_key,
            "threshold": thr_val,
            "horizon_key": horizon_key,
            "horizon": horizon_val,
            "metric_files": [str(p) for p in metric_files],
            "metrics": metrics,
        }
        rows_json.append(row_json)
        rows_csv.append(
            {
                "config": row_json["config"],
                "ticker": row_json["ticker"],
                "cfg_hash": row_json["cfg_hash"],
                "run_dir": row_json["run_dir"],
                "return_metric_key": row_json["return_metric_key"],
                "return_metric_raw": row_json["return_metric_raw"],
                "return_metric_pct": row_json["return_metric_pct"],
                "sharpe": row_json["sharpe"],
                "max_drawdown_pct": row_json["max_drawdown_pct"],
                "win_rate_pct": row_json["win_rate_pct"],
                "trades": row_json["trades"],
                "threshold": row_json["threshold"],
                "horizon": row_json["horizon"],
                "metric_file_count": len(metric_files),
            }
        )

    index_dir.mkdir(parents=True, exist_ok=True)
    all_json_path = index_dir / "all_results_index.json"
    all_csv_path = index_dir / "all_results_index.csv"
    save_json(all_json_path, rows_json)
    save_csv(all_csv_path, rows_csv)

    ranked = [row for row in rows_json if row.get("return_metric_pct") is not None]
    ranked.sort(key=lambda row: row["return_metric_pct"], reverse=True)
    top_rows = ranked[:top_k]

    showcase_dir.mkdir(parents=True, exist_ok=True)
    for old in showcase_dir.glob("rank_*"):
        if old.is_dir():
            shutil.rmtree(old, ignore_errors=True)
        else:
            try:
                old.unlink()
            except Exception:
                pass

    top_json_path = showcase_dir / f"top{top_k}_by_return.json"
    top_csv_path = showcase_dir / f"top{top_k}_by_return.csv"

    save_json(top_json_path, top_rows)
    save_csv(
        top_csv_path,
        [
            {
                "rank": idx,
                "ticker": row.get("ticker"),
                "config": row.get("config"),
                "return_metric_key": row.get("return_metric_key"),
                "return_metric_pct": row.get("return_metric_pct"),
                "sharpe": row.get("sharpe"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "win_rate_pct": row.get("win_rate_pct"),
                "trades": row.get("trades"),
                "threshold": row.get("threshold"),
                "horizon": row.get("horizon"),
                "run_dir": row.get("run_dir"),
            }
            for idx, row in enumerate(top_rows, start=1)
        ],
    )

    for idx, row in enumerate(top_rows, start=1):
        ticker = safe_name(str(row.get("ticker") or "NA"))
        config = safe_name(str(row.get("config") or "NA"))
        src = Path(str(row["run_dir"]))
        dst = showcase_dir / f"rank_{idx:02d}__{ticker}__{config}"

        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            save_json(
                dst / "showcase_summary.json",
                {
                    "rank": idx,
                    "ticker": row.get("ticker"),
                    "config": row.get("config"),
                    "cfg_hash": row.get("cfg_hash"),
                    "return_metric_key": row.get("return_metric_key"),
                    "return_metric_pct": row.get("return_metric_pct"),
                    "sharpe": row.get("sharpe"),
                    "max_drawdown_pct": row.get("max_drawdown_pct"),
                    "win_rate_pct": row.get("win_rate_pct"),
                    "trades": row.get("trades"),
                    "threshold": row.get("threshold"),
                    "horizon": row.get("horizon"),
                    "run_dir": row.get("run_dir"),
                    "metric_files": row.get("metric_files"),
                    "metrics": row.get("metrics"),
                },
            )

    top_table = Table(title=f"Top-{top_k} by return", box=box.MINIMAL_HEAVY_HEAD)
    top_table.add_column("Rank", justify="right", style="cyan")
    top_table.add_column("Ticker", style="white")
    top_table.add_column("Config", style="white")
    top_table.add_column("Return %", justify="right", style="green")
    top_table.add_column("Sharpe", justify="right", style="magenta")
    top_table.add_column("Max DD %", justify="right", style="red")
    top_table.add_column("Win rate %", justify="right", style="yellow")

    for idx, row in enumerate(top_rows, start=1):
        top_table.add_row(
            str(idx),
            str(row.get("ticker") or "-"),
            str(row.get("config") or "-"),
            format_metric(row.get("return_metric_pct"), digits=2),
            format_metric(row.get("sharpe"), digits=4),
            format_metric(row.get("max_drawdown_pct"), digits=2),
            format_metric(row.get("win_rate_pct"), digits=2),
        )

    console.print(top_table)
    console.print(
        Panel(
            "\n".join(
                [
                    f"[bold]All index JSON:[/bold] {all_json_path}",
                    f"[bold]All index CSV:[/bold] {all_csv_path}",
                    f"[bold]Top JSON:[/bold] {top_json_path}",
                    f"[bold]Top CSV:[/bold] {top_csv_path}",
                    f"[bold]Showcase dir:[/bold] {showcase_dir}",
                    f"[bold]Ranked runs:[/bold] {len(ranked)}",
                ]
            ),
            title="[green]Post-processing complete[/green]",
            border_style="green",
        )
    )

    return {
        "all_json_path": str(all_json_path),
        "all_csv_path": str(all_csv_path),
        "top_json_path": str(top_json_path),
        "top_csv_path": str(top_csv_path),
        "showcase_dir": str(showcase_dir),
        "ranked_runs": len(ranked),
        "top_count": len(top_rows),
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Sequential batch pipeline for running all tickers through all experiment configs."
    )
    ap.add_argument("--configs-glob", default="configs/exp_m*.yaml", help='Config glob. Example: "configs/exp_m*.yaml"')
    ap.add_argument("--data-root", default="data", help="Path to data root with Stocks/ and ETFs/")
    ap.add_argument("--output-dir", default="reports/runs", help="Run artifact directory")
    ap.add_argument("--logs-dir", default="reports/logs/batch", help="Batch log directory")
    ap.add_argument("--state", default="reports/batch_state_all.jsonl", help="JSONL state file for resume")
    ap.add_argument("--tmp-dir", default="configs/_batch_tmp", help="Temporary config directory")
    ap.add_argument("--index-dir", default="reports/index", help="Aggregated index directory")
    ap.add_argument(
        "--showcase-dir",
        default="reports/showcase/top10_by_return",
        help="Directory for copied top-k showcase runs",
    )
    ap.add_argument("--showcase-top", type=int, default=10, help="How many best runs to copy for showcase")
    ap.add_argument("--max-tickers", type=int, default=0, help="0 means all tickers")
    ap.add_argument("--resume", action="store_true", help="Skip runs already marked as ok in state file")
    ap.add_argument(
        "--group-by-config",
        action="store_true",
        help="Iterate as config -> tickers. Default is ticker -> configs.",
    )
    ap.add_argument(
        "--keep-suite-list",
        action="store_true",
        help="Do not replace suite.tickers with [ticker] for m8 configs.",
    )
    ap.add_argument(
        "--skip-postprocess",
        action="store_true",
        help="Skip final result indexing and top-k showcase export",
    )
    ap.add_argument(
        "--tickers",
        default="",
        help='Optional comma-separated ticker whitelist, e.g. "AAPL,MSFT,SPY"',
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    configs = sorted(REPO_ROOT.glob(args.configs_glob))
    if not configs:
        console.print(f"[red][ERR][/red] No configs matched: {args.configs_glob}")
        return 2

    data_root = (REPO_ROOT / args.data_root).resolve()
    if not data_root.exists():
        console.print(f"[red][ERR][/red] Data root does not exist: {data_root}")
        return 2

    tickers = get_available_tickers(str(data_root))
    tickers = sorted(set(str(t).upper() for t in tickers))

    if args.tickers.strip():
        whitelist = {t.strip().upper() for t in args.tickers.split(",") if t.strip()}
        tickers = [t for t in tickers if t in whitelist]

    if args.max_tickers and args.max_tickers > 0:
        tickers = tickers[: args.max_tickers]

    if not tickers:
        console.print("[red][ERR][/red] No tickers selected.")
        return 2

    output_dir = (REPO_ROOT / args.output_dir).resolve()
    logs_dir = (REPO_ROOT / args.logs_dir).resolve()
    state_path = (REPO_ROOT / args.state).resolve()
    tmp_dir = (REPO_ROOT / args.tmp_dir).resolve()
    index_dir = (REPO_ROOT / args.index_dir).resolve()
    showcase_dir = (REPO_ROOT / args.showcase_dir).resolve()

    done_keys = load_done_keys(state_path) if args.resume else set()
    jobs = prepare_jobs(
        configs=configs,
        tickers=tickers,
        resume=args.resume,
        done_keys=done_keys,
        single_ticker_suite=not args.keep_suite_list,
        group_by_config=args.group_by_config,
    )

    print_plan_summary(
        configs=configs,
        tickers=tickers,
        jobs=jobs,
        output_dir=output_dir,
        state_path=state_path,
        logs_dir=logs_dir,
        index_dir=index_dir,
        showcase_dir=showcase_dir,
        single_ticker_suite=not args.keep_suite_list,
        resume=args.resume,
    )

    if not jobs:
        console.print("[yellow]Nothing to run. Resume filtered everything out.[/yellow]")
        if not args.skip_postprocess:
            build_results_index_and_showcase(
                output_dir=output_dir,
                state_path=state_path,
                index_dir=index_dir,
                showcase_dir=showcase_dir,
                top_k=args.showcase_top,
            )
        return 0

    tmp_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    started = time.time()
    with make_progress() as progress:
        task_id = progress.add_task("Batch runs", total=len(jobs))

        for idx, job in enumerate(jobs, start=1):
            progress.update(
                task_id,
                description=f"Batch runs • {idx}/{len(jobs)} • {job['config_path'].name} • {job['ticker']}",
            )

            job_table = Table(box=box.SIMPLE_HEAVY)
            job_table.add_column("Field", style="cyan")
            job_table.add_column("Value", style="white")
            job_table.add_row("Config", job["config_path"].name)
            job_table.add_row("Ticker", job["ticker"])
            job_table.add_row("Cfg hash", job["cfg_hash"])
            console.print(job_table)

            result = run_one_job(
                job=job,
                output_dir=output_dir,
                logs_dir=logs_dir,
                state_path=state_path,
                tmp_dir=tmp_dir,
            )
            results.append(result)
            render_job_result(result)
            progress.advance(task_id)

    elapsed = time.time() - started
    console.print(Panel(f"[bold]Elapsed:[/bold] {elapsed:.1f}s", title="Batch runtime", border_style="cyan"))
    print_final_summary(results)

    if not args.skip_postprocess:
        build_results_index_and_showcase(
            output_dir=output_dir,
            state_path=state_path,
            index_dir=index_dir,
            showcase_dir=showcase_dir,
            top_k=args.showcase_top,
        )

    console.print("\n[bold green][DONE][/bold green] All requested experiment runs finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())