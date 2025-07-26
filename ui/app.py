import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_classifier import train_classifier
from forecasting.threshold_optimizer import find_best_threshold
from simulate.smart_simulator import simulate_with_filters
from reports.exporter import (
    save_model,
    save_predictions,
    save_strategy_plot,
    save_summary_report
)

st.set_page_config(page_title="ThothMind Dashboard", layout="wide")
st.title("🧠 ThothMind — Market Intelligence")

# Выбор тикера
ticker = st.text_input("Enter ticker symbol:", "AAPL").upper()

if st.button("📥 Run Analysis"):
    st.info(f"Загружаем данные для {ticker}...")
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    st.success("Признаки сгенерированы.")

    # Обучение модели
    model, X_test, y_test, y_proba = train_classifier(df_feat)
    roc_auc = round(roc_auc_score(y_test, y_proba), 4)

    best_t, best_f1 = find_best_threshold(y_test, y_proba)
    preds = (y_proba > best_t).astype(int)

    sim_df = simulate_with_filters(df_feat, y_proba, threshold=best_t)
    strategy_return = sim_df["capital"].iloc[-1] - 1
    trades = int(sim_df["final_signal"].sum())

    metrics = {
        "roc_auc": roc_auc,
        "threshold": best_t,
        "f1": best_f1,
        "trades": trades,
        "strategy_return": strategy_return
    }

    # Экспорт
    save_model(model)
    save_predictions(sim_df)
    save_strategy_plot(sim_df)
    save_summary_report(ticker, metrics)

    st.subheader("📊 Модель обучена")
    st.markdown(f"""
    - **ROC AUC:** `{roc_auc}`
    - **Best threshold:** `{best_t:.3f}` (F1 = `{best_f1:.3f}`)
    - **Trades made:** `{trades}`
    - **Return:** `{strategy_return:.2%}`
    """)

    # Показ графика
    st.subheader("📈 Стратегия против Buy & Hold")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(sim_df["capital"], label="Strategy")
    ax.plot(sim_df["buy_and_hold"], label="Buy & Hold", linestyle="--")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)

    # Скачать CSV
    st.download_button("⬇️ Download predictions (CSV)",
                       sim_df.to_csv(index=False), file_name=f"{ticker}_predictions.csv")

    # Показ DataFrame
    st.subheader("📄 Последние сигналы")
    st.dataframe(sim_df.tail(10))

