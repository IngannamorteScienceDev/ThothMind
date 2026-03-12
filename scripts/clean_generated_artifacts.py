
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table

    console = Console()
except Exception:
    console = None


def log(msg: str) -> None:
    if console:
        console.print(msg)
    else:
        print(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean generated project artifacts: Python caches, batch runs, indexes, logs and temp files."
    )
    parser.add_argument("--all", action="store_true", help="Clean the full default set of generated artifacts.")
    parser.add_argument("--python-cache", action="store_true", help="Remove __pycache__, .pytest_cache, .mypy_cache, .ruff_cache.")
    parser.add_argument("--runs", action="store_true", help="Remove reports/runs.")
    parser.add_argument("--index", action="store_true", help="Remove reports/index.")
    parser.add_argument("--showcase", action="store_true", help="Remove reports/showcase.")
    parser.add_argument("--batch-state", action="store_true", help="Remove reports/batch_state_all.jsonl.")
    parser.add_argument("--logs", action="store_true", help="Remove reports/logs/batch.")
    parser.add_argument("--tmp-configs", action="store_true", help="Remove configs/_batch_tmp.")
    parser.add_argument("--universe-selection", action="store_true", help="Remove reports/universe_selection.")
    parser.add_argument(
        "--curated-data",
        default="",
        help="Optional curated data directory to remove, e.g. data_curated_demo_30s_10e",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be removed.")
    return parser.parse_args()


def remove_path(path: Path, *, dry_run: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"

    if dry_run:
        return True, "planned"

    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return True, "removed"


def collect_python_cache_paths(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    names = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    for path in repo_root.rglob("*"):
        if path.name in names:
            paths.append(path)
    return sorted(set(paths))


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    clean_all = bool(args.all)
    targets: list[tuple[str, Path]] = []

    if clean_all or args.runs:
        targets.append(("reports/runs", repo_root / "reports/runs"))
    if clean_all or args.index:
        targets.append(("reports/index", repo_root / "reports/index"))
    if clean_all or args.showcase:
        targets.append(("reports/showcase", repo_root / "reports/showcase"))
    if clean_all or args.batch_state:
        targets.append(("reports/batch_state_all.jsonl", repo_root / "reports/batch_state_all.jsonl"))
    if clean_all or args.logs:
        targets.append(("reports/logs/batch", repo_root / "reports/logs/batch"))
    if clean_all or args.tmp_configs:
        targets.append(("configs/_batch_tmp", repo_root / "configs/_batch_tmp"))
    if clean_all or args.universe_selection:
        targets.append(("reports/universe_selection", repo_root / "reports/universe_selection"))

    curated_data_value = str(args.curated_data).strip()
    if curated_data_value:
        targets.append((curated_data_value, repo_root / curated_data_value))

    rows: list[dict[str, str]] = []

    for label, path in targets:
        existed, status = remove_path(path, dry_run=args.dry_run)
        rows.append({"target": label, "path": str(path), "status": status if existed else "missing"})

    if clean_all or args.python_cache:
        for cache_path in collect_python_cache_paths(repo_root):
            existed, status = remove_path(cache_path, dry_run=args.dry_run)
            rows.append({"target": cache_path.name, "path": str(cache_path), "status": status if existed else "missing"})

    if console:
        table = Table(title="Cleanup summary")
        table.add_column("Target")
        table.add_column("Status")
        table.add_column("Path")
        for row in rows:
            table.add_row(row["target"], row["status"], row["path"])
        console.print(table)
    else:
        for row in rows:
            print(f'{row["status"]:>8} | {row["target"]:<28} | {row["path"]}')

    if not rows:
        log(
            "[yellow]Nothing selected for cleanup. Use flags like --all, --runs, --python-cache, --universe-selection.[/yellow]"
            if console
            else "Nothing selected for cleanup."
        )
    else:
        log(
            "[bold green]Cleanup finished.[/bold green]" if console else "Cleanup finished."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
