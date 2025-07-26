import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_model import train_xgb
from explain.shap_explainer import explain_xgb_model

def main():
    ticker = "AAPL"
    from forecasting.metrics import print_regression_metrics

    df = load_ticker_data(ticker)
    df_feat = generate_features(df)
    model, X_test, y_test, y_pred = train_xgb(df_feat)

    print_regression_metrics(y_test, y_pred)
    explain_xgb_model(model, X_test)

if __name__ == "__main__":
    main()
