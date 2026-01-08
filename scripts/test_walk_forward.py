import pandas as pd
from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor
from simulate.smart_simulator import simulate_with_filters
from metrics.performance import compute_performance_metrics
from stats.regime import detect_market_regime
from stats.bootstrap import paired_bootstrap_test
from decision.decision_engine import DecisionEngine

print("\n🚶 Walk-forward backtest for AAPL\n")

ticker = "AAPL"
df = load_ticker_data(ticker)
df_feat = generate_features(df)

engine = DecisionEngine()

train_years = 5
test_years = 1

results = []

dates = df_feat["Date"]

for i in range(len(dates) - (train_years + test_years) * 252):
    train_start = dates.iloc[i]
    train_end = dates.iloc[i + train_years * 252]
    test_start = dates.iloc[i + train_years * 252 + 1]
    test_end = dates.iloc[i + (train_years + test_years) * 252]

    train_df = df_feat[(df_feat["Date"] >= train_start) & (df_feat["Date"] <= train_end)]
    test_df = df_feat[(df_feat["Date"] >= test_start) & (df_feat["Date"] <= test_end)]

    if len(train_df) < 200 or len(test_df) < 50:
        continue

    print(f"📅 Train: {train_start.date()} → {train_end.date()} | Test: {test_start.date()} → {test_end.date()}")

    model, _, _, y_pred = train_regressor(train_df, test_df)

    sim_df = simulate_with_filters(
        test_df,
        y_pred,
        entry_threshold=0.01,
        commission=0.001
    )

    metrics = compute_performance_metrics(sim_df["capital"])

    regime = detect_market_regime(train_df)

    bootstrap = paired_bootstrap_test(
        sim_df["strategy_return"],
        sim_df["buy_and_hold"].pct_change().fillna(0)
    )

    decision = engine.evaluate(
        expected_return=metrics["total_return"],
        sharpe=metrics["sharpe"],
        max_drawdown=metrics["max_drawdown"],
        market_regime=regime,
        bootstrap_p_value=bootstrap["p_value"]
    )

    print(f"🧠 Decision: {decision.decision} ({decision.confidence})")
    print(f"📌 Rationale: {decision.rationale}\n")

    results.append({
        "train_start": train_start,
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
        "market_regime": regime,
        "total_return": metrics["total_return"],
        "sharpe": metrics["sharpe"],
        "max_drawdown": metrics["max_drawdown"],
        "bootstrap_p_value": bootstrap["p_value"],
        "decision": decision.decision,
        "confidence": decision.confidence
    })

results_df = pd.DataFrame(results)
results_df.to_csv("reports/csv/walk_forward_AAPL.csv", index=False)

print("✅ Saved to reports/csv/walk_forward_AAPL.csv")
