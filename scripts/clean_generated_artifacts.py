from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Iterable

try:
    from rich.console import Console
    from rich.table import Table

    console = Console()
except Exception:
    console = None


SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "ENV",
    "node_modules",
}

PY_CACHE_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

DEFAULT_BATCH_STATE_GLOBS = [
    "reports/batch_state*.jsonl",
]


def log(message: str) -> None:
    if console:
        console.print(message)
    else:
        print(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean generated ThothMind artifacts without touching third-party "
            "virtual environment contents or frontend dependencies."
        )
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Clean the full default set of safe generated artifacts.",
    )

    parser.add_argument(
        "--python-cache",
        action="store_true",
        help="Remove project-level __pycache__, .pytest_cache, .mypy_cache, .ruff_cache.",
    )
    parser.add_argument(
        "--runs",
        action="store_true",
        help="Remove reports/runs.",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Remove reports/index.",
    )
    parser.add_argument(
        "--showcase",
        action="store_true",
        help="Remove reports/showcase.",
    )
    parser.add_argument(
        "--batch-state",
        action="store_true",
        help="Remove reports/batch_state*.jsonl.",
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help="Remove reports/logs/batch.",
    )
    parser.add_argument(
        "--tmp-configs",
        action="store_true",
        help="Remove configs/_batch_tmp.",
    )
    parser.add_argument(
        "--universe-selection",
        action="store_true",
        help="Remove reports/universe_selection.",
    )
    parser.add_argument(
        "--frontend-dist",
        action="store_true",
        help="Remove frontend/dist.",
    )
    parser.add_argument(
        "--frontend-research",
        action="store_true",
        help="Remove frontend/public/data/research.",
    )
    parser.add_argument(
        "--frontend-flat-data",
        action="store_true",
        help="Remove deprecated flat frontend data structure: index/meta/showcase.",
    )
    parser.add_argument(
        "--curated-data",
        default="",
        help=(
            "Optional curated data directory to remove relative to repo root, "
            "for example: data_curated_demo_30s_10e"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would be removed.",
    )

    return parser.parse_args()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def ensure_safe_repo_path(path: Path, repo_root: Path) -> Path:
    resolved = path.resolve()
    repo_resolved = repo_root.resolve()

    if not is_relative_to(resolved, repo_resolved):
        raise ValueError(
            f"Refusing to operate outside repository root: {resolved}"
        )

    return resolved


def remove_path(path: Path, *, dry_run: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"

    if dry_run:
        return True, "planned"

    if path.is_dir():
        shutil.rmtree(path, ignore_errors=False)
    else:
        path.unlink(missing_ok=True)

    return True, "removed"


def collect_python_cache_paths(repo_root: Path) -> list[Path]:
    collected: list[Path] = []

    for path in repo_root.rglob("*"):
        parts = set(path.parts)
        if SKIP_DIR_NAMES & parts:
            continue

        if path.name in PY_CACHE_NAMES:
            collected.append(path)

    unique_sorted = sorted({p.resolve() for p in collected})
    return [p for p in unique_sorted if is_relative_to(p, repo_root)]


def collect_batch_state_paths(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    for pattern in DEFAULT_BATCH_STATE_GLOBS:
        paths.extend(repo_root.glob(pattern))
    return sorted({p.resolve() for p in paths if p.exists()})


def iter_targets(args: argparse.Namespace, repo_root: Path) -> Iterable[tuple[str, Path]]:
    clean_all = bool(args.all)

    if clean_all or args.runs:
        yield "reports/runs", repo_root / "reports" / "runs"

    if clean_all or args.index:
        yield "reports/index", repo_root / "reports" / "index"

    if clean_all or args.showcase:
        yield "reports/showcase", repo_root / "reports" / "showcase"

    if clean_all or args.logs:
        yield "reports/logs/batch", repo_root / "reports" / "logs" / "batch"

    if clean_all or args.universe_selection:
        yield "reports/universe_selection", repo_root / "reports" / "universe_selection"

    if clean_all or args.tmp_configs:
        yield "configs/_batch_tmp", repo_root / "configs" / "_batch_tmp"

    if clean_all or args.frontend_dist:
        yield "frontend/dist", repo_root / "frontend" / "dist"

    if args.frontend_research:
        yield (
            "frontend/public/data/research",
            repo_root / "frontend" / "public" / "data" / "research",
        )

    if args.frontend_flat_data:
        yield (
            "frontend/public/data/index",
            repo_root / "frontend" / "public" / "data" / "index",
        )
        yield (
            "frontend/public/data/meta",
            repo_root / "frontend" / "public" / "data" / "meta",
        )
        yield (
            "frontend/public/data/showcase",
            repo_root / "frontend" / "public" / "data" / "showcase",
        )

    curated_data_value = str(args.curated_data).strip()
    if curated_data_value:
        candidate = ensure_safe_repo_path(repo_root / curated_data_value, repo_root)
        yield curated_data_value, candidate


def print_summary(rows: list[dict[str, str]]) -> None:
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
            print(f'{row["status"]:>8} | {row["target"]:<34} | {row["path"]}')


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    rows: list[dict[str, str]] = []
    seen_paths: set[Path] = set()

    for label, raw_path in iter_targets(args, repo_root):
        path = ensure_safe_repo_path(raw_path, repo_root)
        if path in seen_paths:
            continue
        seen_paths.add(path)

        existed, status = remove_path(path, dry_run=args.dry_run)
        rows.append(
            {
                "target": label,
                "path": str(path),
                "status": status if existed else "missing",
            }
        )

    if args.all or args.batch_state:
        for path in collect_batch_state_paths(repo_root):
            safe_path = ensure_safe_repo_path(path, repo_root)
            if safe_path in seen_paths:
                continue
            seen_paths.add(safe_path)

            existed, status = remove_path(safe_path, dry_run=args.dry_run)
            rows.append(
                {
                    "target": safe_path.name,
                    "path": str(safe_path),
                    "status": status if existed else "missing",
                }
            )

    if args.all or args.python_cache:
        for cache_path in collect_python_cache_paths(repo_root):
            safe_path = ensure_safe_repo_path(cache_path, repo_root)
            if safe_path in seen_paths:
                continue
            seen_paths.add(safe_path)

            existed, status = remove_path(safe_path, dry_run=args.dry_run)
            rows.append(
                {
                    "target": safe_path.name,
                    "path": str(safe_path),
                    "status": status if existed else "missing",
                }
            )

    if not rows:
        log(
            "[yellow]Nothing selected for cleanup. Use --all or specific flags.[/yellow]"
            if console
            else "Nothing selected for cleanup. Use --all or specific flags."
        )
        return 0

    print_summary(rows)

    log(
        "[bold green]Cleanup finished.[/bold green]"
        if console
        else "Cleanup finished."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())