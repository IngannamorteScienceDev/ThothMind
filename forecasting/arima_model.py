import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from datetime import timedelta

def forecast_arima(df: pd.DataFrame, ticker: str, forecast_days: int = 30):
    """
    Обучает ARIMA и прогнозирует на N дней по цене закрытия
    """
    df = df.copy()
    df.set_index("Date", inplace=True)
    series = df["Close"]

    # ARIMA(5,1,0) — можно заменить на авто-подбор
    model = ARIMA(series, order=(5, 1, 0))
    model_fit = model.fit()

    # Прогноз
    forecast = model_fit.forecast(steps=forecast_days)

    # Даты прогноза
    last_date = series.index[-1]
    forecast_index = [last_date + timedelta(days=i) for i in range(1, forecast_days + 1)]

    # Построение графика
    plt.figure(figsize=(12, 6))
    plt.plot(series[-200:], label="Actual", color="blue")
    plt.plot(forecast_index, forecast, label="Forecast", color="orange")
    plt.title(f"{ticker.upper()} — ARIMA Forecast ({forecast_days}d)")
    plt.xlabel("Date")
    plt.ylabel("Close Price")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()
