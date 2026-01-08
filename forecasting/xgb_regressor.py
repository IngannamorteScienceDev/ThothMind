import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split

def train_regressor(df: pd.DataFrame):
    feature_cols = [
        "return_1d", "return_5d", "return_20d",
        "SMA_5", "SMA_20", "SMA_50",
        "volatility_5d", "volatility_20d",
        "lag_1", "lag_5", "lag_20"
    ]
    X = df[feature_cols]
    y = df["target_return_5d"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=3)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    return model, X_test, y_test, y_pred
