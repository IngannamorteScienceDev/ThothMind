from __future__ import annotations

import argparse
import json
import shutil
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish research backend artifacts into frontend/public/data/research."
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
        default="data_curated_demo_30s_10e/curated_manifest.json",
        help="Path to curated manifest JSON to publish into frontend meta",
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


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    frontend_dir = (repo_root / args.frontend_dir).resolve()
    reports_dir = (repo_root / args.reports_dir).resolve()
    manifest_path = (repo_root / args.manifest).resolve()

    target_root = frontend_dir / "public" / "data" / args.target_mode
    index_src = reports_dir / "index"
    showcase_src = reports_dir / "showcase" / "top10_by_return"

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

    # Optional extra metadata
    overview = {
        "mode": args.target_mode,
        "source_reports_dir": str(reports_dir),
        "published_to": str(target_root),
        "files": {
            "all_results_index": str(target_root / "index" / "all_results_index.json"),
            "suite_ticker_results_index": str(target_root / "index" / "suite_ticker_results_index.json"),
            "top10_by_return": str(target_root / "showcase" / "top10_by_return.json"),
            "top10_defense_ready": str(target_root / "showcase" / "top10_defense_ready.json"),
            "curated_manifest": str(target_root / "meta" / "curated_manifest.json"),
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