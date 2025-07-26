import sys
import os
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_model import train_xgb
from simulate.simulator import simulate_strategy
from forecasting.metrics import print_regression_metrics

def main():
    ticker = "AAPL"
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)
    model, X_test, y_test, y_pred = train_xgb(df_feat)

    print_regression_metrics(y_test, y_pred)

    sim_df = simulate_strategy(df_feat, y_pred, threshold=0.01)

    print("\n📈 Статистика симуляции:")
    total_return = sim_df["capital"].iloc[-1] - 1
    winrate = (sim_df["strategy_return"] > 0).mean()
    trades = sim_df["signal"].sum()

    print(f"- Total return: {total_return:.2%}")
    print(f"- Winrate: {winrate:.2%}")
    print(f"- Trades made: {trades}")

    # Визуализация
    plt.figure(figsize=(10, 5))
    plt.plot(sim_df["capital"], label="Strategy")
    plt.plot(sim_df["buy_and_hold"], label="Buy & Hold", linestyle="--")
    plt.title(f"{ticker.upper()} — Investment Simulation")
    plt.xlabel("Time (Test Period)")
    plt.ylabel("Capital Growth")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
