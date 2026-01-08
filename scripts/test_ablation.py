import os
import sys
import pandas as pd
import numpy as np

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor
from simulate.smart_simulator import simulate_with_filters
from forecasting.metrics import evaluate_strategy


TICKER = "AAPL"

experiments = [
    {"name": "Buy&Hold", "use_ml": False, "use_filters": False},
    {"name": "Random", "use_ml": False, "use_filters": False, "random": True},
    {"name": "ML_only", "use_ml": True, "use_filters": False},
    {"name": "ML+Filters", "use_ml": True, "use_filters": True},
]

results = []

# Load data once
df = load_ticker_data(TICKER)
df_feat = generate_features(df)

# Train ML model once
model, X_test, y_test, y_pred = train_regressor(df_feat)

for exp in experiments:
    print(f"\n🧪 Running experiment: {exp['name']}")

    if exp.get("random", False):
        y_signal = np.random.normal(0, 0.01, size=len(y_pred))
    elif exp["use_ml"]:
        y_signal = y_pred
    else:
        y_signal = np.zeros(len(y_pred))  # no trades

    sim_df = simulate_with_filters(
        df_feat,
        y_signal,
        entry_threshold=0.01,
        exit_threshold=0.0,
        max_holding=5,
        commission=0.001,
        use_filters=exp.get("use_filters", False)
    )

    metrics = evaluate_strategy(sim_df)
    metrics["experiment"] = exp["name"]
    results.append(metrics)

results_df = pd.DataFrame(results)
results_df = results_df[
    ["experiment", "total_return", "sharpe", "max_drawdown"]
]

print("\n📊 ABLATION STUDY RESULTS")
print(results_df)

os.makedirs("reports/csv", exist_ok=True)
results_df.to_csv("reports/csv/ablation_results_AAPL.csv", index=False)

print("\n✅ Saved to reports/csv/ablation_results_AAPL.csv")
