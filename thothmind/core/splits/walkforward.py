from __future__ import annotations


def generate_walkforward_splits(
    n_rows: int,
    train_size: int,
    test_size: int,
    step: int,
) -> list[dict]:
    """
    Generate walk-forward splits using integer indices (0..n_rows-1).

    Each split is a dict:
      - train_start, train_end (inclusive)
      - test_start, test_end (inclusive)

    Example:
      train [0..755], test [756..818], step=63 -> next train [63..818], test [819..881], etc.
    """
    train_size = int(train_size)
    test_size = int(test_size)
    step = int(step)

    if train_size <= 0 or test_size <= 0 or step <= 0:
        raise ValueError("train_size, test_size, and step must be positive integers.")

    if n_rows < train_size + test_size:
        raise ValueError(
            f"Not enough rows for one split: n_rows={n_rows}, "
            f"need at least train_size+test_size={train_size+test_size}."
        )

    splits = []
    train_start = 0

    while True:
        train_end = train_start + train_size - 1
        test_start = train_end + 1
        test_end = test_start + test_size - 1

        if test_end >= n_rows:
            break

        splits.append(
            {
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
            }
        )

        train_start += step

    if not splits:
        raise ValueError("No splits generated. Check parameters.")

    return splits
