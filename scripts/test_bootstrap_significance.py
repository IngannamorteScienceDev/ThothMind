import os
import numpy as np
import pandas as pd


# =======================
# CONFIG
# =======================

TICKER = "AAPL"
INPUT_PATH = f"reports/csv/regime_aware_walk_forward_{TICKER}.csv"
N_BOOT = 20_000
SEED = 42

METRICS = ["total_return", "sharpe"]


def percentile_ci(x: np.ndarray, alpha: float = 0.05):
    lo = np.percentile(x, 100 * (alpha / 2))
    hi = np.percentile(x, 100 * (1 - alpha / 2))
    return lo, hi


def paired_bootstrap_mean_diff(diffs: np.ndarray, n_boot: int, seed: int):
    """
    Paired bootstrap on per-window diffs.
    Resample windows with replacement and compute mean diff.
    """
    rng = np.random.default_rng(seed)
    n = len(diffs)
    boot_means = np.empty(n_boot, dtype=float)

    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)  # resample windows
        boot_means[i] = diffs[idx].mean()

    return boot_means


def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"File not found: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    # Keep only the clean comparison: global vs regime_aware
    # (fallback is not a regime-aware model, it's just a safeguard)
    df = df[df["model"].isin(["global", "regime_aware"])].copy()

    # We need paired rows per test window (same test_start/test_end)
    key_cols = ["test_start", "test_end", "market_regime"]
    pivot = df.pivot_table(
        index=key_cols,
        columns="model",
        values=METRICS,
        aggfunc="first"
    )

    # Drop windows where regime_aware is missing (because fallback happened)
    pivot = pivot.dropna(subset=[(m, "global") for m in METRICS] + [(m, "regime_aware") for m in METRICS], how="any")

    # Flatten columns: (metric, model) -> metric__model
    pivot.columns = [f"{metric}__{model}" for metric, model in pivot.columns]
    pivot = pivot.reset_index()

    if len(pivot) < 5:
        raise RuntimeError(
            f"Too few paired windows for bootstrap: {len(pivot)}. "
            "Try lowering MIN_REGIME_TRAIN_SAMPLES or increasing history."
        )

    print(f"\n🧪 Bootstrap significance (paired) for {TICKER}")
    print(f"Paired windows used: {len(pivot)}")
    print(f"Bootstrap samples: {N_BOOT}")

    rng_seed = SEED

    results = []

    for metric in METRICS:
        g = pivot[f"{metric}__global"].to_numpy(dtype=float)
        r = pivot[f"{metric}__regime_aware"].to_numpy(dtype=float)

        diffs = r - g  # per-window paired differences
        obs_mean = diffs.mean()
        obs_median = np.median(diffs)
        win_rate = (diffs > 0).mean()

        boot_means = paired_bootstrap_mean_diff(diffs, n_boot=N_BOOT, seed=rng_seed)
        ci_lo, ci_hi = percentile_ci(boot_means, alpha=0.05)

        # One-sided p-value: probability that mean improvement <= 0
        p_one_sided = (boot_means <= 0).mean()

        results.append({
            "metric": metric,
            "obs_mean_diff": obs_mean,
            "obs_median_diff": obs_median,
            "win_rate": win_rate,
            "boot_mean_ci_lo_95": ci_lo,
            "boot_mean_ci_hi_95": ci_hi,
            "p_value_one_sided": p_one_sided
        })

        rng_seed += 1  # slightly vary seed per metric

    results_df = pd.DataFrame(results)

    # Pretty print
    print("\n📌 RESULTS (Regime-aware minus Global)")
    for _, row in results_df.iterrows():
        metric = row["metric"]
        print(f"\nMetric: {metric}")
        print(f"  Observed mean Δ:   {row['obs_mean_diff']:.6f}")
        print(f"  Observed median Δ: {row['obs_median_diff']:.6f}")
        print(f"  Win-rate:          {row['win_rate']:.2%}")
        print(f"  95% CI(mean Δ):    [{row['boot_mean_ci_lo_95']:.6f}, {row['boot_mean_ci_hi_95']:.6f}]")
        print(f"  One-sided p-value: {row['p_value_one_sided']:.4f}")

    os.makedirs("reports/csv", exist_ok=True)
    out_path = f"reports/csv/bootstrap_significance_{TICKER}.csv"
    results_df.to_csv(out_path, index=False)
    print(f"\n✅ Saved to {out_path}")

    # Also save paired diffs for transparency / appendix
    diffs_out = f"reports/csv/bootstrap_paired_windows_{TICKER}.csv"
    pivot.to_csv(diffs_out, index=False)
    print(f"✅ Saved paired windows to {diffs_out}")


if __name__ == "__main__":
    main()
