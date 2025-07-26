import numpy as np
from sklearn.metrics import f1_score

def find_best_threshold(y_true, y_proba):
    thresholds = np.linspace(0, 1, 100)
    best_f1 = 0
    best_threshold = 0.5

    for t in thresholds:
        preds = (y_proba > t).astype(int)
        score = f1_score(y_true, preds)
        if score > best_f1:
            best_f1 = score
            best_threshold = t

    return best_threshold, best_f1
