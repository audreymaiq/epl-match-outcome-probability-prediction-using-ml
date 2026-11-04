import numpy as np
import pytest
from ml.evaluation.drift import distribution_shift


def test_identical_distributions_have_zero_shift():
    values = np.arange(100)
    assert distribution_shift(values, values)["psi"] == pytest.approx(0)


def test_constant_reference_detects_unseen_values():
    assert distribution_shift(np.zeros(100), np.ones(100))["psi"] > 1


def test_invalid_features_and_binning_are_rejected():
    with pytest.raises(ValueError, match="finite"):
        distribution_shift([1, 2], [np.nan])
    with pytest.raises(ValueError, match="bins"):
        distribution_shift([1], [2], bins=1)
