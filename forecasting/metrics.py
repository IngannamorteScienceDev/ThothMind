from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np

def print_regression_metrics(y_true, y_pred):
    print("📊 Evaluation Metrics:")
    print(f"MAE:  {mean_absolute_error(y_true, y_pred):.5f}")
    print(f"RMSE: {np.sqrt(mean_squared_error(y_true, y_pred)):.5f}")
    print(f"R²:   {r2_score(y_true, y_pred):.5f}")
