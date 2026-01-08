import pandas as pd
from datetime import timedelta

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor
from simulate.smart_simulator import simulate_with_filters
from metrics.performance import compute_performance_metrics
from regime.regime_detector import detect_market_regime
from decision.decision_engine import DecisionEngine


TICKER = "AAPL"
TRAIN_YEARS = 5
TEST_YEARS = 1


def main():
    print(f"\n🚶 Walk-forward backtest for {TICKER}\n")

    df = load_ticker_data(TICKER)
    df = generate_features(df)

    engine = DecisionEngine(
        min_sharpe=0.3,
        max_drawdown_limit=-0.30,
        significance_level=0.10
    )

    results = []

    start_date = df["Date"].min()
    end_date = df["Date"].max()

    train_start = start_date

    while True:
        train_end = train_start + pd.DateOffset(years=TRAIN_YEARS)
        test_end = train_end + pd.DateOffset(years=TEST_YEARS)

        if test_end > end_date:
            break

        train_df = df[(df["Date"] >= train_start) & (df["Date"] < train_end)]
        test_df = df[(df["Date"] >= train_end) & (df["Date"] < test_end)]

        if len(train_df) < 200 or len(test_df) < 50:
            train_start += pd.DateOffset(years=1)
            continue

        print(
            f"📅 Train: {train_start.date()} → {train_end.date()} | "
            f"Test: {train_end.date()} → {test_end.date()}"
        )

        model, _, _, y_pred = train_regressor(train_df, test_df)

        sim_df = simulate_with_filters(
            test_df,
            y_pred,
            threshold=0.01,
            use_filters=True
        )

        metrics = compute_performance_metrics(sim_df)
        regime = detect_market_regime(train_df)

        decision = engine.evaluate(
            expected_return=metrics["total_return"],
            sharpe=metrics["sharpe"],
            max_drawdown=metrics["max_drawdown"],
            market_regime=regime,
            bootstrap_p_value=None
        )

        print(
            f"🧠 Decision: {decision.decision} "
            f"(confidence: {decision.confidence})"
        )
        print(f"📌 Rationale: {decision.rationale}\n")

        results.append({
            "train_start": train_start.date(),
            "train_end": train_end.date(),
            "test_start": train_end.date(),
            "test_end": test_end.date(),
            "market_regime": regime,
            "total_return": metrics["total_return"],
            "sharpe": metrics["sharpe"],
            "max_drawdown": metrics["max_drawdown"],
            "decision": decision.decision,
            "confidence": decision.confidence
        })

        train_start += pd.DateOffset(years=1)

    results_df = pd.DataFrame(results)
    results_df.to_csv(
        f"reports/csv/walk_forward_{TICKER}_with_decisions.csv",
        index=False
    )

    print("📊 WALK-FORWARD WITH DECISION LAYER (head)")
    print(results_df.head())
    print("\n✅ Saved to reports/csv/walk_forward_AAPL_with_decisions.csv")


if __name__ == "__main__":
    main()
