import shap
import matplotlib.pyplot as plt

def explain_xgb_model(model, X_test):
    """
    Строит SHAP-графики для XGBoost модели
    """
    explainer = shap.Explainer(model)
    shap_values = explainer(X_test)

    # Summary plot (bar)
    print("📊 Feature importance (SHAP):")
    shap.plots.bar(shap_values)

    # Summary plot (dot)
    shap.summary_plot(shap_values, X_test)

    # Dependence plot по ключевому признаку
    top_feature = X_test.columns[0]
    shap.dependence_plot(top_feature, shap_values.values, X_test)

    # (Optional) Force plot — работает в Jupyter
    # shap.plots.force(shap_values[0])
