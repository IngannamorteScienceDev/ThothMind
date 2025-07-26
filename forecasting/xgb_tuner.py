import pandas as pd
from sklearn.model_selection import GridSearchCV
from xgboost import XGBRegressor
from sklearn.metrics import make_scorer, mean_squared_error
import numpy as np

def tune_xgb_model(df_feat: pd.DataFrame,
                   learning_rates, max_depths, estimators, subsamples):
    df_feat = df_feat.copy()
    feature_cols = [
        "return_1d", "return_5d", "return_20d",
        "SMA_5", "SMA_20", "SMA_50",
        "volatility_5d", "volatility_20d",
        "lag_1", "lag_5", "lag_20"
    ]
    X = df_feat[feature_cols]
    y = df_feat["target_return_5d"]

    param_grid = {
        "learning_rate": learning_rates,
        "max_depth": max_depths,
        "n_estimators": estimators,
        "subsample": subsamples
    }

    model = XGBRegressor(random_state=42, verbosity=0)
    scorer = make_scorer(mean_squared_error, greater_is_better=False)
    grid = GridSearchCV(model, param_grid, cv=3, scoring=scorer, n_jobs=-1)
    grid.fit(X, y)

    best_params = grid.best_params_
    best_score = np.sqrt(-grid.best_score_)

    # Вся история
    results_df = pd.DataFrame(grid.cv_results_)
    results_df["rmse"] = np.sqrt(-results_df["mean_test_score"])
    results_df = results_df[[
        "param_learning_rate", "param_max_depth", "param_n_estimators",
        "param_subsample", "rmse"
    ]]
    results_df.columns = ["learning_rate", "max_depth", "n_estimators", "subsample", "rmse"]

    return best_params, best_score, results_df
