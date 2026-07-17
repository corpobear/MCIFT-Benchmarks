from __future__ import annotations

from collections.abc import Mapping

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
