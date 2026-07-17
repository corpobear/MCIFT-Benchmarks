import numpy as np
import pytest

from mcift_benchmarks.evaluation.early_warning import stable_warning
from mcift_benchmarks.features.conventional import crest_factor, peak_to_peak, rms
from mcift_benchmarks.features.mcift_adapter import MciftAdapter


def test_conventional_features_on_synthetic_array() -> None:
    values = np.array([-1.0, 0.0, 1.0], dtype=np.float64)
    assert rms(values) == pytest.approx(np.sqrt(2 / 3))
    assert peak_to_peak(values) == 2.0
    assert crest_factor(values) == pytest.approx(np.sqrt(3 / 2))


def test_stable_warning_uses_first_consecutive_run() -> None:
    mask = np.array([False, True, False, True, True, True], dtype=np.bool_)
    assert stable_warning(mask, 3) == 3


def test_mcift_adapter_fails_closed() -> None:
    with pytest.raises(NotImplementedError, match="refusing to fabricate"):
        MciftAdapter().transform(np.ones(3), {})
