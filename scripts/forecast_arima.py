import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.arima_model import forecast_arima

def main():
    ticker = "AAPL"
    df = load_ticker_data(ticker)
    forecast_arima(df, ticker, forecast_days=30)

if __name__ == "__main__":
    main()
