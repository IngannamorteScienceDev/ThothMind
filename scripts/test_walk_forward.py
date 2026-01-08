import os
import sys
import pandas as pd

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_research import train_xgb_on_window, predict_on_window
from simulate.smart_simulator import simulate_with_filters
from forecasting.metrics import evaluate_strategy


TICKER = "AAPL"

TRAIN_YEARS = 5
TEST_YEARS = 1
TRADING_DAYS = 252

TRAIN_WINDOW = TRAIN_YEARS * TRADING_DAYS
TEST_WINDOW = TEST_YEARS * TRADING_DAYS


print(f"\n🚶 Walk-forward backtest for {TICKER}")

df = load_ticker_data(TICKER)
df_feat = generate_features(df)

results = []
start = 0
step = TEST_WINDOW

while start + TRAIN_WINDOW + TEST_WINDOW <= len(df_feat):
    train_start = start
    train_end = start + TRAIN_WINDOW
    test_end = train_end + TEST_WINDOW

    train_df = df_feat.iloc[train_start:train_end]
    test_df = df_feat.iloc[train_end:test_end]

    print(
        f"\n📅 Train: {train_df['Date'].iloc[0].date()} "
        f"→ {train_df['Date'].iloc[-1].date()} | "
        f"Test: {test_df['Date'].iloc[0].date()} "
        f"→ {test_df['Date'].iloc[-1].date()}"
    )

    # 🔬 Research-grade training
    model = train_xgb_on_window(train_df)
    y_pred = predict_on_window(model, test_df)

    # 🎯 Strategy simulation on test window only
    sim_df = simulate_with_filters(
        test_df,
        y_pred,
        entry_threshold=0.01,
        exit_threshold=0.0,
        max_holding=5,
        commission=0.001,
        use_filters=True
    )

    metrics = evaluate_strategy(sim_df)
    metrics["train_start"] = train_df["Date"].iloc[0]
    metrics["test_start"] = test_df["Date"].iloc[0]

    results.append(metrics)
    start += step


results_df = pd.DataFrame(results)

print("\n📊 WALK-FORWARD RESULTS")
print(results_df[["total_return", "sharpe", "max_drawdown"]])

os.makedirs("reports/csv", exist_ok=True)
out_path = f"reports/csv/walk_forward_{TICKER}.csv"
results_df.to_csv(out_path, index=False)

print(f"\n✅ Saved to {out_path}")
