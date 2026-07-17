from __future__ import annotations

import numpy as np
import numpy.typing as npt


def healthy_quantile(values: npt.NDArray[np.float64], quantile: float) -> float:
    if not 0 < quantile < 1:
        raise ValueError("quantile must be between zero and one")
    return float(np.quantile(values, quantile))
