import numpy as np
import pandas as pd

def compute_performance_metrics(returns: pd.Series, freq: int = 252) -> dict:
    returns = returns.dropna()

    if len(returns) == 0:
        return {
            "total_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0
        }

    cumulative = (1 + returns).cumprod()
    total_return = cumulative.iloc[-1] - 1

    sharpe = (
        np.sqrt(freq) * returns.mean() / returns.std()
        if returns.std() != 0 else 0.0
    )

    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    max_drawdown = drawdown.min()

    return {
        "total_return": total_return,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown
    }
