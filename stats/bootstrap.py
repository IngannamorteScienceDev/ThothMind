import numpy as np


def paired_bootstrap_test(
    strategy_returns,
    benchmark_returns,
    n_bootstrap: int = 10000,
    seed: int = 42
):
    """
    Paired bootstrap test for difference in mean returns.
    H0: E[strategy - benchmark] <= 0
    """

    rng = np.random.default_rng(seed)

    strategy_returns = np.asarray(strategy_returns)
    benchmark_returns = np.asarray(benchmark_returns)

    diff = strategy_returns - benchmark_returns
    observed_mean = diff.mean()

    bootstrap_means = []
    n = len(diff)

    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, n)
        bootstrap_means.append(diff[idx].mean())

    bootstrap_means = np.array(bootstrap_means)

    p_value = np.mean(bootstrap_means <= 0)

    return {
        "observed_mean": observed_mean,
        "bootstrap_means": bootstrap_means,
        "p_value": p_value
    }
