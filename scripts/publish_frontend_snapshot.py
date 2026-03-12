from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Publish real backend artifacts into frontend/public/data/<mode>/..."
        )
    )
    parser.add_argument(
        "--frontend-dir",
        default="frontend",
        help="Frontend root directory",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Reports directory with index/showcase artifacts",
    )
    parser.add_argument(
        "--manifest",
        default="auto",
        help=(
            "Path to curated manifest JSON. "
            "Use 'auto' to resolve the most relevant curated_manifest.json automatically."
        ),
    )
    parser.add_argument(
        "--target-mode",
        default="research",
        choices=["research", "demo"],
        help="Frontend data mode to publish into",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete target mode directory before publishing",
    )
    return parser.parse_args()


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def file_meta(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
    }


def resolve_showcase_dir(reports_dir: Path) -> Path:
    candidates = [
        reports_dir / "showcase" / "top10_by_return",
        reports_dir / "showcase",
    ]

    for candidate in candidates:
        if (
            (candidate / "top10_by_return.json").exists()
            and (candidate / "top10_defense_ready.json").exists()
        ):
            return candidate

    searched = "\n".join(str(p) for p in candidates)
    raise FileNotFoundError(
        "Could not find showcase files.\n"
        "Expected both top10_by_return.json and top10_defense_ready.json in one of:\n"
        f"{searched}"
    )


def iter_manifest_candidates(repo_root: Path) -> Iterable[Path]:
    explicit_priority = [
        repo_root / "data_curated_demo_30s_10e" / "curated_manifest.json",
        repo_root / "data_curated" / "curated_manifest.json",
    ]

    yielded: set[Path] = set()
    for candidate in explicit_priority:
        if candidate.exists() and candidate not in yielded:
            yielded.add(candidate)
            yield candidate

    dynamic_candidates = sorted(
        repo_root.glob("data_curated*/curated_manifest.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )

    for candidate in dynamic_candidates:
        if candidate.exists() and candidate not in yielded:
            yielded.add(candidate)
            yield candidate


def resolve_manifest_path(repo_root: Path, manifest_arg: str) -> Path:
    manifest_arg = str(manifest_arg).strip()

    if manifest_arg and manifest_arg.lower() != "auto":
        manifest_path = (repo_root / manifest_arg).resolve()
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        return manifest_path

    for candidate in iter_manifest_candidates(repo_root):
        return candidate

    raise FileNotFoundError(
        "Could not resolve curated_manifest.json automatically. "
        "Pass --manifest explicitly."
    )


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    frontend_dir = (repo_root / args.frontend_dir).resolve()
    reports_dir = (repo_root / args.reports_dir).resolve()
    manifest_path = resolve_manifest_path(repo_root, args.manifest)

    if not frontend_dir.exists():
        raise FileNotFoundError(f"Frontend dir not found: {frontend_dir}")
    if not reports_dir.exists():
        raise FileNotFoundError(f"Reports dir not found: {reports_dir}")

    target_root = frontend_dir / "public" / "data" / args.target_mode
    index_src = reports_dir / "index"
    showcase_src = resolve_showcase_dir(reports_dir)

    required_files = {
        index_src / "all_results_index.json": target_root / "index" / "all_results_index.json",
        index_src / "suite_ticker_results_index.json": target_root / "index" / "suite_ticker_results_index.json",
        showcase_src / "top10_by_return.json": target_root / "showcase" / "top10_by_return.json",
        showcase_src / "top10_defense_ready.json": target_root / "showcase" / "top10_defense_ready.json",
        manifest_path: target_root / "meta" / "curated_manifest.json",
    }

    missing = [str(src) for src in required_files if not src.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required publish inputs:\n" + "\n".join(missing)
        )

    if args.clean and target_root.exists():
        shutil.rmtree(target_root)

    for src, dst in required_files.items():
        copy_file(src, dst)

    overview = {
        "mode": args.target_mode,
        "is_synthetic_demo": False,
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_reports_dir": str(reports_dir),
        "source_showcase_dir": str(showcase_src),
        "source_manifest": str(manifest_path),
        "published_to": str(target_root),
        "files": {
            "all_results_index": file_meta(target_root / "index" / "all_results_index.json"),
            "suite_ticker_results_index": file_meta(
                target_root / "index" / "suite_ticker_results_index.json"
            ),
            "top10_by_return": file_meta(target_root / "showcase" / "top10_by_return.json"),
            "top10_defense_ready": file_meta(
                target_root / "showcase" / "top10_defense_ready.json"
            ),
            "curated_manifest": file_meta(target_root / "meta" / "curated_manifest.json"),
        },
    }

    overview_path = target_root / "meta" / "publish_overview.json"
    overview_path.write_text(
        json.dumps(overview, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if console:
        table = Table(title="Frontend snapshot publish summary")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Mode", args.target_mode)
        table.add_row("Target root", str(target_root))
        table.add_row("Reports dir", str(reports_dir))
        table.add_row("Showcase dir", str(showcase_src))
        table.add_row("Manifest", str(manifest_path))
        table.add_row("Overview", str(overview_path))
        console.print(table)
    else:
        print(json.dumps(overview, indent=2, ensure_ascii=False))

    log(
        f"[bold green]Done.[/bold green] Published frontend snapshot to: {target_root}"
        if console
        else f"Done. Published snapshot to {target_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())