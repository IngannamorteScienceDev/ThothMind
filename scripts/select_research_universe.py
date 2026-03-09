from __future__ import annotations

import argparse
import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    from rich.console import Console
    from rich.table import Table

    console = Console()
except Exception:
    console = None


@dataclass
class ScanRow:
    kind: str
    ticker: str
    file_name: str
    file_path: str
    file_size_mb: float
    rows: int
    start_date: Optional[str]
    end_date: Optional[str]
    close_fill_rate: float
    volume_fill_rate: float
    zero_volume_share: float
    status: str
    error: str = ""


def log(msg: str) -> None:
    if console:
        console.print(msg)
    else:
        print(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a curated research universe from raw Stocks/ETFs txt files."
    )
    parser.add_argument("--data-root", default="data", help="Root folder with Stocks/ and ETFs/")
    parser.add_argument("--stocks-dir", default="Stocks", help="Stocks subfolder name")
    parser.add_argument("--etfs-dir", default="ETFs", help="ETFs subfolder name")
    parser.add_argument("--stock-count", type=int, default=150, help="How many stocks to select")
    parser.add_argument("--etf-count", type=int, default=50, help="How many ETFs to select")
    parser.add_argument(
        "--min-rows",
        type=int,
        default=1000,
        help="Hard minimum number of rows for a ticker to be considered eligible",
    )
    parser.add_argument(
        "--min-close-fill",
        type=float,
        default=0.95,
        help="Minimum allowed Close fill rate",
    )
    parser.add_argument(
        "--min-volume-fill",
        type=float,
        default=0.80,
        help="Minimum allowed Volume fill rate",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=12,
        help="Parallel workers for scanning files",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/universe_selection",
        help="Where to save the selection reports",
    )
    return parser.parse_args()


def ticker_from_filename(path: Path) -> str:
    name = path.name
    if name.endswith(".us.txt"):
        return name[:-7]
    return path.stem.split(".")[0]


def safe_float(value: str) -> Optional[float]:
    value = (value or "").strip()
    if value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def safe_date(value: str) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except Exception:
        try:
            return pd.to_datetime(value).date().isoformat()
        except Exception:
            return None


def scan_one_file(path: Path, kind: str) -> ScanRow:
    ticker = ticker_from_filename(path)
    file_size_mb = round(path.stat().st_size / (1024 * 1024), 6)

    rows = 0
    start_date = None
    end_date = None
    close_valid = 0
    volume_valid = 0
    zero_volume_count = 0

    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return ScanRow(
                    kind=kind,
                    ticker=ticker,
                    file_name=path.name,
                    file_path=str(path.resolve()),
                    file_size_mb=file_size_mb,
                    rows=0,
                    start_date=None,
                    end_date=None,
                    close_fill_rate=0.0,
                    volume_fill_rate=0.0,
                    zero_volume_share=1.0,
                    status="error",
                    error="Empty file or missing header",
                )

            header_map = {h.strip().lower(): i for i, h in enumerate(header)}
            date_idx = header_map.get("date")
            close_idx = header_map.get("close")
            volume_idx = header_map.get("volume")

            if date_idx is None:
                return ScanRow(
                    kind=kind,
                    ticker=ticker,
                    file_name=path.name,
                    file_path=str(path.resolve()),
                    file_size_mb=file_size_mb,
                    rows=0,
                    start_date=None,
                    end_date=None,
                    close_fill_rate=0.0,
                    volume_fill_rate=0.0,
                    zero_volume_share=1.0,
                    status="error",
                    error="Missing Date column",
                )

            for row in reader:
                if not row:
                    continue
                if len(row) <= date_idx:
                    continue

                date_raw = row[date_idx].strip()
                if not date_raw:
                    continue

                rows += 1

                date_val = safe_date(date_raw)
                if rows == 1:
                    start_date = date_val or date_raw
                end_date = date_val or date_raw

                close_val = None
                if close_idx is not None and len(row) > close_idx:
                    close_val = safe_float(row[close_idx])
                if close_val is not None and not math.isnan(close_val):
                    close_valid += 1

                volume_val = None
                if volume_idx is not None and len(row) > volume_idx:
                    volume_val = safe_float(row[volume_idx])
                if volume_val is not None and not math.isnan(volume_val):
                    volume_valid += 1
                    if volume_val <= 0:
                        zero_volume_count += 1

        close_fill_rate = (close_valid / rows) if rows else 0.0
        volume_fill_rate = (volume_valid / rows) if rows else 0.0
        zero_volume_share = (zero_volume_count / volume_valid) if volume_valid else 1.0

        return ScanRow(
            kind=kind,
            ticker=ticker,
            file_name=path.name,
            file_path=str(path.resolve()),
            file_size_mb=file_size_mb,
            rows=rows,
            start_date=start_date,
            end_date=end_date,
            close_fill_rate=round(close_fill_rate, 6),
            volume_fill_rate=round(volume_fill_rate, 6),
            zero_volume_share=round(zero_volume_share, 6),
            status="ok",
            error="",
        )

    except Exception as e:
        return ScanRow(
            kind=kind,
            ticker=ticker,
            file_name=path.name,
            file_path=str(path.resolve()),
            file_size_mb=file_size_mb,
            rows=rows,
            start_date=start_date,
            end_date=end_date,
            close_fill_rate=0.0 if rows == 0 else round(close_valid / rows, 6),
            volume_fill_rate=0.0 if rows == 0 else round(volume_valid / rows, 6),
            zero_volume_share=1.0 if volume_valid == 0 else round(zero_volume_count / volume_valid, 6),
            status="error",
            error=repr(e),
        )


