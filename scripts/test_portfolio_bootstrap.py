import os
import sys
import numpy as np
import pandas as pd

# ===============================
# PROJECT ROOT PATCH
# ===============================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ===============================
# CONFIG
# ===============================
ALLOCATION_RESULTS_PATH = "reports/csv/portfolio_allocation_results.csv"
BOOTSTRAP_SAMPLES = 20000
OUTPUT_PATH = "reports/csv/portfolio_bootstrap_significance.csv"


def bootstrap_mean_diff(a, b, n=10000):
    diffs = []
    for _ in range(n):
        idx = np.random.randint(0, len(a), len(a))
        diffs.append(np.mean(a[idx] - b[idx]))
    return np.array(diffs)


def main():
    print("\n🧪 Portfolio bootstrap significance (window-level)")

    if not os.path.exists(ALLOCATION_RESULTS_PATH):
        raise FileNotFoundError(
            "Run scripts/test_portfolio_allocation.py first."
        )

    df = pd.read_csv(ALLOCATION_RESULTS_PATH)

    results = []

    for alloc in sorted(df["allocation"].unique()):
        sub = df[df["allocation"] == alloc]

        # 🔑 WINDOW-LEVEL RETURNS
        strategy = sub["total_return"].values
        benchmark = sub["benchmark_bh_return"].values

        # sanity check
        if len(strategy) < 5:
            continue

        diffs = bootstrap_mean_diff(strategy, benchmark, BOOTSTRAP_SAMPLES)

        results.append({
            "allocation": alloc,
            "mean_excess_return": diffs.mean(),
            "ci_lower": np.percentile(diffs, 2.5),
            "ci_upper": np.percentile(diffs, 97.5),
            "p_value": np.mean(diffs <= 0)
        })

        print(f"\n📌 Allocation = {alloc}")
        print(f"Mean excess return: {diffs.mean():.4f}")
        print(f"95% CI: [{np.percentile(diffs,2.5):.4f}, {np.percentile(diffs,97.5):.4f}]")
        print(f"P-value: {np.mean(diffs <= 0):.4f}")

    result_df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    result_df.to_csv(OUTPUT_PATH, index=False)

    print("\n✅ Saved:")
    print(f"   {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
