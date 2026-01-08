import pandas as pd
from xgboost import XGBRegressor


FEATURE_COLS = [
    "return_1d", "return_5d", "return_20d",
    "SMA_5", "SMA_20", "SMA_50",
    "volatility_5d", "volatility_20d",
    "lag_1", "lag_5", "lag_20"
]


def train_xgb_on_window(train_df: pd.DataFrame):
    """
    Train XGBoost regressor on a given training window.
    """
    X_train = train_df[FEATURE_COLS]
    y_train = train_df["target_return_5d"]

    model = XGBRegressor(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )

    model.fit(X_train, y_train)
    return model


def predict_on_window(model, test_df: pd.DataFrame):
    """
    Generate predictions for the test window.
    """
    X_test = test_df[FEATURE_COLS]
    y_pred = model.predict(X_test)
    return y_pred
