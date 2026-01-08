import os
import sys

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from data.smart_loader import load_ticker_data
from forecasting.features import generate_features
from forecasting.xgb_regressor import train_regressor
from simulate.smart_simulator import simulate_with_filters
from forecasting.metrics import evaluate_strategy

ticker = "AAPL"

df = load_ticker_data(ticker)
df_feat = generate_features(df)

model, X_test, y_test, y_pred = train_regressor(df_feat)

sim_df = simulate_with_filters(
    df_feat,
    y_pred,
    entry_threshold=0.01,   # 1%
    exit_threshold=0.0,
    max_holding=5,
    commission=0.001,
    use_filters=True
)

metrics = evaluate_strategy(sim_df)

print("Strategy metrics:")
for k, v in metrics.items():
    print(f"{k}: {v}")
