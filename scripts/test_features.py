import sys
import os

# Добавляем корень проекта в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features

def main():
    ticker = "AAPL"
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    print("🧠 Сгенерированы признаки:")
    print(df_feat.head())

    print("\n🎯 Примеры целевой переменной:")
    print(df_feat[[f"target_return_5d"]].head())

if __name__ == "__main__":
    main()
