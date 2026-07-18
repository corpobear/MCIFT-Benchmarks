from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


class MciftAdapter:
    """Contract for a reviewed theory-to-observable mapping."""

    def transform(
        self, values: npt.NDArray[np.float64], context: Mapping[str, object]
    ) -> npt.NDArray[np.float64]:
        del values, context
        # TODO(science): map reviewed MCIFT equations to IMS/Exathlon observables,
        # including units, topology, boundary conditions, and falsification rules.
        raise NotImplementedError(
            "MCIFT mapping is unresolved; refusing to fabricate a benchmark feature"
        )


@dataclass(frozen=True)
class ExchangeObservables:
    information: npt.NDArray[np.float64]
    angular_frequency: npt.NDArray[np.float64]
    phase: npt.NDArray[np.float64]
    pairwise_exchange: npt.NDArray[np.float64]
    mean_pairwise_exchange: float
    densification: float


@dataclass(frozen=True)
class InferredExchangeAdapter:
    """Observable mapping inferred from the MCIFT pairwise exchange toy law.

    The equation is source-derived; mapping sensor/telemetry channels to information
    points and choosing observable summaries is an explicit benchmark proposal.
    """

    sigma_information: float
    sigma_angular_frequency: float
    coupling: float = 1.0
    densification_eta: float = 1.0

    def transform_window(
        self,
        values: npt.NDArray[np.float64],
        sampling_rate_hz: float,
        reference_scale: npt.NDArray[np.float64],
    ) -> ExchangeObservables:
        if values.ndim != 2 or values.shape[0] < 4 or values.shape[1] < 2:
            raise ValueError("exchange adapter requires samples x channels with at least 4 x 2")
        if (
            sampling_rate_hz <= 0
            or self.sigma_information <= 0
            or self.sigma_angular_frequency <= 0
        ):
            raise ValueError("sampling rate and mismatch scales must be positive")
        if (
            reference_scale.shape != (values.shape[1],)
            or not np.all(np.isfinite(reference_scale))
            or np.any(reference_scale <= 0)
        ):
            raise ValueError("one positive finite reference scale is required per channel")

        centered = (values - values.mean(axis=0)) / reference_scale
        information = np.log(np.sqrt(np.mean(np.square(centered), axis=0)) + np.finfo(float).eps)
        spectrum = np.fft.rfft(centered, axis=0)
        frequencies = np.fft.rfftfreq(values.shape[0], d=1.0 / sampling_rate_hz)
        power = np.square(np.abs(spectrum))
        if len(frequencies) > 1:
            power[0, :] = 0.0
        totals = power.sum(axis=0)
        angular_frequency = np.divide(
            (2.0 * np.pi * frequencies[:, None] * power).sum(axis=0),
            totals,
            out=np.zeros(values.shape[1], dtype=np.float64),
            where=totals > 0,
        )

        shared_bin = int(np.argmax(power.sum(axis=1)))
        phase = np.angle(spectrum[shared_bin, :]).astype(np.float64)
        channel_count = values.shape[1]
        exchange = np.zeros((channel_count, channel_count), dtype=np.float64)
        for left in range(channel_count):
            for right in range(left + 1, channel_count):
                information_term = np.exp(
                    -((information[left] - information[right]) ** 2)
                    / (2.0 * self.sigma_information**2)
                )
                frequency_term = np.exp(
                    -((angular_frequency[left] - angular_frequency[right]) ** 2)
                    / (2.0 * self.sigma_angular_frequency**2)
                )
                phase_term = np.cos(phase[left] - phase[right]) ** 2
                value = self.coupling * information_term * frequency_term * phase_term
                exchange[left, right] = value
                exchange[right, left] = value
        upper = exchange[np.triu_indices(channel_count, k=1)]
        mean_exchange = float(upper.mean())
        return ExchangeObservables(
            information=np.asarray(information, dtype=np.float64),
            angular_frequency=np.asarray(angular_frequency, dtype=np.float64),
            phase=phase,
            pairwise_exchange=exchange,
            mean_pairwise_exchange=mean_exchange,
            densification=float(np.exp(self.densification_eta * mean_exchange)),
        )
