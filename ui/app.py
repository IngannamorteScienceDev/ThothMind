import os
import sys
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Добавим корень проекта
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features

# 📊 EDA-индикаторы
def plot_price_and_indicators(df: pd.DataFrame, ticker: str):
    df = df.sort_values("Date")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["Date"], df["Close"], label="Close", linewidth=1.8)
    ax.plot(df["Date"], df["SMA_5"], label="SMA 5", linestyle="--")
    ax.plot(df["Date"], df["SMA_20"], label="SMA 20", linestyle="--")
    ax.plot(df["Date"], df["SMA_50"], label="SMA 50", linestyle="--")
    ax.set_title(f"{ticker} — Price and SMA")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.grid(True)
    ax.legend()
    st.pyplot(fig)

    # RSI-график
    fig2, ax2 = plt.subplots(figsize=(12, 3))
    delta = df["Close"].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.rolling(14).mean()
    roll_down = down.rolling(14).mean()
    rs = roll_up / roll_down
    rsi = 100 - (100 / (1 + rs))
    ax2.plot(df["Date"], rsi, label="RSI", color="purple")
    ax2.axhline(70, linestyle="--", color="red", alpha=0.4)
    ax2.axhline(30, linestyle="--", color="green", alpha=0.4)
    ax2.set_title(f"{ticker} — RSI (14)")
    ax2.grid(True)
    st.pyplot(fig2)

# 🧠 Настройки дашборда
st.set_page_config(page_title="ThothMind Dashboard", layout="wide")
st.title("🧠 ThothMind — Market Intelligence Platform")

# 📂 Вкладки
tab = st.sidebar.selectbox("Выберите модуль:", [
    "📊 EDA",
    "🧠 Model",
    "🧪 Tuning",
    "📈 SHAP",
    "📥 Upload CSV",
    "📤 Export"
])

# Общий ввод тикера
ticker = st.sidebar.text_input("Ticker:", "AAPL").upper()

# 📊 Вкладка: EDA
if tab == "📊 EDA":
    st.header("📊 Exploratory Data Analysis")
    st.write("Загрузка данных и визуализация цены, SMA и RSI")

    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    st.success(f"Загружено {len(df)} строк для {ticker}")
    plot_price_and_indicators(df_feat, ticker)
    st.dataframe(df_feat.tail(10))

from forecasting.xgb_classifier import train_classifier
from forecasting.threshold_optimizer import find_best_threshold
from simulate.smart_simulator import simulate_with_filters
from sklearn.metrics import classification_report, roc_auc_score

# 🧠 Вкладка: Model
elif tab == "🧠 Model":
    st.header("🧠 Model Training & Strategy Simulation")

    if st.button("🚀 Запустить модель"):
        df = load_ticker_data(ticker)
        df_feat = generate_features(df)

        model, X_test, y_test, y_proba = train_classifier(df_feat)
        roc_auc = round(roc_auc_score(y_test, y_proba), 4)

        best_t, best_f1 = find_best_threshold(y_test, y_proba)
        preds = (y_proba > best_t).astype(int)

        sim_df = simulate_with_filters(df_feat, y_proba, threshold=best_t)
        strategy_return = sim_df["capital"].iloc[-1] - 1
        trades = int(sim_df["final_signal"].sum())

        st.success("✅ Модель обучена и стратегия рассчитана")
        st.markdown(f"""
        - **ROC AUC:** `{roc_auc}`
        - **Best threshold:** `{best_t:.3f}` (F1 = `{best_f1:.3f}`)
        - **Trades made:** `{trades}`
        - **Return:** `{strategy_return:.2%}`
        """)

        st.subheader("📈 Strategy vs Buy & Hold")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(sim_df["capital"], label="Strategy")
        ax.plot(sim_df["buy_and_hold"], label="Buy & Hold", linestyle="--")
        ax.legend()
        ax.grid(True)
        st.pyplot(fig)

        st.subheader("📄 Последние сигналы модели")
        st.dataframe(sim_df.tail(10))
    else:
        st.info("Нажмите кнопку выше, чтобы обучить модель и запустить стратегию.")

# 🧪 Вкладка: Tuning
elif tab == "🧪 Tuning":
    st.header("🧪 Model Tuning")
    st.info("Раздел в разработке...")

# 📈 Вкладка: SHAP
elif tab == "📈 SHAP":
    st.header("📈 Explainable AI (SHAP)")
    st.info("Раздел в разработке...")

# 📥 Вкладка: Upload CSV
elif tab == "📥 Upload CSV":
    st.header("📥 Прогноз по загруженному CSV")
    st.info("Раздел в разработке...")

# 📤 Вкладка: Export
elif tab == "📤 Export":
    st.header("📤 Отчёты и загрузки")
    st.info("Раздел в разработке...")
