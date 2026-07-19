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


def unresolved_paths(value: object, prefix: str = "") -> list[str]:
    """Return explicit unresolved/fail-closed configuration paths."""
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(unresolved_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(unresolved_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and value in {
        "unresolved",
        "blocks-run",
        "unresolved-scientific-protocol",
    }:
        paths.append(prefix)
    return paths


def require_scientifically_resolved(config: BenchmarkConfig) -> None:
    unresolved = unresolved_paths(config.raw)
    if unresolved:
        raise ValueError("scientific configuration unresolved: " + ", ".join(unresolved))
