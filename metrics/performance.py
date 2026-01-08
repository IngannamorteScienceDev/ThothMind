import numpy as np
import pandas as pd


def compute_performance_metrics(returns: pd.Series) -> dict:
    returns = returns.dropna()

    if len(returns) == 0:
        return {
            "total_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0
        }

    cumulative = (1 + returns).cumprod()
    total_return = cumulative.iloc[-1] - 1

    mean = returns.mean()
    std = returns.std()

    sharpe = mean / std * np.sqrt(252 / 5) if std > 0 else 0.0

    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    max_drawdown = drawdown.min()

    return {
        "total_return": float(total_return),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_drawdown)
    }
