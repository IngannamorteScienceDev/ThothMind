import os
import sys
import pandas as pd
import numpy as np

# Добавляем корень проекта в PYTHONPATH
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor
from simulate.smart_simulator import simulate_with_filters
from forecasting.metrics import evaluate_strategy


TICKER = "AAPL"

EXPERIMENTS = [
    {"name": "Buy&Hold", "mode": "buy_and_hold"},
    {"name": "Random", "mode": "random"},
    {"name": "ML_only", "mode": "ml", "use_filters": False},
    {"name": "ML+Filters", "mode": "ml", "use_filters": True},
]

results = []

print(f"\n📊 Running ablation study for {TICKER}")

# 1. Load and prepare data
df = load_ticker_data(TICKER)
df_feat = generate_features(df)

# 2. Train ML model once
model, X_test, y_test, y_pred = train_regressor(df_feat)

for exp in EXPERIMENTS:
    print(f"\n🧪 Experiment: {exp['name']}")

    # =========================
    # BUY & HOLD (canonical)
    # =========================
    if exp["mode"] == "buy_and_hold":
        sim_df = simulate_with_filters(
            df_feat,
            y_pred,
            force_buy_and_hold=True
        )

    # =========================
    # RANDOM BASELINE
    # =========================
    elif exp["mode"] == "random":
        rng = np.random.default_rng(seed=42)
        random_signal = rng.normal(0, 0.01, size=len(y_pred))

        sim_df = simulate_with_filters(
            df_feat,
            random_signal,
            entry_threshold=0.01,
            exit_threshold=0.0,
            max_holding=5,
            commission=0.001,
            use_filters=False
        )

    # =========================
    # ML-BASED STRATEGIES
    # =========================
    elif exp["mode"] == "ml":
        sim_df = simulate_with_filters(
            df_feat,
            y_pred,
            entry_threshold=0.01,
            exit_threshold=0.0,
            max_holding=5,
            commission=0.001,
            use_filters=exp.get("use_filters", False)
        )

    else:
        raise ValueError(f"Unknown experiment mode: {exp['mode']}")

    # 3. Evaluate strategy
    metrics = evaluate_strategy(sim_df)
    metrics["experiment"] = exp["name"]

    results.append(metrics)

# 4. Collect results
results_df = pd.DataFrame(results)
results_df = results_df[
    ["experiment", "total_return", "sharpe", "max_drawdown"]
]

print("\n📊 ABLATION STUDY RESULTS")
print(results_df)

# 5. Save results
os.makedirs("reports/csv", exist_ok=True)
out_path = f"reports/csv/ablation_results_{TICKER}.csv"
results_df.to_csv(out_path, index=False)

print(f"\n✅ Saved to {out_path}")
