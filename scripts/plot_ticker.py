import sys
import os

# Добавляем корень проекта в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from eda.visuals import plot_price_with_sma

def main():
    ticker = "AAPL"
    df = load_ticker_data(ticker)
    plot_price_with_sma(df, ticker)

if __name__ == "__main__":
    main()
