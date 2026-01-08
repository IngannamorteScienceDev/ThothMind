import pandas as pd

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor

from simulate.smart_simulator import simulate_with_allocation
from data.metrics.performance import compute_performance_metrics
from stats.regime import detect_market_regime
from stats.bootstrap import paired_bootstrap_test

from decision.decision_engine import DecisionEngine
from decision.allocation import AllocationEngine


print("\n🧪 Allocation ablation study for AAPL\n")

TICKER = "AAPL"
TRAIN_YEARS = 5
TEST_YEARS = 1
TRADING_DAYS = 252

ENTRY_THRESHOLD = 0.01
COMMISSION = 0.001

df = load_ticker_data(TICKER)
df_feat = generate_features(df)
dates = df_feat["Date"]

decision_engine = DecisionEngine()
allocation_engine = AllocationEngine()

results = []

for i in range(len(dates) - (TRAIN_YEARS + TEST_YEARS) * TRADING_DAYS):

    train_start = dates.iloc[i]
    train_end = dates.iloc[i + TRAIN_YEARS * TRADING_DAYS]
    test_start = dates.iloc[i + TRAIN_YEARS * TRADING_DAYS + 1]
    test_end = dates.iloc[i + (TRAIN_YEARS + TEST_YEARS) * TRADING_DAYS]

    train_df = df_feat[(df_feat["Date"] >= train_start) & (df_feat["Date"] <= train_end)]
    test_df = df_feat[(df_feat["Date"] >= test_start) & (df_feat["Date"] <= test_end)]

    if len(train_df) < 200 or len(test_df) < 50:
        continue

    model, _, _, y_pred = train_regressor(train_df, test_df)

    regime = detect_market_regime(train_df)

    sim_full = simulate_with_allocation(
        test_df, y_pred, allocation=1.0,
        entry_threshold=ENTRY_THRESHOLD,
        commission=COMMISSION
    )

    metrics_full = compute_performance_metrics(sim_full["capital"])

    bootstrap = paired_bootstrap_test(
        sim_full["strategy_return"],
        sim_full["buy_and_hold"].pct_change().fillna(0)
    )

    decision = decision_engine.evaluate(
        expected_return=metrics_full["total_return"],
        sharpe=metrics_full["sharpe"],
        max_drawdown=metrics_full["max_drawdown"],
        market_regime=regime,
        bootstrap_p_value=bootstrap["p_value"]
    )

    allocation_decision = allocation_engine.allocate(decision.decision)

    experiments = {
        "Full_100": 1.0,
        "Decision_based": allocation_decision.allocation,
        "Conservative_50": 0.5,
        "No_trade": 0.0
    }

    for name, alloc in experiments.items():

        sim = simulate_with_allocation(
            test_df, y_pred,
            allocation=alloc,
            entry_threshold=ENTRY_THRESHOLD,
            commission=COMMISSION
        )

        m = compute_performance_metrics(sim["capital"])

        results.append({
            "experiment": name,
            "allocation": alloc,
            "market_regime": regime,
            "total_return": m["total_return"],
            "sharpe": m["sharpe"],
            "max_drawdown": m["max_drawdown"]
        })

results_df = pd.DataFrame(results)
results_df.to_csv(
    f"reports/csv/allocation_ablation_{TICKER}.csv",
    index=False
)

print("📊 ALLOCATION ABLATION SUMMARY\n")
print(
    results_df
    .groupby("experiment")[["total_return", "sharpe", "max_drawdown"]]
    .mean()
)

print(f"\n✅ Saved to reports/csv/allocation_ablation_{TICKER}.csv")
