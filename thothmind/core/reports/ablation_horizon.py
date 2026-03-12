from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _safe_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def _stage_for_run(run_dir: Path) -> Optional[str]:
    if (run_dir / "suite_summary.csv").exists() or (run_dir / "tickers").exists():
        return "m8"
    if (run_dir / "oos_significance.json").exists():
        return "m7"
    return None


def _read_horizon_from_df_feat(df_feat_path: Path) -> Optional[int]:
    if not df_feat_path.exists():
        return None
    try:
        df = pd.read_csv(df_feat_path, usecols=["horizon"])
        if df.empty:
            return None
        return int(df["horizon"].iloc[0])
    except Exception:
        return None


def _read_m7_horizon(run_dir: Path) -> Optional[int]:
    return _read_horizon_from_df_feat(run_dir / "df_feat.csv")


def _read_m8_horizon(run_dir: Path) -> Optional[int]:
    tickers_dir = run_dir / "tickers"
    if not tickers_dir.exists():
        return None

    spy = tickers_dir / "SPY" / "df_feat.csv"
    if spy.exists():
        h = _read_horizon_from_df_feat(spy)
        if h is not None:
            return h

    for p in sorted(tickers_dir.glob("*")):
        if p.is_dir():
            h = _read_horizon_from_df_feat(p / "df_feat.csv")
            if h is not None:
                return h
    return None


def _extract_regime_deltas(regime_wide_csv: Path) -> Dict[str, float]:
    """
    Flat dict keys like:
      delta_worst_drawdown__bear_high_vol, delta_mean_net_ret__bull_low_vol, ...
    """
    if not regime_wide_csv.exists():
        return {}
    df = pd.read_csv(regime_wide_csv)
    if df.empty or "regime" not in df.columns:
        return {}

    out: Dict[str, float] = {}
    for _, row in df.iterrows():
        regime = str(row["regime"])
        for col in ["delta_mean_net_ret", "delta_sharpe", "delta_total_rel_return", "delta_worst_drawdown"]:
            if col in df.columns:
                out[f"{col}__{regime}"] = _safe_float(row[col])
    return out


def summarize_m7(run_dir: Path) -> Dict[str, Any]:
    sig_path = run_dir / "oos_significance.json"
    sig = _read_json(sig_path) if sig_path.exists() else {}

    horizon = _read_m7_horizon(run_dir)
    out: Dict[str, Any] = {
        "run_id": run_dir.name,
        "stage": "m7",
        "horizon": horizon,
        "actual_rel_return": _safe_float(sig.get("actual_rel_return")),
        "prob_outperform": _safe_float(sig.get("prob_outperform")),
        "p_value_one_sided": _safe_float(sig.get("p_value_one_sided")),
        "ci_rel_return_low": _safe_float(sig.get("ci_rel_return_low")),
        "ci_rel_return_high": _safe_float(sig.get("ci_rel_return_high")),
    }
    out.update(_extract_regime_deltas(run_dir / "regime" / "regime_summary_wide.csv"))
    return out


def _aggregate_suite_summary(suite_csv: Path) -> Dict[str, Any]:
    df = pd.read_csv(suite_csv)
    if df.empty:
        return {}

    if "status" in df.columns:
        ok = df[df["status"].astype(str).str.lower() == "ok"].copy()
    else:
        ok = df.copy()

    out: Dict[str, Any] = {"n_tickers": int(len(df)), "n_ok": int(len(ok))}
    if ok.empty:
        return out

    for col in ["actual_rel_return", "prob_outperform", "p_value_one_sided"]:
        if col in ok.columns:
            out[f"{col}_mean"] = _safe_float(ok[col].mean())
            out[f"{col}_median"] = _safe_float(ok[col].median())

    if "actual_rel_return" in ok.columns:
        best_idx = ok["actual_rel_return"].astype(float).idxmax()
        worst_idx = ok["actual_rel_return"].astype(float).idxmin()
        out["best_ticker"] = str(ok.loc[best_idx, "ticker"])
        out["best_rel_return"] = _safe_float(ok.loc[best_idx, "actual_rel_return"])
        out["worst_ticker"] = str(ok.loc[worst_idx, "ticker"])
        out["worst_rel_return"] = _safe_float(ok.loc[worst_idx, "actual_rel_return"])

    return out


