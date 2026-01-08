import os
import pandas as pd
import joblib
import matplotlib.pyplot as plt

def save_model(model, ticker: str):
    path = f"models/xgb_{ticker.upper()}.joblib"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)

def save_predictions(df: pd.DataFrame, ticker: str):
    path = f"reports/csv/{ticker.upper()}_predictions.csv"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)

def save_strategy_plot(df: pd.DataFrame, ticker: str):
    path = f"reports/plots/{ticker.upper()}_strategy.png"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    plt.figure(figsize=(10, 5))
    plt.plot(df["capital"], label="Strategy")
    plt.plot(df["buy_and_hold"], label="Buy & Hold", linestyle="--")
    plt.plot(df["random_capital"], label="Random", linestyle=":")
    plt.title(f"{ticker.upper()} — Strategy Backtest")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def save_summary_report(
    ticker: str,
    regression_metrics: dict,
    strategy_metrics: dict
):
    path = f"reports/summary/summary_{ticker.upper()}.md"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 📊 ThothMind Report — {ticker.upper()}\n\n")

        f.write("## 🤖 Regression model quality\n")
        f.write(f"- R²: {regression_metrics['r2']:.4f}\n")
        f.write(f"- RMSE: {regression_metrics['rmse']:.6f}\n")
        f.write(f"- MAE: {regression_metrics['mae']:.6f}\n")
        f.write(f"- MAPE: {regression_metrics['mape']:.2f}%\n\n")

        f.write("## 📈 Strategy performance\n")
        f.write(f"- Total return: {strategy_metrics['total_return']:.2%}\n")
        f.write(f"- Sharpe ratio: {strategy_metrics['sharpe']:.3f}\n")
        f.write(f"- Max drawdown: {strategy_metrics['max_drawdown']:.2%}\n\n")

        f.write(f"![Strategy plot](../plots/{ticker.upper()}_strategy.png)\n")
