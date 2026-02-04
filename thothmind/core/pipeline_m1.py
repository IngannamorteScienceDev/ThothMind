from __future__ import annotations

from dataclasses import asdict, dataclass
import pandas as pd

from .data.source import load_ohlcv
from .features.pipeline import build_features, infer_feature_columns
from .regimes.labeler import add_regimes


@dataclass
class DataSnapshot:
    rows: int
    cols: list[str]
    date_start: str
    date_end: str
    n_missing_total: int
    missing_by_col: dict


def make_snapshot(df: pd.DataFrame) -> dict:
    miss = df.isna().sum().to_dict()
    snap = DataSnapshot(
        rows=int(len(df)),
        cols=list(df.columns),
        date_start=str(df["date"].min()),
        date_end=str(df["date"].max()),
        n_missing_total=int(sum(miss.values())),
        missing_by_col={k: int(v) for k, v in miss.items()},
    )
    return asdict(snap)


def build_df_feat(cfg: dict) -> tuple[pd.DataFrame, dict]:
    # --- Data ---
    data_cfg = cfg.get("data", {})
    ticker = data_cfg.get("ticker") or (data_cfg.get("universe", ["SPY"])[0])
    base_path = data_cfg.get("base_path", "data")
    start = data_cfg.get("start")
    end = data_cfg.get("end")

    df_raw = load_ohlcv(ticker=ticker, base_path=base_path, start=start, end=end)

    # --- Features ---
    feat_cfg = cfg.get("features", {})
    df_feat = build_features(
        df_raw,
        horizon=int(feat_cfg.get("horizon", 1)),
        sma_windows=feat_cfg.get("sma_windows"),
        vol_windows=feat_cfg.get("vol_windows"),
        lags=feat_cfg.get("lags"),
    )

    # --- Regimes ---
    reg_cfg = cfg.get("regimes", {})
    df_feat = add_regimes(
        df_feat,
        vol_window=int(reg_cfg.get("vol_window", 20)),
        vol_median_window=int(reg_cfg.get("vol_median_window", 252)),
        trend_sma_window=int(reg_cfg.get("trend_sma_window", 200)),
    )

    snapshot = make_snapshot(df_feat)
    snapshot["ticker"] = str(ticker)
    snapshot["feature_cols"] = infer_feature_columns(df_feat)

    return df_feat, snapshot
