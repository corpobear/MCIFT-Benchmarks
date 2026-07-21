from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

IMS_DATASET_ID = "nasa-ims-bearing"
EXPECTED_PREFIX = "datasets/ims/"
_STAMP = re.compile(r"^(\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2})(?:\.[A-Za-z0-9]+)?$")


@dataclass(frozen=True)
class IMSFile:
    path: Path
    relative_path: str
    timestamp: str
    timestamp_utc: str
    size_bytes: int
    sha256: str

    def manifest_record(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("path")
        return value


def timestamp_from_name(path: Path) -> datetime:
    match = _STAMP.fullmatch(path.name)
    if not match:
        raise ValueError(f"not an IMS recording filename: {path.name}")
    parsed = datetime.strptime(match.group(1), "%Y.%m.%d.%H.%M.%S")
    return parsed.replace(tzinfo=UTC)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_ims_files(
    root: Path, *, limit: int | None = None
) -> tuple[list[IMSFile], dict[str, float]]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(
            f"IMS dataset root not found: {root}. Download Test Set 2 from the official NASA "
            "IMS Bearings catalog, extract it locally, and pass --dataset-root or IMS_DATASET_ROOT."
        )
    discovery_start = time.perf_counter()
    candidates: list[tuple[datetime, Path]] = []
    for path in root.rglob("*"):
        if not path.is_file() or not _STAMP.fullmatch(path.name):
            continue
        candidates.append((timestamp_from_name(path), path))
    candidates.sort(key=lambda item: (item[0], item[1].as_posix()))
    if not candidates:
        raise ValueError(f"no timestamp-named IMS recordings found below {root}")
    timestamps = [item[0] for item in candidates]
    duplicates = sorted({stamp for stamp in timestamps if timestamps.count(stamp) > 1})
    if duplicates:
        raise ValueError(
            f"duplicate IMS timestamps: {', '.join(d.isoformat() for d in duplicates)}"
        )
    if any(right <= left for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise ValueError("IMS recording chronology is not strictly increasing")
    discovery_seconds = time.perf_counter() - discovery_start
    selected = candidates if limit is None else candidates[:limit]
    hash_start = time.perf_counter()
    files = [
        IMSFile(
            path=path,
            relative_path=path.relative_to(root).as_posix(),
            timestamp=stamp.strftime("%Y.%m.%d.%H.%M.%S"),
            timestamp_utc=stamp.isoformat().replace("+00:00", "Z"),
            size_bytes=path.stat().st_size,
            sha256=sha256_file(path),
        )
        for stamp, path in selected
    ]
    return files, {
        "dataset_discovery_seconds": discovery_seconds,
        "dataset_hashing_seconds": time.perf_counter() - hash_start,
    }


def load_recording(
    file: IMSFile, *, channels: int, sampling_rate_hz: float
) -> npt.NDArray[np.float64]:
    from mcift.adapters.ims import load_ims_file

    return load_ims_file(
        file.path,
        expected_channel_count=channels,
        sampling_rate_hz=sampling_rate_hz,
    ).values


def iter_recordings(
    files: list[IMSFile], *, channels: int, sampling_rate_hz: float
) -> Iterator[tuple[IMSFile, npt.NDArray[np.float64]]]:
    for file in files:
        yield file, load_recording(file, channels=channels, sampling_rate_hz=sampling_rate_hz)
