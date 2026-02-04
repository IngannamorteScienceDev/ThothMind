from pathlib import Path
import matplotlib.pyplot as plt


def plot_drawdown(sim_df, out_path: Path) -> None:
    """
    Plot drawdown curve. If 'drawdown' column is missing, compute it from equity:
      drawdown = equity / cummax(equity) - 1
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = sim_df.copy()
    if "date" not in df.columns:
        raise KeyError("plot_drawdown expects 'date' column.")
    if "drawdown" not in df.columns:
        if "equity" not in df.columns:
            raise KeyError("plot_drawdown expects 'equity' if 'drawdown' is missing.")
        eq = df["equity"].astype(float)
        peak = eq.cummax()
        df["drawdown"] = eq / peak - 1.0

    plt.figure()
    plt.plot(df["date"], df["drawdown"])
    plt.title("Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
