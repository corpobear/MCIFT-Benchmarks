from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class BenchmarkConfig:
    path: Path
    raw: dict[str, Any]
    sha256: str


def load_config(path: str | Path) -> BenchmarkConfig:
    config_path = Path(path).resolve()
    payload = config_path.read_bytes()
    raw = yaml.safe_load(payload)
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")
    required = {"benchmark", "dataset", "mcift", "output", "seed"}
    missing = sorted(required - raw.keys())
    if missing:
        raise ValueError(f"missing configuration keys: {', '.join(missing)}")
    return BenchmarkConfig(config_path, raw, hashlib.sha256(payload).hexdigest())
