import pandas as pd
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.metrics import make_scorer, mean_squared_error

def tune_xgb(df: pd.DataFrame, target_column: str = "target_return_5d"):
    """
    Подбор гиперпараметров XGBoost через GridSearchCV с TimeSeriesSplit
    """
    df = df.copy()
    X = df.drop(columns=["Date", "ticker", target_column])
    y = df[target_column]

    # Разделение по времени
    tscv = TimeSeriesSplit(n_splits=3)

    model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42)

    param_grid = {
        "n_estimators": [50, 100],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.01, 0.1, 0.2],
        "subsample": [0.8, 1.0],
    }

    scorer = make_scorer(mean_squared_error, greater_is_better=False)

    grid = GridSearchCV(
        model,
        param_grid,
        cv=tscv,
        scoring=scorer,
        n_jobs=-1,
        verbose=1,
    )

    grid.fit(X, y)

    best_model = grid.best_estimator_
    best_params = grid.best_params_
    best_score = grid.best_score_

    return best_model, best_params, -best_score  # RMSE положительный
