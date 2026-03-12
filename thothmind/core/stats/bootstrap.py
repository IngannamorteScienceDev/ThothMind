from __future__ import annotations

import numpy as np


def moving_block_bootstrap_sample(x: np.ndarray, block_len: int, rng: np.random.Generator) -> np.ndarray:
    """
    Create one moving-block bootstrap sample of length len(x).
    Blocks are sampled with replacement from contiguous segments of length block_len.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    L = int(block_len)
    if n <= 0:
        return x.copy()
    if L <= 0:
        raise ValueError("block_len must be positive.")
    if L > n:
        # If block too large, just sample with replacement (fallback)
        idx = rng.integers(0, n, size=n)
        return x[idx]

    n_blocks = int(np.ceil(n / L))
    starts = rng.integers(0, n - L + 1, size=n_blocks)

    out = []
    for s in starts:
        out.append(x[s : s + L])

    boot = np.concatenate(out)[:n]
    return boot


def moving_block_bootstrap_stats(
    x: np.ndarray,
    stat_fn,
    n_boot: int,
    block_len: int,
    seed: int = 42,
) -> np.ndarray:
    """
    Compute bootstrap statistics for x using moving-block bootstrap.
    """
    rng = np.random.default_rng(int(seed))
    stats = np.empty(int(n_boot), dtype=float)

    for i in range(int(n_boot)):
        xb = moving_block_bootstrap_sample(x, block_len=block_len, rng=rng)
        stats[i] = float(stat_fn(xb))

    return stats
