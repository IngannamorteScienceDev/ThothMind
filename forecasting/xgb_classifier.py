import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split

def train_classifier(df: pd.DataFrame, target_column: str = "target_up_5d"):
    df = df.copy()
    X = df.drop(columns=["Date", "ticker", "target_return_5d", target_column])
    y = df[target_column]

    X_train, X_test, y_train, y_test = train_test_split(X, y, shuffle=False, test_size=0.2)

    model = xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.01,
        max_depth=3,
        subsample=0.8,
        random_state=42,
        use_label_encoder=False,
        eval_metric="logloss"
    )
    model.fit(X_train, y_train)

    y_proba = model.predict_proba(X_test)[:, 1]  # Вероятность "вверх"
    return model, X_test, y_test, y_proba
