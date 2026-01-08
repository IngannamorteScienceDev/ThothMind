import pandas as pd
import numpy as np


def simulate_with_filters(
    df: pd.DataFrame,
    y_pred: np.ndarray,
    entry_threshold: float = 0.01,
    exit_threshold: float = 0.0,
    max_holding: int = 5,
    commission: float = 0.001,
    use_filters: bool = True,
    force_buy_and_hold: bool = False
):
    """
    Event-driven trading simulator.
    """

    df = df.copy()
    df = df.iloc[-len(y_pred):].reset_index(drop=True)

    # === Market return (t -> t+1) ===
    df["market_return"] = df["return_1d"].shift(-1)

    # ✅ CANONICAL BUY & HOLD (НЕ зависит от сигналов)
    df["buy_and_hold"] = (1 + df["market_return"]).cumprod()

    # === Если нужен чистый Buy & Hold — сразу возвращаем ===
    if force_buy_and_hold:
        df = df.iloc[:-1].reset_index(drop=True)
        df["strategy_return"] = df["market_return"]
        df["capital"] = df["buy_and_hold"]
        df["position"] = 1
        return df

    # === ML-driven strategy ===
    df["predicted_return"] = y_pred

    position = 0
    holding_days = 0
    cooldown = 0

    strategy_returns = []
    positions = []

    for i in range(len(df)):
        ret = 0.0

        if cooldown > 0:
            cooldown -= 1

        trend_ok = True
        if use_filters:
            trend_ok = (
                df.loc[i, "SMA_5"] > df.loc[i, "SMA_20"] >
                df.loc[i, "SMA_50"]
            )

        # ENTRY
        if (
            position == 0 and
            cooldown == 0 and
            df.loc[i, "predicted_return"] > entry_threshold and
            trend_ok
        ):
            position = 1
            holding_days = 0
            ret -= commission

        # HOLD / EXIT
        elif position == 1:
            holding_days += 1
            ret += df.loc[i, "market_return"]

            if (
                holding_days >= max_holding or
                df.loc[i, "predicted_return"] < exit_threshold
            ):
                position = 0
                cooldown = 1
                ret -= commission

        strategy_returns.append(ret)
        positions.append(position)

    df["strategy_return"] = strategy_returns
    df["position"] = positions
    df["capital"] = (1 + df["strategy_return"]).cumprod()

    # ❗ убираем последнюю строку (нет future return)
    df = df.iloc[:-1].reset_index(drop=True)

    return df
