import os
import sys
import pandas as pd

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor
from simulate.smart_simulator import simulate_with_filters
from forecasting.metrics import evaluate_strategy


TICKERS = ["AAPL", "MSFT", "NVDA", "SPY"]

results = []

for ticker in TICKERS:
    print(f"\n🚀 Running backtest for {ticker}")

    # 1. Load data
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    # 2. Train model
    model, X_test, y_test, y_pred = train_regressor(df_feat)

    # 3. Simulate strategy
    sim_df = simulate_with_filters(
        df_feat,
        y_pred,
        entry_threshold=0.01,
        exit_threshold=0.0,
        max_holding=5,
        commission=0.001,
        use_filters=True
    )

    # 4. Evaluate
    metrics = evaluate_strategy(sim_df)

    metrics["ticker"] = ticker
    results.append(metrics)

# 5. Results table
results_df = pd.DataFrame(results)
results_df = results_df[
    ["ticker", "total_return", "sharpe", "max_drawdown"]
]

print("\n📊 MULTI-TICKER RESULTS")
print(results_df)

# 6. Save to CSV
os.makedirs("reports/csv", exist_ok=True)
results_df.to_csv("reports/csv/multiticker_results.csv", index=False)

print("\n✅ Saved to reports/csv/multiticker_results.csv")
