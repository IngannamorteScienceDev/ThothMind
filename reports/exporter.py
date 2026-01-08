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
    plt.title(f"{ticker.upper()} — Smart Strategy Simulation")
    plt.xlabel("Test Period")
    plt.ylabel("Capital Growth")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def save_summary_report(ticker: str, metrics: dict):
    path = f"reports/summary/summary_{ticker.upper()}.md"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 📊 ThothMind Report — {ticker.upper()}\n\n")
        f.write(f"**Model:** XGBoost Regressor\n")
        f.write(f"**R² Score:** {metrics['r2']:.4f}\n")
        f.write(f"**RMSE:** {metrics['rmse']:.6f}\n")
        f.write(f"**Trades Made:** {metrics['trades']}\n")
        f.write(f"**Strategy Return:** {metrics['strategy_return']:.2%}\n\n")
        f.write(f"![Strategy Plot](../plots/{ticker.upper()}_strategy.png)\n")
