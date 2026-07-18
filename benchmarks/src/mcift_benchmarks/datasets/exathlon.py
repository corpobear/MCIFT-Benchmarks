from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from mcift_benchmarks.storage import blob_client

EXATHLON_DATASET_ID = "exathlon"
EXPECTED_PREFIX = "datasets/exathlon/"
EXCLUDED_APPS = {7, 8}

IDENTITY_FEATURES = (
    "driver_StreamingMetrics_streaming_lastCompletedBatch_processingDelay_value",
    "driver_StreamingMetrics_streaming_lastCompletedBatch_schedulingDelay_value",
    "driver_StreamingMetrics_streaming_lastCompletedBatch_totalDelay_value",
)
DIFFERENCE_FEATURES = (
    "driver_StreamingMetrics_streaming_totalCompletedBatches_value",
    "driver_StreamingMetrics_streaming_totalProcessedRecords_value",
    "driver_StreamingMetrics_streaming_totalReceivedRecords_value",
    "driver_StreamingMetrics_streaming_lastReceivedBatch_records_value",
    "driver_BlockManager_memory_memUsed_MB_value",
    "driver_jvm_heap_used_value",
    "node5_CPU_ALL_Idle%",
    "node6_CPU_ALL_Idle%",
    "node7_CPU_ALL_Idle%",
    "node8_CPU_ALL_Idle%",
)
EXECUTOR_FEATURES = (
    "executor_filesystem_hdfs_write_ops_value",
    "executor_cpuTime_count",
    "executor_runTime_count",
    "executor_shuffleRecordsRead_count",
    "executor_shuffleRecordsWritten_count",
    "jvm_heap_used_value",
)


@dataclass(frozen=True)
class Trace:
    name: str
    trace_type: int
    timestamps: npt.NDArray[np.int64]
    values: npt.NDArray[np.float64]


def _normalized_column(name: str) -> str:
    if "StreamingMetrics" not in name:
        return name
    return name.replace(f"{'_'.join(name.split('_')[1:10])}_", "")


def load_manifest(manifest_uri: str) -> tuple[list[dict[str, object]], str, str]:
    payload = bytes(blob_client(manifest_uri).download_blob().readall())
    manifest = json.loads(payload)
    entries = manifest.get("files", [])
    if not isinstance(entries, list) or len(entries) < 94:
        raise ValueError("Exathlon aggregate manifest is incomplete")
    base_uri = manifest_uri.rsplit("/", 2)[0]
    return entries, hashlib.sha256(payload).hexdigest(), base_uri


def _read_zip_csv(uris: list[str]) -> tuple[str, pd.DataFrame]:
    payload = b"".join(
        bytes(blob_client(uri).download_blob(max_concurrency=4).readall()) for uri in uris
    )
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [
            member for member in archive.infolist() if member.filename.lower().endswith(".csv")
        ]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in archive ending {uris[-1]}")
        member = members[0]
        if len(uris) > 1:
            local_header = payload.find(b"PK\x03\x04")
            if local_header < 0:
                raise ValueError(f"split ZIP local header not found for {uris[-1]}")
            member.header_offset = local_header
        name = member.filename
        with archive.open(member) as handle:
            header = pd.read_csv(handle, nrows=0).columns.tolist()
        normalized = {_normalized_column(column): column for column in header}
        wanted = ["t", *IDENTITY_FEATURES, *DIFFERENCE_FEATURES]
        executor_raw = [
            f"{slot}_{feature}" for feature in EXECUTOR_FEATURES for slot in range(1, 6)
        ]
        wanted.extend(executor_raw)
        missing = sorted(set(wanted) - set(normalized))
        if missing:
            raise ValueError(f"missing official Exathlon features in {name}: {missing}")
        raw_columns = [normalized[column] for column in wanted]
        with archive.open(member) as handle:
            frame = pd.read_csv(handle, usecols=raw_columns)
        frame = frame.rename(
            columns={raw: normalized_name for normalized_name, raw in normalized.items()}
        )
    return name.rsplit("/", 1)[-1].removesuffix(".csv"), frame


def load_ground_truth(uri: str) -> pd.DataFrame:
    _, frame = _read_ground_truth_zip(uri)
    return frame


def _read_ground_truth_zip(uri: str) -> tuple[str, pd.DataFrame]:
    payload = bytes(blob_client(uri).download_blob().readall())
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = archive.namelist()[0]
        with archive.open(name) as handle:
            frame = pd.read_csv(handle)
    return name, frame


def load_trace(uris: list[str]) -> Trace:
    name, frame = _read_zip_csv(uris)
    timestamps = frame.pop("t").to_numpy(dtype=np.int64)
    output: dict[str, pd.Series[float]] = {}
    for feature in IDENTITY_FEATURES:
        output[feature] = frame[feature].astype(float)
    for feature in DIFFERENCE_FEATURES:
        output[f"diff_{feature}"] = frame[feature].astype(float).diff()
    for feature in EXECUTOR_FEATURES:
        group = frame[[f"{slot}_{feature}" for slot in range(1, 6)]].replace(-1, np.nan)
        output[f"diff_avg_{feature}"] = group.mean(axis=1).fillna(-1).diff()
    values = pd.DataFrame(output).iloc[1:].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    trace_type = int(name.split("_")[1])
    return Trace(
        name=name,
        trace_type=trace_type,
        timestamps=np.asarray(timestamps[1:], dtype=np.int64),
        values=np.asarray(values.to_numpy(dtype=np.float64), dtype=np.float64),
    )


def scoped_entries(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for entry in entries:
        original = str(entry["original_path"])
        if original.endswith("ground_truth.zip"):
            selected.append(entry)
            continue
        app = int(original.split("/")[2].removeprefix("app"))
        if app not in EXCLUDED_APPS:
            selected.append(entry)
    return selected
