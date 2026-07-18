import numpy as np
import pytest

from mcift_benchmarks.evaluation.early_warning import stable_warning
from mcift_benchmarks.features.conventional import (
    crest_factor,
    ewma,
    pca_reconstruction_error,
    peak_to_peak,
    rms,
    rolling_zscore,
)
from mcift_benchmarks.features.mcift_adapter import InferredExchangeAdapter, MciftAdapter


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


def test_telemetry_baselines_on_synthetic_arrays() -> None:
    values = np.array([1.0, 1.0, 1.0, 3.0])
    assert np.isnan(rolling_zscore(values, 3)[:2]).all()
    assert ewma(values, 0.5).tolist() == [1.0, 1.0, 1.0, 2.0]
    reference = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])
    error = pca_reconstruction_error(reference, np.array([[1.0, 2.0]]), 1)
    assert error[0] == pytest.approx(0.25)


def test_inferred_exchange_is_symmetric_for_aligned_channels() -> None:
    time = np.arange(128) / 128.0
    signal = np.sin(2 * np.pi * 8 * time)
    values = np.column_stack([signal, signal])
    result = InferredExchangeAdapter(1.0, 1.0).transform_window(
        values, 128.0, np.ones(2, dtype=np.float64)
    )
    assert result.pairwise_exchange[0, 1] == pytest.approx(1.0)
    assert result.mean_pairwise_exchange == pytest.approx(1.0)
    assert result.densification == pytest.approx(np.e)
