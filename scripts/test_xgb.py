import sys
import os
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_model import train_xgb
from forecasting.metrics import print_regression_metrics

def main():
    ticker = "AAPL"
    df = load_ticker_data(ticker)
    df_feat = generate_features(df)

    model, X_test, y_test, y_pred = train_xgb(df_feat)

    print_regression_metrics(y_test, y_pred)

    # Визуализация
    plt.figure(figsize=(10, 5))
    plt.plot(y_test.values, label="Actual")
    plt.plot(y_pred, label="Predicted")
    plt.title(f"{ticker.upper()} — XGBoost Forecast vs Actual")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
