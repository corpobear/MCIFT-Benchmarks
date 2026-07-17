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
