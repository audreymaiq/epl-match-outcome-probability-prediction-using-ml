"""A smoothed training-only class-frequency reference for probability forecasts."""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin


class FrequencyClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, smoothing=1.0):
        self.smoothing = smoothing

    def fit(self, X, y):
        counts = np.bincount(np.asarray(y, dtype=int), minlength=3) + self.smoothing
        self.probabilities_ = counts / counts.sum()
        self.classes_ = np.array([0, 1, 2])
        return self

    def predict_proba(self, X):
        return np.tile(self.probabilities_, (len(X), 1))
