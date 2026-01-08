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


print("\n🚶 Walk-forward backtest for AAPL\n")

# =========================
# CONFIG
# =========================
TICKER = "AAPL"
TRAIN_YEARS = 5
TEST_YEARS = 1
TRADING_DAYS = 252

ENTRY_THRESHOLD = 0.01
COMMISSION = 0.001

# =========================
# LOAD DATA
# =========================
df = load_ticker_data(TICKER)
df_feat = generate_features(df)

dates = df_feat["Date"]

# =========================
# INIT ENGINES
# =========================
decision_engine = DecisionEngine(
    min_sharpe=0.3,
    max_drawdown_limit=-0.30,
    significance_level=0.10
)

allocation_engine = AllocationEngine()

results = []

# =========================
# WALK-FORWARD LOOP
# =========================
for i in range(len(dates) - (TRAIN_YEARS + TEST_YEARS) * TRADING_DAYS):

    train_start = dates.iloc[i]
    train_end = dates.iloc[i + TRAIN_YEARS * TRADING_DAYS]
    test_start = dates.iloc[i + TRAIN_YEARS * TRADING_DAYS + 1]
    test_end = dates.iloc[i + (TRAIN_YEARS + TEST_YEARS) * TRADING_DAYS]

    train_df = df_feat[
        (df_feat["Date"] >= train_start) &
        (df_feat["Date"] <= train_end)
    ]

    test_df = df_feat[
        (df_feat["Date"] >= test_start) &
        (df_feat["Date"] <= test_end)
    ]

    if len(train_df) < 200 or len(test_df) < 50:
        continue

    print(
        f"📅 Train: {train_start.date()} → {train_end.date()} | "
        f"Test: {test_start.date()} → {test_end.date()}"
    )

    # =========================
    # TRAIN MODEL
    # =========================
    model, _, _, y_pred = train_regressor(
        train_df=train_df,
        test_df=test_df
    )

    # =========================
    # MARKET REGIME
    # =========================
    market_regime = detect_market_regime(train_df)

    # =========================
    # BASE SIMULATION (FULL CAPITAL, FOR METRICS)
    # =========================
    sim_full = simulate_with_allocation(
        df=test_df,
        predictions=y_pred,
        allocation=1.0,
        entry_threshold=ENTRY_THRESHOLD,
        commission=COMMISSION
    )

    metrics = compute_performance_metrics(sim_full["capital"])

    # =========================
    # BOOTSTRAP SIGNIFICANCE
    # =========================
    bootstrap = paired_bootstrap_test(
        strategy_returns=sim_full["strategy_return"],
        benchmark_returns=sim_full["buy_and_hold"].pct_change().fillna(0),
        n_bootstrap=10000
    )

    # =========================
    # DECISION LAYER
    # =========================
    decision = decision_engine.evaluate(
        expected_return=metrics["total_return"],
        sharpe=metrics["sharpe"],
        max_drawdown=metrics["max_drawdown"],
        market_regime=market_regime,
        bootstrap_p_value=bootstrap["p_value"]
    )

    # =========================
    # ALLOCATION LAYER
    # =========================
    allocation_result = allocation_engine.allocate(decision.decision)

    print(
        f"🧠 Decision: {decision.decision} ({decision.confidence}) | "
        f"p-value={bootstrap['p_value']:.3f}"
    )
    print(
        f"💰 Allocation: {allocation_result.allocation * 100:.0f}% | "
        f"{allocation_result.rationale}\n"
    )

    # =========================
    # FINAL SIMULATION (WITH ALLOCATION)
    # =========================
    sim_alloc = simulate_with_allocation(
        df=test_df,
        predictions=y_pred,
        allocation=allocation_result.allocation,
        entry_threshold=ENTRY_THRESHOLD,
        commission=COMMISSION
    )

    alloc_metrics = compute_performance_metrics(sim_alloc["capital"])

    results.append({
        "train_start": train_start,
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
        "market_regime": market_regime,

        "decision": decision.decision,
        "confidence": decision.confidence,
        "allocation": allocation_result.allocation,

        "total_return": alloc_metrics["total_return"],
        "sharpe": alloc_metrics["sharpe"],
        "max_drawdown": alloc_metrics["max_drawdown"],
        "bootstrap_p_value": bootstrap["p_value"]
    })

# =========================
# SAVE RESULTS
# =========================
results_df = pd.DataFrame(results)
results_df.to_csv(
    f"reports/csv/walk_forward_{TICKER}.csv",
    index=False
)

print(f"✅ Saved to reports/csv/walk_forward_{TICKER}.csv")
