from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

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
        description="Copy selected tickers into a separate curated data directory."
    )
    parser.add_argument(
        "--selected-csv",
        default="reports/universe_selection/selected_files.csv",
        help="CSV produced by select_research_universe.py",
    )
    parser.add_argument(
        "--output-root",
        default="data_curated",
        help="Destination root for curated data",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete destination folder before copying",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    selected_csv = (repo_root / args.selected_csv).resolve()
    output_root = (repo_root / args.output_root).resolve()

    if not selected_csv.exists():
        raise FileNotFoundError(f"Selected CSV not found: {selected_csv}")

    df = pd.read_csv(selected_csv)
    required_cols = {"kind", "ticker", "file_path", "file_name"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Selected CSV is missing columns: {sorted(missing)}")

    if args.clean and output_root.exists():
        log(f"[yellow]Removing existing curated folder: {output_root}[/yellow]" if console else f"Removing {output_root}")
        shutil.rmtree(output_root)

    stocks_out = output_root / "Stocks"
    etfs_out = output_root / "ETFs"
    stocks_out.mkdir(parents=True, exist_ok=True)
    etfs_out.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing_files = []

    for _, row in df.iterrows():
        kind = str(row["kind"]).strip().lower()
        src = Path(str(row["file_path"])).resolve()
        file_name = str(row["file_name"]).strip()

        if kind == "stock":
            dst_dir = stocks_out
        elif kind == "etf":
            dst_dir = etfs_out
        else:
            continue

        dst = dst_dir / file_name

        if not src.exists():
            missing_files.append(str(src))
            continue

        shutil.copy2(src, dst)
        copied += 1

    selected_stocks = df[df["kind"].astype(str).str.lower() == "stock"]["ticker"].astype(str).tolist()
    selected_etfs = df[df["kind"].astype(str).str.lower() == "etf"]["ticker"].astype(str).tolist()
    selected_all = selected_stocks + selected_etfs

    (output_root / "selected_stocks.txt").write_text("\n".join(selected_stocks) + "\n", encoding="utf-8")
    (output_root / "selected_etfs.txt").write_text("\n".join(selected_etfs) + "\n", encoding="utf-8")
    (output_root / "selected_all.txt").write_text("\n".join(selected_all) + "\n", encoding="utf-8")

    manifest = {
        "selected_csv": str(selected_csv),
        "output_root": str(output_root),
        "stocks_count": len(selected_stocks),
        "etfs_count": len(selected_etfs),
        "total_expected": len(df),
        "total_copied": copied,
        "missing_files_count": len(missing_files),
        "missing_files": missing_files,
    }

    manifest_path = output_root / "curated_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    if console:
        table = Table(title="Curated universe materialization summary")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Output root", str(output_root))
        table.add_row("Stocks copied", str(len(selected_stocks)))
        table.add_row("ETFs copied", str(len(selected_etfs)))
        table.add_row("Total copied", str(copied))
        table.add_row("Missing files", str(len(missing_files)))
        table.add_row("Manifest", str(manifest_path))
        console.print(table)
    else:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))

    log(f"[bold green]Done.[/bold green] Curated universe created at: {output_root}" if console else f"Done. Created {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())