def scan_dir(dir_path: Path, kind: str, workers: int) -> list[ScanRow]:
    files = sorted(dir_path.glob("*.txt"))
    log(f"[cyan]Scanning {kind}: {len(files)} files in {dir_path}[/cyan]" if console else f"Scanning {kind}: {len(files)} files")

    results: list[ScanRow] = []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(scan_one_file, path, kind): path for path in files}
        done_count = 0
        total = len(futures)

        for fut in as_completed(futures):
            results.append(fut.result())
            done_count += 1
            if done_count % 500 == 0 or done_count == total:
                log(f"[green]{kind}: scanned {done_count}/{total}[/green]" if console else f"{kind}: scanned {done_count}/{total}")

    return results


def normalize_series(s: pd.Series) -> pd.Series:
    if s.empty:
        return s
    s = s.astype(float)
    s_min = s.min()
    s_max = s.max()
    if pd.isna(s_min) or pd.isna(s_max) or s_max == s_min:
        return pd.Series([1.0] * len(s), index=s.index)
    return (s - s_min) / (s_max - s_min)


def build_scores(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()
    out["end_date_dt"] = pd.to_datetime(out["end_date"], errors="coerce")
    global_max_end = out["end_date_dt"].max()

    out["days_lag"] = (global_max_end - out["end_date_dt"]).dt.days.fillna(999999)
    out["history_score"] = normalize_series(out["rows"])
    out["recency_score"] = 1.0 - normalize_series(out["days_lag"])
    out["quality_score"] = (
        0.50 * out["close_fill_rate"].fillna(0.0)
        + 0.30 * out["volume_fill_rate"].fillna(0.0)
        + 0.20 * (1.0 - out["zero_volume_share"].fillna(1.0))
    )
    out["score"] = (
        0.55 * out["history_score"]
        + 0.30 * out["recency_score"]
        + 0.15 * out["quality_score"]
    )
    return out


def select_top(
    df: pd.DataFrame,
    target_count: int,
    min_rows: int,
    min_close_fill: float,
    min_volume_fill: float,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    eligible = df[
        (df["status"] == "ok")
        & (df["rows"] >= min_rows)
        & (df["close_fill_rate"] >= min_close_fill)
        & (df["volume_fill_rate"] >= min_volume_fill)
    ].copy()

    eligible = eligible.sort_values(
        by=["score", "rows", "end_date_dt", "close_fill_rate", "volume_fill_rate"],
        ascending=[False, False, False, False, False],
    )

    if len(eligible) >= target_count:
        return eligible.head(target_count).copy()

    fallback = df[df["status"] == "ok"].copy()
    fallback = fallback.sort_values(
        by=["score", "rows", "end_date_dt", "close_fill_rate", "volume_fill_rate"],
        ascending=[False, False, False, False, False],
    )

    selected = fallback.head(target_count).copy()
    return selected


def save_manifest_txt(path: Path, tickers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(tickers) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    data_root = (repo_root / args.data_root).resolve()
    stocks_dir = data_root / args.stocks_dir
    etfs_dir = data_root / args.etfs_dir
    output_dir = (repo_root / args.output_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    if not stocks_dir.exists():
        raise FileNotFoundError(f"Stocks dir not found: {stocks_dir}")
    if not etfs_dir.exists():
        raise FileNotFoundError(f"ETFs dir not found: {etfs_dir}")

    stocks_rows = scan_dir(stocks_dir, "stock", args.workers)
    etfs_rows = scan_dir(etfs_dir, "etf", args.workers)

    all_rows = stocks_rows + etfs_rows
    scan_df = pd.DataFrame([asdict(r) for r in all_rows])

    stocks_df = build_scores(scan_df[scan_df["kind"] == "stock"].copy())
    etfs_df = build_scores(scan_df[scan_df["kind"] == "etf"].copy())

    selected_stocks = select_top(
        stocks_df,
        target_count=args.stock_count,
        min_rows=args.min_rows,
        min_close_fill=args.min_close_fill,
        min_volume_fill=args.min_volume_fill,
    )
    selected_etfs = select_top(
        etfs_df,
        target_count=args.etf_count,
        min_rows=args.min_rows,
        min_close_fill=args.min_close_fill,
        min_volume_fill=args.min_volume_fill,
    )

    selected_df = pd.concat([selected_stocks, selected_etfs], ignore_index=True)
    selected_df = selected_df.sort_values(by=["kind", "score", "rows"], ascending=[True, False, False])

    scan_csv = output_dir / "universe_scan_all.csv"
    stocks_csv = output_dir / "universe_scan_stocks.csv"
    etfs_csv = output_dir / "universe_scan_etfs.csv"
    selected_csv = output_dir / "selected_files.csv"

    scan_df.to_csv(scan_csv, index=False, encoding="utf-8-sig")
    stocks_df.sort_values(by=["score", "rows"], ascending=[False, False]).to_csv(
        stocks_csv, index=False, encoding="utf-8-sig"
    )
    etfs_df.sort_values(by=["score", "rows"], ascending=[False, False]).to_csv(
        etfs_csv, index=False, encoding="utf-8-sig"
    )
    selected_df.to_csv(selected_csv, index=False, encoding="utf-8-sig")

    stock_tickers = selected_stocks["ticker"].astype(str).tolist()
    etf_tickers = selected_etfs["ticker"].astype(str).tolist()
    all_tickers = stock_tickers + etf_tickers

    save_manifest_txt(output_dir / "selected_stocks.txt", stock_tickers)
    save_manifest_txt(output_dir / "selected_etfs.txt", etf_tickers)
    save_manifest_txt(output_dir / "selected_all.txt", all_tickers)

    summary = {
        "data_root": str(data_root),
        "stocks_dir": str(stocks_dir),
        "etfs_dir": str(etfs_dir),
        "total_scanned": int(len(scan_df)),
        "stocks_scanned": int((scan_df["kind"] == "stock").sum()),
        "etfs_scanned": int((scan_df["kind"] == "etf").sum()),
        "stocks_selected": int(len(selected_stocks)),
        "etfs_selected": int(len(selected_etfs)),
        "total_selected": int(len(selected_df)),
        "selection_params": {
            "stock_count": args.stock_count,
            "etf_count": args.etf_count,
            "min_rows": args.min_rows,
            "min_close_fill": args.min_close_fill,
            "min_volume_fill": args.min_volume_fill,
        },
        "artifacts": {
            "scan_all_csv": str(scan_csv),
            "scan_stocks_csv": str(stocks_csv),
            "scan_etfs_csv": str(etfs_csv),
            "selected_csv": str(selected_csv),
            "selected_stocks_txt": str(output_dir / "selected_stocks.txt"),
            "selected_etfs_txt": str(output_dir / "selected_etfs.txt"),
            "selected_all_txt": str(output_dir / "selected_all.txt"),
        },
    }

    summary_json = output_dir / "selection_summary.json"
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if console:
        table = Table(title="Research universe selection summary")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Stocks scanned", str(summary["stocks_scanned"]))
        table.add_row("ETFs scanned", str(summary["etfs_scanned"]))
        table.add_row("Stocks selected", str(summary["stocks_selected"]))
        table.add_row("ETFs selected", str(summary["etfs_selected"]))
        table.add_row("Total selected", str(summary["total_selected"]))
        table.add_row("Selected CSV", str(selected_csv))
        console.print(table)

        preview = selected_df[["kind", "ticker", "rows", "end_date", "score"]].head(15).copy()
        preview["score"] = preview["score"].round(6)
        preview_table = Table(title="Selection preview")
        for col in preview.columns:
            preview_table.add_column(col)
        for _, row in preview.iterrows():
            preview_table.add_row(*(str(v) for v in row.tolist()))
        console.print(preview_table)
    else:
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    log(f"[bold green]Done.[/bold green] Selection artifacts saved to: {output_dir}" if console else f"Done. Saved to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())