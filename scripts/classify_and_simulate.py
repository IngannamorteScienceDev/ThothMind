import sys
import os
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_classifier import train_classifier
from forecasting.threshold_optimizer import find_best_threshold
from simulate.smart_simulator import simulate_with_filters
from sklearn.metrics import classification_report, roc_auc_score

from reports.exporter import (
    save_model,
    save_predictions,
    save_strategy_plot,
    save_summary_report
)

def main():
    ticker = "AAPL"
    use_filters = False  # 🔁 Меняй на True/False по желанию

    print("🧠 Загрузка данных и генерация признаков...")
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    print("📚 Обучение модели...")
    model, X_test, y_test, y_proba = train_classifier(df_feat)
    roc_auc = roc_auc_score(y_test, y_proba)
    print(f"ROC AUC: {roc_auc:.4f}")

    best_t, best_f1 = find_best_threshold(y_test, y_proba)
    print(f"Best threshold: {best_t:.3f} (F1 = {best_f1:.3f})")

    preds = (y_proba > best_t).astype(int)
    print("\n" + classification_report(y_test, preds))

    print("📈 Запуск симуляции стратегии...")
    sim_df = simulate_with_filters(df_feat, y_proba, threshold=best_t, use_filters=use_filters)

    strategy_return = sim_df["capital"].iloc[-1] - 1
    print(f"\n📈 Final strategy return: {strategy_return:.2%}")
    print(f"📊 Trades made: {sim_df['final_signal'].sum()}")

    plt.figure(figsize=(10, 5))
    plt.plot(sim_df["capital"], label="Strategy")
    plt.plot(sim_df["buy_and_hold"], label="Buy & Hold", linestyle="--")
    plt.title(f"{ticker.upper()} — Strategy Simulation (Filters: {'ON' if use_filters else 'OFF'})")
    plt.xlabel("Test Period")
    plt.ylabel("Capital Growth")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    print("💾 Экспорт результатов...")
    save_model(model, ticker)
    save_predictions(sim_df, ticker)
    save_strategy_plot(sim_df, ticker)
    save_summary_report(
        ticker,
        metrics={
            "roc_auc": roc_auc,
            "threshold": best_t,
            "f1": best_f1,
            "trades": sim_df["final_signal"].sum(),
            "strategy_return": strategy_return
        }
    )

if __name__ == "__main__":
    main()
