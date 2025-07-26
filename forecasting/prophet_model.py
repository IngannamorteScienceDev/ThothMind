import pandas as pd
import matplotlib.pyplot as plt
from prophet import Prophet

def forecast_prophet(df: pd.DataFrame, ticker: str, forecast_days: int = 30):
    """
    Строит прогноз с помощью Facebook Prophet на N дней
    """
    df = df.copy()
    df = df[["Date", "Close"]].rename(columns={"Date": "ds", "Close": "y"})
    df = df.sort_values("ds")

    # Модель
    model = Prophet(daily_seasonality=True)
    model.fit(df)

    # Прогноз
    future = model.make_future_dataframe(periods=forecast_days)
    forecast = model.predict(future)

    # График
    fig = model.plot(forecast)
    plt.title(f"{ticker.upper()} — Prophet Forecast ({forecast_days}d)")
    plt.xlabel("Date")
    plt.ylabel("Close Price")
    plt.grid(True)
    plt.tight_layout()
    plt.show()
