import pandas as pd

path = "reports/csv/walk_forward_AAPL.csv"

df = pd.read_csv(path)

print("\n📊 REGIME PERFORMANCE SUMMARY\n")

summary = (
    df.groupby("market_regime")
    .agg(
        mean_return=("total_return", "mean"),
        median_return=("total_return", "median"),
        sharpe_mean=("sharpe", "mean"),
        drawdown_mean=("max_drawdown", "mean"),
        n_windows=("total_return", "count")
    )
    .sort_values("mean_return", ascending=False)
)

print(summary)

out_path = "reports/csv/regime_analysis_AAPL.csv"
summary.to_csv(out_path)

print(f"\n✅ Saved to {out_path}")
