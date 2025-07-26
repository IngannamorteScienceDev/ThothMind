import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split

def train_xgb(df: pd.DataFrame, target_column: str = "target_return_5d"):
    """
    Обучает XGBoost модель на признаках
    """
    # Целевая переменная и признаки
    features = df.drop(columns=["Date", "ticker", target_column])
    target = df[target_column]

    # Делим на train/test
    X_train, X_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, shuffle=False
    )

    model = xgb.XGBRegressor(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)

    # Прогноз
    y_pred = model.predict(X_test)

    return model, X_test, y_test, y_pred
