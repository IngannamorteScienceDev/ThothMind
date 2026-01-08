import os
import sys
import pandas as pd

# Добавляем корень проекта
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_research import (
    train_xgb_on_window,
    predict_on_window
)
from simulate.smart_simulator import simulate_with_filters
from forecasting.metrics import evaluate_strategy
from analysis.regimes import assign_market_regime


# =======================
# CONFIG
# =======================

TICKER = "AAPL"

TRAIN_YEARS = 5
TEST_YEARS = 1
TRADING_DAYS = 252

TRAIN_WINDOW = TRAIN_YEARS * TRADING_DAYS
TEST_WINDOW = TEST_YEARS * TRADING_DAYS

ENTRY_THRESHOLD = 0.01
EXIT_THRESHOLD = 0.0
MAX_HOLDING = 5
COMMISSION = 0.001
USE_FILTERS = True


# =======================
# LOAD & PREP DATA
# =======================

print(f"\n🚶 Walk-forward backtest for {TICKER}")

df = load_ticker_data(TICKER)
df_feat = generate_features(df)

results = []
start = 0
step = TEST_WINDOW


# =======================
# WALK-FORWARD LOOP
# =======================

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

    # =======================
    # REGIME LABELING (TEST ONLY)
    # =======================

    test_df = assign_market_regime(test_df)

    dominant_regime = test_df["market_regime"].mode()[0]

    # =======================
    # TRAIN & PREDICT
    # =======================

    model = train_xgb_on_window(train_df)
    y_pred = predict_on_window(model, test_df)

    # =======================
    # STRATEGY SIMULATION
    # =======================

    sim_df = simulate_with_filters(
        test_df,
        y_pred,
        entry_threshold=ENTRY_THRESHOLD,
        exit_threshold=EXIT_THRESHOLD,
        max_holding=MAX_HOLDING,
        commission=COMMISSION,
        use_filters=USE_FILTERS
    )

    # =======================
    # METRICS
    # =======================

    metrics = evaluate_strategy(sim_df)

    metrics.update({
        "ticker": TICKER,
        "train_start": train_df["Date"].iloc[0],
        "train_end": train_df["Date"].iloc[-1],
        "test_start": test_df["Date"].iloc[0],
        "test_end": test_df["Date"].iloc[-1],
        "market_regime": dominant_regime
    })

    results.append(metrics)

    start += step


# =======================
# SAVE RESULTS
# =======================

results_df = pd.DataFrame(results)

print("\n📊 WALK-FORWARD RESULTS (per window)")
print(
    results_df[
        ["market_regime", "total_return", "sharpe", "max_drawdown"]
    ]
)

os.makedirs("reports/csv", exist_ok=True)

out_path = f"reports/csv/walk_forward_{TICKER}.csv"
results_df.to_csv(out_path, index=False)

print(f"\n✅ Saved to {out_path}")
