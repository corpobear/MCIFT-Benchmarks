from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.stats import kurtosis


def rms(values: npt.NDArray[np.float64]) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def peak_to_peak(values: npt.NDArray[np.float64]) -> float:
    return float(np.ptp(values))


def crest_factor(values: npt.NDArray[np.float64]) -> float:
    denominator = rms(values)
    return float(np.max(np.abs(values)) / denominator) if denominator else 0.0


def sample_kurtosis(values: npt.NDArray[np.float64]) -> float:
    return float(kurtosis(values, fisher=False, bias=False))


def spectral_entropy(values: npt.NDArray[np.float64]) -> float:
    power = np.abs(np.fft.rfft(values)) ** 2
    total = power.sum()
    if total == 0:
        return 0.0
    probabilities = power / total
    probabilities = probabilities[probabilities > 0]
    return float(-np.sum(probabilities * np.log2(probabilities)))


def band_energy(values: npt.NDArray[np.float64], low_bin: int, high_bin: int) -> float:
    power = np.abs(np.fft.rfft(values)) ** 2
    return float(power[low_bin:high_bin].sum())


def rolling_zscore(values: npt.NDArray[np.float64], window: int) -> npt.NDArray[np.float64]:
    if values.ndim != 1 or window < 2:
        raise ValueError("rolling z-score requires a vector and window >= 2")
    output = np.full(values.shape, np.nan, dtype=np.float64)
    for index in range(window - 1, len(values)):
        sample = values[index - window + 1 : index + 1]
        deviation = sample.std(ddof=1)
        output[index] = 0.0 if deviation == 0 else (values[index] - sample.mean()) / deviation
    return output


def ewma(values: npt.NDArray[np.float64], alpha: float) -> npt.NDArray[np.float64]:
    if values.ndim != 1 or not 0 < alpha <= 1:
        raise ValueError("EWMA requires a vector and 0 < alpha <= 1")
    output = np.empty_like(values, dtype=np.float64)
    if len(values) == 0:
        return output
    output[0] = values[0]
    for index in range(1, len(values)):
        output[index] = alpha * values[index] + (1 - alpha) * output[index - 1]
    return output


def pca_reconstruction_error(
    reference: npt.NDArray[np.float64],
    evaluation: npt.NDArray[np.float64],
    components: int,
) -> npt.NDArray[np.float64]:
    if reference.ndim != 2 or evaluation.ndim != 2 or reference.shape[1] != evaluation.shape[1]:
        raise ValueError("PCA inputs must be matrices with equal feature counts")
    if not 1 <= components < reference.shape[1]:
        raise ValueError("components must be between one and feature_count - 1")
    mean = reference.mean(axis=0)
    _, _, right = np.linalg.svd(reference - mean, full_matrices=False)
    basis = right[:components]
    centered = evaluation - mean
    reconstruction = (centered @ basis.T) @ basis
    return np.asarray(np.mean(np.square(centered - reconstruction), axis=1), dtype=np.float64)
