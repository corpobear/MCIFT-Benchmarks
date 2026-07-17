from __future__ import annotations

import numpy as np
import numpy.typing as npt


def stable_warning(mask: npt.NDArray[np.bool_], consecutive: int) -> int | None:
    if consecutive < 1:
        raise ValueError("consecutive must be positive")
    run = 0
    for index, active in enumerate(mask):
        run = run + 1 if active else 0
        if run >= consecutive:
            return index - consecutive + 1
    return None
