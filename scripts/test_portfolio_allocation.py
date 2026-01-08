import os
import sys
import numpy as np
import pandas as pd

# ===============================
# 🔧 PROJECT ROOT PATCH
# ===============================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from decision.allocation import allocate_capital
from data.metrics.performance import compute_performance_metrics

# ===============================
# CONFIG
# ===============================
TICKERS = ["AAPL", "MSFT", "NVDA", "SPY"]
ALLOCATION_LEVELS = [0.0, 0.5, 1.0]
OUTPUT_PATH = "reports/csv/portfolio_allocation_results.csv"


def run_allocation_backtest():
    print("\n📊 Portfolio Allocation Backtest")

    records = []

    for ticker in TICKERS:
        print(f"\n🚀 Processing {ticker}")

        df = load_ticker_data(ticker)
        df_feat = generate_features(df)

        # Buy & Hold baseline
        returns = df_feat["target_return_5d"]
        bh_metrics = compute_performance_metrics(returns)

        for alloc in ALLOCATION_LEVELS:
            allocated_returns = allocate_capital(
                returns=returns,
                allocation=alloc
            )

            metrics = compute_performance_metrics(allocated_returns)

            records.append({
                "ticker": ticker,
                "allocation": alloc,
                "total_return": metrics["total_return"],
                "sharpe": metrics["sharpe"],
                "max_drawdown": metrics["max_drawdown"],
                "benchmark_bh_return": bh_metrics["total_return"]
            })

    result_df = pd.DataFrame(records)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    result_df.to_csv(OUTPUT_PATH, index=False)

    print("\n✅ Saved:")
    print(f"   {OUTPUT_PATH}")


if __name__ == "__main__":
    run_allocation_backtest()
