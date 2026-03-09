from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(slots=True)
class PositionPolicyConfig:
    enter_quantile: float = 0.70
    exit_quantile: float = 0.45
    edge_buffer_bps: float = 5.0
    min_hold_bars: int = 5
    cooldown_bars: int = 3
    trend_sma_window: int = 200
    use_trend_filter: bool = True
    block_regimes: tuple[str, ...] = ("Bear_HighVol",)
    vol_target_annual: float = 0.18
    vol_lookback: int = 20
    max_position: float = 1.0
    min_position: float = 0.0
    confidence_floor: float = 0.25
    confidence_cap: float = 1.00
    execution_lag: int = 1


def _first_existing_col(df: pd.DataFrame, names: Iterable[str]) -> str | None:
    lower_map = {c.lower(): c for c in df.columns}
    for name in names:
        if name in df.columns:
            return name
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def _coerce_numeric(series: pd.Series, fill: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(fill).astype(float)


def resolve_close_col(df: pd.DataFrame) -> str:
    col = _first_existing_col(df, ["close", "Close"])
    if col is None:
        raise KeyError("Could not find close column ('close' / 'Close').")
    return col


def resolve_return_col(df: pd.DataFrame) -> str:
    col = _first_existing_col(df, ["return_1d", "ret_1d", "daily_return"])
    if col is not None:
        return col

    close_col = resolve_close_col(df)
    df["return_1d"] = _coerce_numeric(df[close_col]).pct_change().fillna(0.0)
    return "return_1d"


def resolve_trend_reference(df: pd.DataFrame, trend_sma_window: int) -> pd.Series:
    close_col = resolve_close_col(df)
    candidates = [
        f"sma_{trend_sma_window}",
        f"SMA_{trend_sma_window}",
        f"ma_{trend_sma_window}",
        f"MA_{trend_sma_window}",
    ]
    sma_col = _first_existing_col(df, candidates)

    close = _coerce_numeric(df[close_col])
    if sma_col is not None:
        sma = _coerce_numeric(df[sma_col])
    else:
        sma = close.rolling(trend_sma_window, min_periods=max(20, trend_sma_window // 4)).mean()

    return close > sma


def compute_dynamic_thresholds(
    train_predictions: np.ndarray | pd.Series,
    *,
    commission_bps: float = 0.0,
    slippage_k: float = 0.0,
    enter_quantile: float = 0.70,
    exit_quantile: float = 0.45,
    edge_buffer_bps: float = 5.0,
) -> tuple[float, float]:
    """
    Build entry/exit thresholds from the train-window prediction distribution.

    Key idea:
    - do not enter just because prediction > 0
    - require forecasted edge to exceed costs + noise buffer
    """
    preds = pd.Series(np.asarray(train_predictions, dtype=float)).replace([np.inf, -np.inf], np.nan).dropna()
    if preds.empty:
        base = (commission_bps / 10_000.0) + max(0.0, slippage_k) * 0.0005 + edge_buffer_bps / 10_000.0
        return float(base), float(base * 0.35)

    positive = preds[preds > 0]
    source = positive if not positive.empty else preds

    q_enter = float(source.quantile(min(max(enter_quantile, 0.05), 0.95)))
    q_exit = float(source.quantile(min(max(exit_quantile, 0.05), 0.95)))

    cost_floor = (commission_bps / 10_000.0) + max(0.0, slippage_k) * 0.0005 + edge_buffer_bps / 10_000.0
    enter_thr = max(q_enter, cost_floor)
    exit_thr = max(min(q_exit, enter_thr * 0.75), cost_floor * 0.35)

    return float(enter_thr), float(exit_thr)


def build_long_only_positions(
    df: pd.DataFrame,
    *,
    prediction_col: str = "pred",
    lower_bound_col: str | None = None,
    regime_col: str = "market_regime",
    commission_bps: float = 0.0,
    slippage_k: float = 0.0,
    enter_threshold: float,
    exit_threshold: float,
    policy: PositionPolicyConfig | None = None,
) -> pd.DataFrame:
    """
    Build a long-only position path with:

    - dynamic entry threshold
    - different exit threshold (hysteresis)
    - trend filter
    - optional regime blocklist
    - volatility targeting
    - execution lag

    Important:
    - decision_* columns describe MODEL DECISION on the current bar
    - execution_* columns describe REAL EXECUTION after execution_lag
    - signal is kept as a backward-compatible alias to execution_entry_signal
    """
    if policy is None:
        policy = PositionPolicyConfig()

    out = df.copy().sort_values("date").reset_index(drop=True)

    if prediction_col not in out.columns:
        raise KeyError(f"Prediction column '{prediction_col}' not found.")

    ret_col = resolve_return_col(out)
    close_col = resolve_close_col(out)

    pred = _coerce_numeric(out[prediction_col])
    lower = (
        _coerce_numeric(out[lower_bound_col], fill=np.nan)
        if lower_bound_col and lower_bound_col in out.columns
        else None
    )
    daily_ret = _coerce_numeric(out[ret_col])

    trend_ok = (
        resolve_trend_reference(out, policy.trend_sma_window)
        if policy.use_trend_filter
        else pd.Series(True, index=out.index)
    )

    if regime_col in out.columns:
        blocked = out[regime_col].astype(str).isin(set(policy.block_regimes))
    else:
        blocked = pd.Series(False, index=out.index)

    realized_vol = daily_ret.rolling(
        policy.vol_lookback,
        min_periods=max(5, policy.vol_lookback // 3),
    ).std()
    annualized_vol = realized_vol * np.sqrt(252.0)
    vol_scale = (policy.vol_target_annual / annualized_vol.replace(0.0, np.nan)).clip(
        lower=policy.min_position,
        upper=policy.max_position,
    )
    vol_scale = vol_scale.replace([np.inf, -np.inf], np.nan).fillna(policy.max_position)

    edge = pred - float(enter_threshold)
    raw_conf = ((edge / max(float(enter_threshold), 1e-9)) + 1.0).clip(
        lower=policy.confidence_floor,
        upper=policy.confidence_cap,
    )

    desired_weight = (raw_conf * vol_scale).clip(
        lower=policy.min_position,
        upper=policy.max_position,
    )

    # Entry/exit logic for decision day
    if lower is not None:
        point_entry_ok = lower > float(enter_threshold)
    else:
        point_entry_ok = pred > float(enter_threshold)

    point_exit_ok = pred < float(exit_threshold)

    enter_ok = point_entry_ok & trend_ok & (~blocked)
    exit_ok = point_exit_ok | (~trend_ok) | blocked

    decision_weight = np.zeros(len(out), dtype=float)
    decision_entry_signal = np.zeros(len(out), dtype=int)
    decision_exit_signal = np.zeros(len(out), dtype=int)

    in_pos = False
    current_weight = 0.0
    hold_bars = 0
    cooldown_left = 0

    for i in range(len(out)):
        if cooldown_left > 0:
            cooldown_left -= 1

        if not in_pos:
            if cooldown_left == 0 and bool(enter_ok.iloc[i]):
                in_pos = True
                current_weight = float(desired_weight.iloc[i])
                hold_bars = 0
                decision_entry_signal[i] = 1
            else:
                current_weight = 0.0
        else:
            hold_bars += 1

            # Rebalance while position is open
            current_weight = float(
                np.clip(
                    desired_weight.iloc[i],
                    policy.min_position,
                    policy.max_position,
                )
            )

            if hold_bars >= int(policy.min_hold_bars) and bool(exit_ok.iloc[i]):
                in_pos = False
                current_weight = 0.0
                cooldown_left = int(policy.cooldown_bars)
                hold_bars = 0
                decision_exit_signal[i] = 1

        decision_weight[i] = current_weight

    out["enter_threshold"] = float(enter_threshold)
    out["exit_threshold"] = float(exit_threshold)

    out["trend_ok"] = trend_ok.astype(int)
    out["blocked_regime"] = blocked.astype(int)

    out["point_entry_ok"] = point_entry_ok.astype(int)
    out["point_exit_ok"] = point_exit_ok.astype(int)
    out["decision_enter_ok"] = enter_ok.astype(int)
    out["decision_exit_ok"] = exit_ok.astype(int)

    out["vol_scale"] = vol_scale.astype(float)
    out["confidence"] = raw_conf.astype(float)
    out["desired_weight"] = desired_weight.astype(float)

    out["decision_weight"] = decision_weight
    out["decision_position"] = decision_weight

    out["decision_entry_signal"] = decision_entry_signal
    out["decision_exit_signal"] = decision_exit_signal

    lag = max(int(policy.execution_lag), 0)

    out["position"] = (
        pd.Series(decision_weight, index=out.index)
        .shift(lag)
        .fillna(0.0)
        .clip(lower=policy.min_position, upper=policy.max_position)
    )

    prev_exec_pos = out["position"].shift(1).fillna(0.0)
    out["execution_entry_signal"] = (
        ((out["position"] > 0).astype(int) - (prev_exec_pos > 0).astype(int)).clip(lower=0)
    )
    out["execution_exit_signal"] = (
        ((prev_exec_pos > 0).astype(int) - (out["position"] > 0).astype(int)).clip(lower=0)
    )

    # Backward-compatible alias
    out["signal"] = out["execution_entry_signal"]

    out["turnover"] = out["position"].diff().abs().fillna(out["position"].abs())

    commission_rate = float(commission_bps) / 10_000.0
    out["commission_cost"] = out["turnover"] * commission_rate
    out["slippage_cost"] = out["turnover"] * float(slippage_k) * daily_ret.abs().clip(upper=0.05)
    out["total_cost"] = out["commission_cost"] + out["slippage_cost"]

    out["gross_ret"] = out["position"] * daily_ret
    out["net_ret"] = out["gross_ret"] - out["total_cost"]

    # Compatibility aliases
    out["strategy_return"] = out["net_ret"]
    out["actual_return"] = daily_ret
    out["close_used"] = _coerce_numeric(out[close_col])

    return out


def attach_equity_curve(sim_df: pd.DataFrame, *, initial_equity: float = 1.0) -> pd.DataFrame:
    out = sim_df.copy()
    net_ret = _coerce_numeric(out["net_ret"])
    out["equity"] = float(initial_equity) * (1.0 + net_ret).cumprod()
    out["capital"] = out["equity"]
    out["drawdown"] = out["equity"] / out["equity"].cummax() - 1.0
    return out


def build_buyhold_path(
    df: pd.DataFrame,
    *,
    initial_equity: float = 1.0,
) -> pd.DataFrame:
    out = df.copy().sort_values("date").reset_index(drop=True)
    ret_col = resolve_return_col(out)
    daily_ret = _coerce_numeric(out[ret_col])

    out["position"] = 1.0
    out["decision_position"] = 1.0
    out["decision_weight"] = 1.0

    out["decision_entry_signal"] = 0
    out["decision_exit_signal"] = 0
    out["execution_entry_signal"] = 0
    out["execution_exit_signal"] = 0
    out["signal"] = 0

    out["turnover"] = 0.0
    out["commission_cost"] = 0.0
    out["slippage_cost"] = 0.0
    out["total_cost"] = 0.0
    out["gross_ret"] = daily_ret
    out["net_ret"] = daily_ret
    out["strategy_return"] = out["net_ret"]
    out["actual_return"] = daily_ret
    out["equity"] = float(initial_equity) * (1.0 + daily_ret).cumprod()
    out["capital"] = out["equity"]
    out["drawdown"] = out["equity"] / out["equity"].cummax() - 1.0
    return out