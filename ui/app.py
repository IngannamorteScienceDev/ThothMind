import os
import sys
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import shap
import numpy as np
import base64

# Добавим корень проекта
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor
from forecasting.metrics import evaluate_regression, evaluate_strategy
from simulate.smart_simulator import simulate_with_filters
from forecasting.xgb_tuner import tune_xgb_model

# =========================
# EDA plots
# =========================

def plot_price_and_indicators(df: pd.DataFrame, ticker: str):
    df = df.sort_values("Date")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["Date"], df["Close"], label="Close")
    ax.plot(df["Date"], df["SMA_5"], label="SMA 5", linestyle="--")
    ax.plot(df["Date"], df["SMA_20"], label="SMA 20", linestyle="--")
    ax.plot(df["Date"], df["SMA_50"], label="SMA 50", linestyle="--")
    ax.set_title(f"{ticker} — Price & SMA")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)

# =========================
# Streamlit layout
# =========================

st.set_page_config(page_title="ThothMind Dashboard", layout="wide")
st.title("🧠 ThothMind — Market Intelligence Platform")

tab = st.sidebar.selectbox(
    "Select module:",
    ["📊 EDA", "🧠 Model", "🧪 Tuning", "📈 SHAP", "📤 Export"]
)

ticker = st.sidebar.text_input("Ticker:", "AAPL").upper()

# =========================
# EDA
# =========================

if tab == "📊 EDA":
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    st.success(f"Loaded {len(df_feat)} rows for {ticker}")
    plot_price_and_indicators(df_feat, ticker)
    st.dataframe(df_feat.tail(10))

# =========================
# Model
# =========================

elif tab == "🧠 Model":
    st.header("🧠 Regression Model & Strategy")

    threshold = st.slider(
        "Minimum predicted return to enter trade",
        min_value=0.0,
        max_value=0.05,
        value=0.01,
        step=0.001
    )

    use_filters = st.checkbox("Use technical trend filters (SMA)", value=True)

    if st.button("🚀 Train model & simulate"):
        df = load_ticker_data(ticker)
        df_feat = generate_features(df)

        model, X_test, y_test, y_pred = train_regressor(df_feat)

        reg_metrics = evaluate_regression(y_test, y_pred)

        sim_df = simulate_with_filters(
            df_feat,
            y_pred,
            threshold=threshold,
            use_filters=use_filters
        )

        strat_metrics = evaluate_strategy(sim_df)

        st.success("Model trained and strategy simulated")

        st.markdown("### 📐 Regression metrics")
        st.json(reg_metrics)

        st.markdown("### 📈 Strategy metrics")
        st.json(strat_metrics)

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(sim_df["capital"], label="Strategy")
        ax.plot(sim_df["buy_and_hold"], label="Buy & Hold", linestyle="--")
        ax.plot(sim_df["random_capital"], label="Random", linestyle=":")
        ax.legend()
        ax.grid(True)
        st.pyplot(fig)

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
            regression_metrics=reg_metrics,
            strategy_metrics=strat_metrics
        )

# =========================
# Tuning
# =========================

elif tab == "🧪 Tuning":
    st.header("🧪 XGBoost Hyperparameter Tuning")

    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    if st.button("Run GridSearch"):
        best_params, best_rmse, results = tune_xgb_model(df_feat)
        st.success("Best parameters found")
        st.json(best_params)
        st.write(f"Best RMSE: {best_rmse:.6f}")
        st.dataframe(results.head(10))

# =========================
# SHAP
# =========================

elif tab == "📈 SHAP":
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    model, X_test, y_test, y_pred = train_regressor(df_feat)

    explainer = shap.Explainer(model)
    shap_values = explainer(X_test)

    st.subheader("SHAP feature importance")
    shap.plots.bar(shap_values, show=False)
    st.pyplot(plt.gcf())
    plt.clf()

# =========================
# Export
# =========================

elif tab == "📤 Export":
    st.header("📤 Reports & Downloads")

    files = {
        "📄 Markdown report": f"reports/summary/summary_{ticker}.md",
        "📈 Strategy plot": f"reports/plots/{ticker}_strategy.png",
        "📦 Predictions CSV": f"reports/csv/{ticker}_predictions.csv",
        "🧠 Model file": f"models/xgb_{ticker}.joblib"
    }

    for label, path in files.items():
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                href = f'<a href="data:file/octet-stream;base64,{b64}" download="{os.path.basename(path)}">{label}</a>'
                st.markdown(href, unsafe_allow_html=True)
        else:
            st.warning(f"{label} not found")
