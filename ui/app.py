import os
import sys
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import shap
import numpy as np
import matplotlib.pyplot as plt

# Добавим корень проекта
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_classifier import train_classifier
from forecasting.threshold_optimizer import find_best_threshold
from simulate.smart_simulator import simulate_with_filters
from sklearn.metrics import classification_report, roc_auc_score
from forecasting.xgb_tuner import tune_xgb_model

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

    st.markdown("**Подбор гиперпараметров XGBoost с использованием GridSearchCV**")

    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    # Пользовательский выбор параметров
    st.sidebar.markdown("🎚 **Диапазоны параметров**")
    learning_rates = st.sidebar.multiselect("learning_rate", [0.001, 0.01, 0.05, 0.1], default=[0.01, 0.1])
    max_depths = st.sidebar.multiselect("max_depth", [2, 3, 4, 5, 6], default=[3, 5])
    estimators = st.sidebar.multiselect("n_estimators", [20, 50, 100, 150], default=[50, 100])
    subsamples = st.sidebar.multiselect("subsample", [0.5, 0.7, 0.8, 1.0], default=[0.8, 1.0])

    if st.button("🔍 Запустить подбор"):
        st.info("Подбираем параметры...")

        best_params, best_score, results_df = tune_xgb_model(
            df_feat,
            learning_rates,
            max_depths,
            estimators,
            subsamples
        )

        st.success("✅ Лучшие параметры найдены")
        st.write(f"**Best RMSE:** {best_score:.5f}")
        st.json(best_params)

        st.subheader("📉 RMSE по параметрам")
        fig, ax = plt.subplots(figsize=(8, 4))
        sns.lineplot(data=results_df, x="n_estimators", y="rmse", hue="learning_rate", style="max_depth", ax=ax)
        ax.grid(True)
        st.pyplot(fig)

        st.subheader("📋 Полные результаты (top 10)")
        st.dataframe(results_df.sort_values("rmse").head(10))

# 📈 Вкладка: SHAP
elif tab == "📈 SHAP":
    st.header("📈 Explainable AI — SHAP Values")

    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    st.info("Обучаем модель и рассчитываем значения SHAP...")
    model, X_test, y_test, y_proba = train_classifier(df_feat)

    explainer = shap.Explainer(model)
    shap_values = explainer(X_test)

    st.success("✅ SHAP значения рассчитаны")

    st.subheader("📊 Важность признаков (summary bar)")
    fig, ax = plt.subplots(figsize=(10, 4))
    shap.plots.bar(shap_values, show=False)
    st.pyplot(plt.gcf())  # Получаем текущую фигуру и рендерим её
    plt.clf()  # Очищаем, чтобы не накапливались графики

    st.subheader("📋 Таблица: топ признаков по важности")
    importance_df = pd.DataFrame({
        "Feature": X_test.columns,
        "Mean |SHAP|": np.abs(shap_values.values).mean(axis=0)
    }).sort_values("Mean |SHAP|", ascending=False)
    st.dataframe(importance_df.head(10))

# 📥 Вкладка: Upload CSV
elif tab == "📥 Upload CSV":
    st.header("📥 Загрузка пользовательского CSV и прогноз")

    uploaded_file = st.file_uploader("Загрузите CSV-файл с историческими данными (Date, Open, High, Low, Close, Volume):", type="csv")

    if uploaded_file is not None:
        user_df = pd.read_csv(uploaded_file)
        st.write("📄 Загружен файл:")
        st.dataframe(user_df.head())

        required_cols = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if not required_cols.issubset(set(user_df.columns)):
            st.error(f"❌ Файл должен содержать колонки: {required_cols}")
        else:
            st.success("✅ Данные загружены корректно. Генерируем признаки...")

            user_df["Date"] = pd.to_datetime(user_df["Date"])
            user_df.sort_values("Date", inplace=True)

            try:
                df_feat = generate_features(user_df)
                st.success("✅ Признаки сгенерированы")

                # Обучим модель на встроенном AAPL
                base_df = load_ticker_data("AAPL")
                base_feat = generate_features(base_df)
                model, _, _, _ = train_classifier(base_feat)

                # Прогноз на пользовательском наборе
                feature_cols = [
                    "return_1d", "return_5d", "return_20d",
                    "SMA_5", "SMA_20", "SMA_50",
                    "volatility_5d", "volatility_20d",
                    "lag_1", "lag_5", "lag_20"
                ]
                X_user = df_feat[feature_cols]
                df_feat["predicted_proba"] = model.predict_proba(X_user)[:, 1]
                df_feat["signal"] = (df_feat["predicted_proba"] > 0.5).astype(int)

                st.subheader("📊 Прогнозы")
                st.dataframe(df_feat[["Date", "Close", "predicted_proba", "signal"]].tail(10))

                st.subheader("📈 График с сигналами")
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(df_feat["Date"], df_feat["Close"], label="Close")
                ax.scatter(df_feat[df_feat["signal"] == 1]["Date"], df_feat[df_feat["signal"] == 1]["Close"],
                           label="Buy Signal", marker="^", color="green")
                ax.set_title("Прогнозируемые сигналы")
                ax.legend()
                ax.grid(True)
                st.pyplot(fig)

                st.download_button("⬇️ Скачать результаты (CSV)",
                                   df_feat.to_csv(index=False),
                                   file_name="thothmind_predictions.csv")
            except Exception as e:
                st.error(f"Ошибка при обработке данных: {e}")
    else:
        st.info("Загрузите CSV для получения прогноза.")

# 📤 Вкладка: Export
elif tab == "📤 Export":
    st.header("📤 Отчёты и загрузки")
    st.info("Раздел в разработке...")
