import sys
import os
import warnings
import matplotlib.pyplot as plt

# Подавим ворнинги от XGBoost
warnings.filterwarnings("ignore", category=UserWarning)

# Подключаем корень проекта
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
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    model, X_test, y_test, y_proba = train_classifier(df_feat)
    roc_auc = roc_auc_score(y_test, y_proba)
    print(f"ROC AUC: {roc_auc:.4f}")

    best_t, best_f1 = find_best_threshold(y_test, y_proba)
    print(f"Best threshold: {best_t:.3f} (F1 = {best_f1:.3f})")

    preds = (y_proba > best_t).astype(int)
    print("\n" + classification_report(y_test, preds))

    sim_df = simulate_with_filters(df_feat, y_proba, threshold=best_t)

    # Финальные метрики
    metrics = {
        "roc_auc": roc_auc,
        "threshold": best_t,
        "f1": best_f1,
        "trades": int(sim_df["final_signal"].sum()),
        "strategy_return": sim_df["capital"].iloc[-1] - 1
    }

    print(f"\n📈 Final strategy return: {metrics['strategy_return']:.2%}")
    print(f"📊 Trades made: {metrics['trades']}")

    # 📤 Экспорт
    save_model(model)
    save_predictions(sim_df)
    save_strategy_plot(sim_df)
    save_summary_report(ticker, metrics)

    # Визуализация
    plt.figure(figsize=(10, 5))
    plt.plot(sim_df["capital"], label="Strategy")
    plt.plot(sim_df["buy_and_hold"], label="Buy & Hold", linestyle="--")
    plt.title(f"{ticker.upper()} — Smart Strategy Simulation")
    plt.xlabel("Test Period")
    plt.ylabel("Capital Growth")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
