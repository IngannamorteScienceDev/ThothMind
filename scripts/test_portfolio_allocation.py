import pandas as pd

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor

from simulate.smart_simulator import simulate_with_allocation
from stats.bootstrap import paired_bootstrap_test
from stats.regime import detect_market_regime

from decision.decision_engine import DecisionEngine
from decision.allocation import AllocationEngine

from portfolio.portfolio_backtester import (
    compute_inverse_vol_weights,
    backtest_portfolio
)


print("\n📦 Portfolio allocation walk-forward (research-grade)\n")

# =========================
# CONFIG
# =========================
TICKERS = ["AAPL", "MSFT", "NVDA", "SPY"]
TRAIN_YEARS = 5
TEST_YEARS = 1
TRADING_DAYS = 252

ENTRY_THRESHOLD = 0.01
COMMISSION = 0.001

# portfolio policy
VOL_LOOKBACK = 20
MAX_WEIGHT = 0.5

# =========================
# ENGINES
# =========================
decision_engine = DecisionEngine(min_sharpe=0.3, max_drawdown_limit=-0.30, significance_level=0.10)
allocation_engine = AllocationEngine()

# =========================
# LOAD ALL DATA
# =========================
data = {}
for t in TICKERS:
    df = load_ticker_data(t)
    data[t] = generate_features(df)

# choose a common date index (intersection) for stability
common_dates = set(data[TICKERS[0]]["Date"])
for t in TICKERS[1:]:
    common_dates = common_dates.intersection(set(data[t]["Date"]))
common_dates = sorted(list(common_dates))

if len(common_dates) < (TRAIN_YEARS + TEST_YEARS) * TRADING_DAYS:
    raise RuntimeError("Not enough common dates across tickers for portfolio walk-forward.")

common_dates = pd.Series(common_dates)

portfolio_results = []
window_weights = []

# =========================
# WALK-FORWARD WINDOWS
# =========================
for i in range(len(common_dates) - (TRAIN_YEARS + TEST_YEARS) * TRADING_DAYS):

    train_start = common_dates.iloc[i]
    train_end = common_dates.iloc[i + TRAIN_YEARS * TRADING_DAYS]
    test_start = common_dates.iloc[i + TRAIN_YEARS * TRADING_DAYS + 1]
    test_end = common_dates.iloc[i + (TRAIN_YEARS + TEST_YEARS) * TRADING_DAYS]

    print(f"📅 Window: Train {train_start.date()} → {train_end.date()} | Test {test_start.date()} → {test_end.date()}")

    per_ticker_returns = {}
    alloc_map = {}
    decision_map = {}
    pval_map = {}

    # ---- Build each ticker strategy returns for this window
    for t in TICKERS:
        df_feat = data[t]
        train_df = df_feat[(df_feat["Date"] >= train_start) & (df_feat["Date"] <= train_end)]
        test_df = df_feat[(df_feat["Date"] >= test_start) & (df_feat["Date"] <= test_end)]

        if len(train_df) < 200 or len(test_df) < 50:
            alloc_map[t] = 0.0
            per_ticker_returns[t] = pd.Series([0.0] * len(test_df), index=test_df["Date"].values)
            decision_map[t] = "DISABLE"
            pval_map[t] = None
            continue

        # model
        _, _, _, y_pred = train_regressor(train_df=train_df, test_df=test_df)

        # base sim with full allocation for bootstrap/metrics inputs
        sim_full = simulate_with_allocation(
            df=test_df,
            predictions=y_pred,
            allocation=1.0,
            entry_threshold=ENTRY_THRESHOLD,
            commission=COMMISSION
        )

        # regime and bootstrap
        regime = detect_market_regime(train_df)

        boot = paired_bootstrap_test(
            strategy_returns=sim_full["strategy_return"],
            benchmark_returns=sim_full["buy_and_hold"].pct_change().fillna(0),
            n_bootstrap=5000
        )

        # We keep decision inputs minimal here: bootstrap + regime only influences decision;
        # you can optionally pass per-ticker metrics later if you want tighter control.
        # For now, DecisionEngine remains consistent with your single-ticker pipeline.
        # We'll compute approximate "expected_return" etc from sim_full capital:
        from metrics.performance import compute_performance_metrics
        m = compute_performance_metrics(sim_full["capital"])

        decision = decision_engine.evaluate(
            expected_return=m["total_return"],
            sharpe=m["sharpe"],
            max_drawdown=m["max_drawdown"],
            market_regime=regime,
            bootstrap_p_value=boot["p_value"]
        )

        alloc = allocation_engine.allocate(decision.decision).allocation

        alloc_map[t] = alloc
        decision_map[t] = decision.decision
        pval_map[t] = boot["p_value"]

        # final returns series (strategy returns scaled by allocation will be applied at portfolio level via weights,
        # so here we store raw strategy returns)
        per_ticker_returns[t] = pd.Series(sim_full["strategy_return"].values, index=sim_full["Date"].values)

    # ---- Align returns into DataFrame by Date
    returns_df = pd.DataFrame(per_ticker_returns).fillna(0.0)
    returns_df.index = pd.to_datetime(returns_df.index)

    # ---- Compute portfolio weights (inverse-vol scaled by allocation)
    weights = compute_inverse_vol_weights(
        returns_df=returns_df,
        alloc_map=alloc_map,
        vol_lookback=VOL_LOOKBACK,
        max_weight=MAX_WEIGHT
    )

    window_weights.append({
        "train_start": train_start,
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
        **{f"w_{k}": v for k, v in weights.items()},
        **{f"alloc_{t}": alloc_map.get(t, 0.0) for t in TICKERS},
        **{f"dec_{t}": decision_map.get(t, "") for t in TICKERS},
        **{f"p_{t}": pval_map.get(t, None) for t in TICKERS},
    })

    # ---- Backtest portfolio
    port = backtest_portfolio(returns_df, weights)
    m_port = port.attrs["metrics"]

    portfolio_results.append({
        "train_start": train_start,
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
        "total_return": m_port["total_return"],
        "sharpe": m_port["sharpe"],
        "max_drawdown": m_port["max_drawdown"],
        "cash_weight": weights.get("CASH", 0.0),
        "active_assets": sum(1 for t in TICKERS if weights.get(t, 0.0) > 0)
    })

# =========================
# SAVE
# =========================
results_df = pd.DataFrame(portfolio_results)
weights_df = pd.DataFrame(window_weights)

results_df.to_csv("reports/csv/portfolio_walk_forward_results.csv", index=False)
weights_df.to_csv("reports/csv/portfolio_walk_forward_weights.csv", index=False)

print("\n✅ Saved:")
print("- reports/csv/portfolio_walk_forward_results.csv")
print("- reports/csv/portfolio_walk_forward_weights.csv")

print("\n📊 PORTFOLIO SUMMARY (mean over windows)")
print(results_df[["total_return", "sharpe", "max_drawdown", "cash_weight", "active_assets"]].mean())
