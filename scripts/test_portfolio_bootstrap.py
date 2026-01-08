import os
import sys
import numpy as np
import pandas as pd

# add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from metrics.performance import compute_performance_metrics


def paired_bootstrap_metric(
    strategy_vals: np.ndarray,
    benchmark_vals: np.ndarray,
    n_bootstrap: int = 20000,
    seed: int = 42,
    ci: float = 0.95
) -> dict:
    """
    Paired bootstrap on per-window metric values.
    H0: E[strategy - benchmark] <= 0  (one-sided)
    """
    rng = np.random.default_rng(seed)

    strategy_vals = np.asarray(strategy_vals, dtype=float)
    benchmark_vals = np.asarray(benchmark_vals, dtype=float)

    mask = ~np.isnan(strategy_vals) & ~np.isnan(benchmark_vals)
    strategy_vals = strategy_vals[mask]
    benchmark_vals = benchmark_vals[mask]

    diff = strategy_vals - benchmark_vals
    n = len(diff)

    if n < 5:
        return {
            "n": n,
            "observed_mean_delta": float(np.mean(diff)) if n > 0 else np.nan,
            "observed_median_delta": float(np.median(diff)) if n > 0 else np.nan,
            "win_rate": float(np.mean(diff > 0)) if n > 0 else np.nan,
            "ci_low": np.nan,
            "ci_high": np.nan,
            "p_value_one_sided": np.nan,
        }

    boot_means = np.empty(n_bootstrap, dtype=float)
    for b in range(n_bootstrap):
        idx = rng.integers(0, n, n)
        boot_means[b] = diff[idx].mean()

    alpha = 1.0 - ci
    lo = float(np.quantile(boot_means, alpha / 2))
    hi = float(np.quantile(boot_means, 1 - alpha / 2))

    # one-sided p-value: P(mean_delta <= 0)
    p_value = float(np.mean(boot_means <= 0))

    return {
        "n": int(n),
        "observed_mean_delta": float(diff.mean()),
        "observed_median_delta": float(np.median(diff)),
        "win_rate": float(np.mean(diff > 0)),
        "ci_low": lo,
        "ci_high": hi,
        "p_value_one_sided": p_value,
    }


def compute_spy_bh_metrics_for_windows(windows_csv: str) -> pd.DataFrame:
    """
    For each walk-forward window in portfolio results, compute SPY buy&hold metrics
    over the SAME test period.
    """
    windows = pd.read_csv(windows_csv)
    for col in ["test_start", "test_end"]:
        windows[col] = pd.to_datetime(windows[col])

    spy = load_ticker_data("SPY")
    spy_feat = generate_features(spy)
    spy_feat["Date"] = pd.to_datetime(spy_feat["Date"])

    out = []
    for _, row in windows.iterrows():
        test_df = spy_feat[(spy_feat["Date"] >= row["test_start"]) & (spy_feat["Date"] <= row["test_end"])].copy()
        if len(test_df) < 10:
            out.append({
                "test_start": row["test_start"],
                "test_end": row["test_end"],
                "bh_total_return": np.nan,
                "bh_sharpe": np.nan,
                "bh_max_drawdown": np.nan,
            })
            continue

        # Buy&Hold capital curve
        r = test_df["target_return_5d"].values  # consistent with your simulator horizon
        capital = (1.0 + r).cumprod()
        m = compute_performance_metrics(pd.Series(capital))

        out.append({
            "test_start": row["test_start"],
            "test_end": row["test_end"],
            "bh_total_return": m["total_return"],
            "bh_sharpe": m["sharpe"],
            "bh_max_drawdown": m["max_drawdown"],
        })

    return pd.DataFrame(out)


def main():
    print("\n🧪 Portfolio bootstrap significance vs SPY Buy&Hold")

    results_path = "reports/csv/portfolio_walk_forward_results.csv"
    if not os.path.exists(results_path):
        raise FileNotFoundError(
            "Missing reports/csv/portfolio_walk_forward_results.csv. "
            "Run scripts/test_portfolio_allocation.py first."
        )

    port = pd.read_csv(results_path)
    for col in ["test_start", "test_end"]:
        port[col] = pd.to_datetime(port[col])

    # compute benchmark metrics per same windows
    bh_df = compute_spy_bh_metrics_for_windows(results_path)

    merged = port.merge(bh_df, on=["test_start", "test_end"], how="left")

    # Save paired window table
    os.makedirs("reports/csv", exist_ok=True)
    paired_path = "reports/csv/portfolio_bootstrap_paired_windows.csv"
    merged.to_csv(paired_path, index=False)

    print(f"Paired windows used: {merged[['total_return','bh_total_return']].dropna().shape[0]}")
    print(f"Bootstrap samples: 20000\n")

    # Bootstrap on per-window metrics (paired)
    res_return = paired_bootstrap_metric(
        merged["total_return"].values,
        merged["bh_total_return"].values,
        n_bootstrap=20000,
        seed=42
    )
    res_sharpe = paired_bootstrap_metric(
        merged["sharpe"].values,
        merged["bh_sharpe"].values,
        n_bootstrap=20000,
        seed=42
    )
    # For drawdown: "higher is better" because it's negative; compare deltas directly
    res_dd = paired_bootstrap_metric(
        merged["max_drawdown"].values,
        merged["bh_max_drawdown"].values,
        n_bootstrap=20000,
        seed=42
    )

    print("📌 RESULTS (Portfolio minus SPY Buy&Hold)\n")

    def pretty(metric_name: str, r: dict):
        print(f"Metric: {metric_name}")
        print(f"  Observed mean Δ:   {r['observed_mean_delta']:.6f}")
        print(f"  Observed median Δ: {r['observed_median_delta']:.6f}")
        print(f"  Win-rate:          {r['win_rate'] * 100:.2f}%")
        print(f"  95% CI(mean Δ):    [{r['ci_low']:.6f}, {r['ci_high']:.6f}]")
        print(f"  One-sided p-value: {r['p_value_one_sided']:.4f}\n")

    pretty("total_return", res_return)
    pretty("sharpe", res_sharpe)
    pretty("max_drawdown", res_dd)

    out = pd.DataFrame([
        {"metric": "total_return", **res_return},
        {"metric": "sharpe", **res_sharpe},
        {"metric": "max_drawdown", **res_dd},
    ])

    out_path = "reports/csv/portfolio_bootstrap_significance.csv"
    out.to_csv(out_path, index=False)

    print(f"✅ Saved to {out_path}")
    print(f"✅ Saved paired windows to {paired_path}")


if __name__ == "__main__":
    main()
