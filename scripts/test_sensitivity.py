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


TICKER = "AAPL"

ENTRY_THRESHOLDS = [0.005, 0.01, 0.02]
COMMISSIONS = [0.001, 0.002]

results = []

print(f"\n📊 Running sensitivity analysis for {TICKER}")

# Load & prepare data
df = load_ticker_data(TICKER)
df_feat = generate_features(df)

# Train model once
model, X_test, y_test, y_pred = train_regressor(df_feat)

for entry in ENTRY_THRESHOLDS:
    for commission in COMMISSIONS:
        print(f"\n🔧 entry_threshold={entry}, commission={commission}")

        sim_df = simulate_with_filters(
            df_feat,
            y_pred,
            entry_threshold=entry,
            exit_threshold=0.0,
            max_holding=5,
            commission=commission,
            use_filters=True
        )

        metrics = evaluate_strategy(sim_df)
        metrics["entry_threshold"] = entry
        metrics["commission"] = commission

        results.append(metrics)

results_df = pd.DataFrame(results)
results_df = results_df[
    ["entry_threshold", "commission", "total_return", "sharpe", "max_drawdown"]
]

print("\n📊 SENSITIVITY ANALYSIS RESULTS")
print(results_df)

# Save
os.makedirs("reports/csv", exist_ok=True)
out_path = f"reports/csv/sensitivity_results_{TICKER}.csv"
results_df.to_csv(out_path, index=False)

print(f"\n✅ Saved to {out_path}")
