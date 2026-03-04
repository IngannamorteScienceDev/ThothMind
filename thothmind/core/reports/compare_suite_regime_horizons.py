from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

import pandas as pd


def _read_horizon_from_run(run_dir: Path) -> Optional[int]:
    # Prefer SPY df_feat
    spy = run_dir / "tickers" / "SPY" / "df_feat.csv"
    if spy.exists():
        try:
            df = pd.read_csv(spy, usecols=["horizon"])
            if not df.empty:
                return int(df["horizon"].iloc[0])
        except Exception:
            pass

    # Fallback: first ticker
    tickers_dir = run_dir / "tickers"
    if tickers_dir.exists():
        for tdir in sorted(tickers_dir.glob("*")):
            if not tdir.is_dir():
                continue
            p = tdir / "df_feat.csv"
            if p.exists():
                try:
                    df = pd.read_csv(p, usecols=["horizon"])
                    if not df.empty:
                        return int(df["horizon"].iloc[0])
                except Exception:
                    continue
    return None


def _ensure_suite_regime(run_dir: Path) -> Path:
    # We assume suite_regime has been generated already; if not, user can run:
    # python -m thothmind.core.reports.suite_regime --run reports/runs/<run_id>
    p = run_dir / "suite_regime" / "suite_regime_summary.csv"
    if not p.exists():
        raise FileNotFoundError(f"Missing suite regime summary: {p}")
    return p


def collect(runs: List[Path]) -> pd.DataFrame:
    rows = []
    for run_dir in runs:
        run_dir = run_dir.expanduser().resolve()
        run_id = run_dir.name
        horizon = _read_horizon_from_run(run_dir)

        suite_csv = _ensure_suite_regime(run_dir)
        df = pd.read_csv(suite_csv)
        if df.empty:
            continue

        df = df.copy()
        df.insert(0, "run_id", run_id)
        df.insert(1, "horizon", horizon)

        # keep only the most defensible columns (others remain if you want)
        preferred = [
            "run_id",
            "horizon",
            "regime",
            "n_tickers",
            "total_weight_days",
            "delta_mean_net_ret_wmean",
            "delta_mean_net_ret_share_pos",
            "delta_worst_drawdown_wmean",
            "delta_worst_drawdown_share_pos",
            "delta_sharpe_wmean",
            "delta_total_rel_return_wmean",
        ]
        keep = [c for c in preferred if c in df.columns]
        df = df[keep].copy()

        rows.append(df)

    if not rows:
        return pd.DataFrame()

    out = pd.concat(rows, ignore_index=True)
    out = out.sort_values(["horizon", "regime"]).reset_index(drop=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare suite-level regime deltas across horizons.")
    ap.add_argument(
        "--runs",
        nargs="+",
        required=True,
        help="Run directories: reports/runs/<run_id> (one per horizon).",
    )
    ap.add_argument(
        "--out",
        type=str,
        default="reports/ablation/suite_regime_compare.csv",
        help="Output CSV path.",
    )
    args = ap.parse_args()

    runs = [Path(x) for x in args.runs]
    df = collect(runs)
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"[compare_suite_regime] rows={len(df)} -> {out_path}")


if __name__ == "__main__":
    main()