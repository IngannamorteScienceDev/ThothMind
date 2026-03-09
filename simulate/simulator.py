from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd


def _resolve_daily_returns(
    df: pd.DataFrame,
    daily_return_col: Optional[str] = None,
) -> pd.Series:
    """
    Return a per-bar return series for simulation.

    Priority:
    1. explicitly provided daily_return_col
    2. return_1d
    3. pct_change() from Close
    """
    if daily_return_col:
        if daily_return_col not in df.columns:
            raise KeyError(f"Column '{daily_return_col}' not found in DataFrame.")
        returns = pd.to_numeric(df[daily_return_col], errors="coerce")
        return returns.fillna(0.0)

    if "return_1d" in df.columns:
        returns = pd.to_numeric(df["return_1d"], errors="coerce")
        return returns.fillna(0.0)

    if "Close" in df.columns:
        returns = pd.to_numeric(df["Close"], errors="coerce").pct_change()
        return returns.fillna(0.0)

    raise KeyError(
        "Could not infer per-bar returns. Provide `daily_return_col`, or add "
        "'return_1d' / 'Close' to the DataFrame."
    )


def _resolve_horizon(
    df: pd.DataFrame,
    horizon: Optional[int] = None,
    target_col: Optional[str] = None,
) -> int:
    """
    Infer holding horizon.

    If not provided explicitly, tries to parse a target column like:
    - target_return_5d
    - target_return_10d
    """
    if horizon is not None:
        if horizon <= 0:
            raise ValueError("`horizon` must be positive.")
        return int(horizon)

    candidate_cols: Iterable[str]
    if target_col:
        candidate_cols = [target_col]
    else:
        candidate_cols = [c for c in df.columns if c.startswith("target_return_") and c.endswith("d")]

    for col in candidate_cols:
        digits = "".join(ch for ch in col if ch.isdigit())
        if digits:
            inferred = int(digits)
            if inferred > 0:
                return inferred

    return 5


def _build_position_schedule(
    n_rows: int,
    signals: np.ndarray,
    allocation: float,
    horizon: int,
    execution_lag: int,
    allow_overlap: bool,
    max_leverage: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert entry signals into an exposure schedule.

    Important:
    - returns are assumed to be per-bar returns (e.g. daily return_1d)
    - a signal on row i starts earning PnL only from row i + execution_lag + 1
    - horizon is the number of future bars held
    """
    if execution_lag < 0:
        raise ValueError("`execution_lag` cannot be negative.")
    if horizon <= 0:
        raise ValueError("`horizon` must be positive.")
    if not 0.0 <= allocation <= max_leverage:
        raise ValueError("`allocation` must be within [0, max_leverage].")

    position = np.zeros(n_rows, dtype=float)
    executed_entries = np.zeros(n_rows, dtype=int)

    last_exit_idx = -1

    for signal_idx, signal in enumerate(signals):
        if signal <= 0:
            continue

        hold_start = signal_idx + execution_lag + 1
        hold_end = hold_start + horizon - 1

        # Require a full holding window to avoid partial/fake last trades.
        if hold_start >= n_rows or hold_end >= n_rows:
            continue

        if not allow_overlap and hold_start <= last_exit_idx:
            continue

        if allow_overlap:
            position[hold_start:hold_end + 1] += allocation
            position[hold_start:hold_end + 1] = np.clip(
                position[hold_start:hold_end + 1], 0.0, max_leverage
            )
        else:
            position[hold_start:hold_end + 1] = allocation

        executed_entries[hold_start] += 1
        last_exit_idx = max(last_exit_idx, hold_end)

    return position, executed_entries


def simulate_strategy(
    df: pd.DataFrame,
    y_pred: np.ndarray,
    threshold: float = 0.01,
    *,
    horizon: Optional[int] = None,
    execution_lag: int = 1,
    allocation: float = 1.0,
    commission: float = 0.001,
    allow_overlap: bool = False,
    daily_return_col: Optional[str] = None,
    target_col: Optional[str] = None,
) -> pd.DataFrame:
    """
    Simulate a trading strategy with honest per-bar PnL.

    Core fixes vs the old implementation:
    1. We DO NOT use target_return_5d as if it were a daily/bar return.
    2. We build a real holding schedule over future bars.
    3. We charge commission on turnover (entry + exit).
    4. We separate `signal` (entry event) from `position` (actual exposure).
    """
    if len(y_pred) == 0:
        raise ValueError("`y_pred` is empty; simulation cannot be run.")

    sim_df = df.copy().iloc[-len(y_pred):].copy()
    sim_df["predicted_return"] = np.asarray(y_pred, dtype=float)

    inferred_horizon = _resolve_horizon(sim_df, horizon=horizon, target_col=target_col)
    daily_returns = _resolve_daily_returns(sim_df, daily_return_col=daily_return_col)

    entry_signal = (sim_df["predicted_return"] > threshold).astype(int).to_numpy()

    position, executed_entries = _build_position_schedule(
        n_rows=len(sim_df),
        signals=entry_signal,
        allocation=float(allocation),
        horizon=inferred_horizon,
        execution_lag=int(execution_lag),
        allow_overlap=bool(allow_overlap),
        max_leverage=1.0,
    )

    sim_df["signal"] = entry_signal
    sim_df["executed_entry"] = executed_entries
    sim_df["position"] = position
    sim_df["daily_return"] = daily_returns.astype(float)
    sim_df["actual_return"] = sim_df["daily_return"]
    sim_df["return"] = sim_df["daily_return"]

    # Commission on entry/exit turnover.
    sim_df["turnover"] = sim_df["position"].diff().fillna(sim_df["position"]).abs()

    sim_df["gross_strategy_return"] = sim_df["position"] * sim_df["daily_return"]
    sim_df["strategy_return"] = sim_df["gross_strategy_return"] - commission * sim_df["turnover"]

    sim_df["capital"] = (1.0 + sim_df["strategy_return"]).cumprod()
    sim_df["buy_and_hold"] = (1.0 + sim_df["daily_return"]).cumprod()

    sim_df.attrs["simulation_summary"] = {
        "horizon": int(inferred_horizon),
        "execution_lag": int(execution_lag),
        "threshold": float(threshold),
        "allocation": float(allocation),
        "commission": float(commission),
        "allow_overlap": bool(allow_overlap),
        "signals_total": int(sim_df["signal"].sum()),
        "executed_entries_total": int(sim_df["executed_entry"].sum()),
    }

    return sim_df