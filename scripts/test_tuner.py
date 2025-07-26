import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_tuner import tune_xgb

def main():
    ticker = "AAPL"
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    print("🔍 Запуск подбора параметров XGBoost...")
    model, params, score = tune_xgb(df_feat)

    print("\n✅ Лучшие параметры:")
    for k, v in params.items():
        print(f"- {k}: {v}")

    print(f"\n📉 Best RMSE (cv): {score:.5f}")

if __name__ == "__main__":
    main()
