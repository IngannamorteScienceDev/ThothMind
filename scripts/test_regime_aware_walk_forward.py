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
from analysis.regimes import assign_market_regime_full


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

MIN_REGIME_TRAIN_SAMPLES = 400  # safeguard: avoid training regime model on tiny subsets


def dominant_regime(window_df: pd.DataFrame) -> str:
    return window_df["market_regime"].mode().iloc[0]


def run_one_model(model_name: str, train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    model = train_xgb_on_window(train_df)
    y_pred = predict_on_window(model, test_df)

    sim_df = simulate_with_filters(
        test_df,
        y_pred,
        entry_threshold=ENTRY_THRESHOLD,
        exit_threshold=EXIT_THRESHOLD,
        max_holding=MAX_HOLDING,
        commission=COMMISSION,
        use_filters=USE_FILTERS
    )

    metrics = evaluate_strategy(sim_df)
    metrics["model"] = model_name
    return metrics


def main():
    print(f"\n🧠 Regime-aware walk-forward for {TICKER}")

    # Load data
    df = load_ticker_data(TICKER)
    df_feat = generate_features(df)

    # IMPORTANT: label regimes ON FULL SERIES (no within-window leakage)
    df_feat = assign_market_regime_full(df_feat)

    results = []
    start = 0
    step = TEST_WINDOW

    while start + TRAIN_WINDOW + TEST_WINDOW <= len(df_feat):
        train_start = start
        train_end = start + TRAIN_WINDOW
        test_end = train_end + TEST_WINDOW

        train_df = df_feat.iloc[train_start:train_end].copy()
        test_df = df_feat.iloc[train_end:test_end].copy()

        dom = dominant_regime(test_df)

        print(
            f"\n📅 Train: {train_df['Date'].iloc[0].date()} → {train_df['Date'].iloc[-1].date()} | "
            f"Test: {test_df['Date'].iloc[0].date()} → {test_df['Date'].iloc[-1].date()} | "
            f"Regime(test): {dom}"
        )

        # 1) Global model
        m_global = run_one_model("global", train_df, test_df)

        # 2) Regime-aware model (train only on same regime as test window)
        regime_train = train_df[train_df["market_regime"] == dom]
        if len(regime_train) < MIN_REGIME_TRAIN_SAMPLES:
            # fallback: too few samples -> use global
            m_regime = dict(m_global)
            m_regime["model"] = "regime_fallback_global"
            m_regime["regime_train_samples"] = len(regime_train)
        else:
            m_regime = run_one_model("regime_aware", regime_train, test_df)
            m_regime["regime_train_samples"] = len(regime_train)

        # enrich metadata
        for m in (m_global, m_regime):
            m.update({
                "ticker": TICKER,
                "train_start": train_df["Date"].iloc[0],
                "train_end": train_df["Date"].iloc[-1],
                "test_start": test_df["Date"].iloc[0],
                "test_end": test_df["Date"].iloc[-1],
                "market_regime": dom
            })
            results.append(m)

        start += step

    results_df = pd.DataFrame(results)

    print("\n📊 REGIME-AWARE WALK-FORWARD RESULTS (head)")
    print(results_df[["model", "market_regime", "total_return", "sharpe", "max_drawdown"]].head(12))

    os.makedirs("reports/csv", exist_ok=True)
    out_path = f"reports/csv/regime_aware_walk_forward_{TICKER}.csv"
    results_df.to_csv(out_path, index=False)

    print(f"\n✅ Saved to {out_path}")

    # quick summary
    summary = (
        results_df
        .groupby(["model"])
        .agg(
            mean_return=("total_return", "mean"),
            median_return=("total_return", "median"),
            sharpe_mean=("sharpe", "mean"),
            drawdown_mean=("max_drawdown", "mean"),
            n=("total_return", "count")
        )
        .sort_values("mean_return", ascending=False)
    )

    print("\n📌 OVERALL SUMMARY")
    print(summary)

    summary_path = f"reports/csv/regime_aware_summary_{TICKER}.csv"
    summary.to_csv(summary_path)
    print(f"\n✅ Saved to {summary_path}")


if __name__ == "__main__":
    main()
