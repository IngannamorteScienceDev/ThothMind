import os
import sys
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import shap
import numpy as np
import base64
from sklearn.metrics import mean_squared_error, r2_score

# Добавим корень проекта
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor
from forecasting.xgb_tuner import tune_xgb_model
from simulate.smart_simulator import simulate_with_filters

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

# 🧠 Настройки
st.set_page_config(page_title="ThothMind Dashboard", layout="wide")
st.title("🧠 ThothMind — Market Intelligence Platform")

# Вкладки
tab = st.sidebar.selectbox("Выберите модуль:", [
    "📊 EDA",
    "🧠 Model",
    "🧪 Tuning",
    "📈 SHAP",
    "📥 Upload CSV",
    "📤 Export"
])

# Тикер
ticker = st.sidebar.text_input("Ticker:", "AAPL").upper()

# 📊 EDA
if tab == "📊 EDA":
    st.header("📊 Exploratory Data Analysis")
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)
    st.success(f"Загружено {len(df)} строк для {ticker}")
    plot_price_and_indicators(df_feat, ticker)
    st.dataframe(df_feat.tail(10))

# 🧠 Model
elif tab == "🧠 Model":
    st.header("🧠 Model Training & Strategy Simulation")

    use_filters = st.checkbox("🧪 Применять технические фильтры (RSI / SMA)", value=True)

    if st.button("🚀 Запустить модель"):
        df = load_ticker_data(ticker)
        df_feat = generate_features(df)

        model, X_test, y_test, y_pred = train_regressor(df_feat)
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_test, y_pred)

        sim_df = simulate_with_filters(df_feat, y_pred, threshold=0, use_filters=use_filters)
        strategy_return = sim_df["capital"].iloc[-1] - 1
        trades = int(sim_df["final_signal"].sum())

        st.success("✅ Модель обучена и стратегия рассчитана")
        st.markdown(f"""
        - **R²:** `{r2:.4f}`
        - **RMSE:** `{rmse:.6f}`
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

        # Сохраняем
        from reports.exporter import (
            save_model,
            save_predictions,
            save_strategy_plot,
            save_summary_report
        )
        save_model(model, ticker)
        save_predictions(sim_df, ticker)
        save_strategy_plot(sim_df, ticker)
        save_summary_report(
            ticker,
            metrics={
                "r2": r2,
                "rmse": rmse,
                "trades": trades,
                "strategy_return": strategy_return
            }
        )
    else:
        st.info("Нажмите кнопку выше, чтобы обучить модель и запустить стратегию.")
