import pandas as pd
import numpy as np


def simulate_with_filters(
    df: pd.DataFrame,
    y_pred: np.ndarray,
    entry_threshold: float = 0.01,
    exit_threshold: float = 0.0,
    max_holding: int = 5,
    commission: float = 0.001,
    use_filters: bool = True
):
    """
    Event-driven trading simulator with:
    - next-day execution (no look-ahead bias)
    - position holding logic
    - commission on entry & exit
    - trend filter (optional)

    Parameters
    ----------
    df : DataFrame
        Feature dataframe (must include return_1d, SMA_5/20/50)
    y_pred : np.ndarray
        Predicted future returns from regression model
    entry_threshold : float
        Minimum predicted return to open position
    exit_threshold : float
        Exit if predicted return falls below this level
    max_holding : int
        Maximum holding period (days)
    commission : float
        Commission per transaction (fraction)
    use_filters : bool
        Whether to apply trend filters

    Returns
    -------
    DataFrame with strategy results
    """

    df = df.copy()
    df = df.iloc[-len(y_pred):].reset_index(drop=True)

    # === Predicted return from model ===
    df["predicted_return"] = y_pred

    # === Realized market return (t -> t+1) ===
    df["market_return"] = df["return_1d"].shift(-1)

    position = 0          # 0 = flat, 1 = long
    holding_days = 0
    cooldown = 0

    strategy_returns = []
    positions = []

    for i in range(len(df)):
        ret = 0.0

        # Cooldown after exit
        if cooldown > 0:
            cooldown -= 1

        # Trend filter
        trend_ok = True
        if use_filters:
            trend_ok = (
                df.loc[i, "SMA_5"] > df.loc[i, "SMA_20"] >
                df.loc[i, "SMA_50"]
            )

        # =========================
        # ENTRY
        # =========================
        if (
            position == 0 and
            cooldown == 0 and
            df.loc[i, "predicted_return"] > entry_threshold and
            trend_ok
        ):
            position = 1
            holding_days = 0
            ret -= commission   # entry commission

        # =========================
        # EXIT / HOLD
        # =========================
        elif position == 1:
            holding_days += 1
            ret += df.loc[i, "market_return"]

            if (
                holding_days >= max_holding or
                df.loc[i, "predicted_return"] < exit_threshold
            ):
                position = 0
                cooldown = 1
                ret -= commission   # exit commission

        strategy_returns.append(ret)
        positions.append(position)

    df["strategy_return"] = strategy_returns
    df["position"] = positions

    # === Capital curves ===
    df["capital"] = (1 + df["strategy_return"]).cumprod()
    df["buy_and_hold"] = (1 + df["market_return"]).cumprod()

    # === Remove last row (no future return available) ===
    df = df.iloc[:-1].reset_index(drop=True)

    return df