def _aggregate_m8_regimes(run_dir: Path) -> pd.DataFrame:
    tickers_dir = run_dir / "tickers"
    rows = []

    for tdir in sorted(tickers_dir.glob("*")):
        if not tdir.is_dir():
            continue
        wide = tdir / "regime" / "regime_summary_wide.csv"
        if not wide.exists():
            continue
        df = pd.read_csv(wide)
        if df.empty or "regime" not in df.columns:
            continue
        df["ticker"] = tdir.name
        rows.append(df)

    if not rows:
        return pd.DataFrame()

    allw = pd.concat(rows, ignore_index=True)

    keep = ["ticker", "regime"]
    for c in ["delta_worst_drawdown", "delta_mean_net_ret", "delta_total_rel_return", "delta_sharpe"]:
        if c in allw.columns:
            keep.append(c)
    allw = allw[keep].copy()

    def _share_pos(s: pd.Series) -> float:
        s = pd.to_numeric(s, errors="coerce").dropna()
        if s.empty:
            return float("nan")
        return float((s > 0).mean())

    grp = allw.groupby("regime", dropna=False)
    out = pd.DataFrame({"regime": grp.size().index, "n_tickers": grp.size().values})

    for col in ["delta_worst_drawdown", "delta_mean_net_ret", "delta_total_rel_return", "delta_sharpe"]:
        if col in allw.columns:
            out[f"{col}_mean"] = grp[col].mean().values
            out[f"{col}_median"] = grp[col].median().values
            out[f"{col}_share_pos"] = grp[col].apply(_share_pos).values

    return out.sort_values("regime").reset_index(drop=True)


def summarize_m8(run_dir: Path) -> Tuple[Dict[str, Any], pd.DataFrame]:
    horizon = _read_m8_horizon(run_dir)
    out: Dict[str, Any] = {"run_id": run_dir.name, "stage": "m8", "horizon": horizon}

    suite_csv = run_dir / "suite_summary.csv"
    if suite_csv.exists():
        out.update(_aggregate_suite_summary(suite_csv))

    reg = _aggregate_m8_regimes(run_dir)
    if not reg.empty:
        reg.insert(0, "run_id", run_dir.name)
        reg.insert(1, "horizon", horizon)

    return out, reg


def collect(runs_root: Path, out_dir: Path) -> None:
    runs_root = runs_root.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    run_dirs = sorted([p for p in runs_root.glob("*") if p.is_dir()], key=lambda p: p.name)

    # keep only latest run per (stage, horizon)
    latest: Dict[Tuple[str, int], Path] = {}

    for rd in run_dirs:
        stage = _stage_for_run(rd)
        if stage is None:
            continue
        h = _read_m7_horizon(rd) if stage == "m7" else _read_m8_horizon(rd)
        if h is None:
            continue
        latest[(stage, int(h))] = rd  # last wins

    m7_rows = []
    m8_rows = []
    m8_regs = []

    for (stage, h), rd in sorted(latest.items(), key=lambda x: (x[0][0], x[0][1])):
        if stage == "m7":
            m7_rows.append(summarize_m7(rd))
        else:
            row, reg = summarize_m8(rd)
            m8_rows.append(row)
            if reg is not None and not reg.empty:
                m8_regs.append(reg)

    if m7_rows:
        pd.DataFrame(m7_rows).sort_values("horizon").to_csv(out_dir / "horizon_m7_summary.csv", index=False)
    if m8_rows:
        pd.DataFrame(m8_rows).sort_values("horizon").to_csv(out_dir / "horizon_m8_summary.csv", index=False)
    if m8_regs:
        pd.concat(m8_regs, ignore_index=True).to_csv(out_dir / "horizon_m8_regime_summary.csv", index=False)

    print(f"[ablation] wrote -> {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect horizon ablation summaries for ThothMind (m7/m8).")
    ap.add_argument("--runs", type=str, default="reports/runs", help="Root folder with run_id subfolders.")
    ap.add_argument("--out", type=str, default="reports/ablation", help="Output folder for ablation CSVs.")
    args = ap.parse_args()

    collect(Path(args.runs), Path(args.out))


if __name__ == "__main__":
    main()