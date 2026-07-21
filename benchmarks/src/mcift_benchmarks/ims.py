from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import psutil
import yaml
from packaging.version import Version

from mcift_benchmarks.datasets.ims import IMSFile, discover_ims_files, load_recording
from mcift_benchmarks.evaluation.ims_metrics import (
    calibrate_baselines,
    evaluate_baseline,
    false_positive_metrics,
    localization_metrics,
    warning_timing,
)

EXPECTED_GATES = (
    "global_deformation",
    "local_relationship_damage",
    "persistence",
    "directional_consistency",
    "robust_progression",
    "conventional_vibration_agreement",
)
DISCLAIMER = (
    "The benchmark evaluates the predictive and anomaly-detection behaviour of a frozen "
    "software method. It does not validate MCIFT as a physical theory."
)


@dataclass(frozen=True)
class Protocol:
    path: Path
    raw: dict[str, Any]
    sha256: str

    @property
    def dataset(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.raw["dataset"])

    @property
    def split(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.raw["split"])

    @property
    def mcift(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.raw["mcift"])


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_jsonable(value), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _hash_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_protocol(path: Path) -> Protocol:
    payload = path.resolve().read_bytes()
    raw = yaml.safe_load(payload)
    if not isinstance(raw, dict):
        raise ValueError("protocol root must be a mapping")
    required = {"benchmark", "dataset", "split", "mcift", "analysis", "random_seed"}
    missing = sorted(required - raw.keys())
    if missing:
        raise ValueError(f"protocol missing keys: {', '.join(missing)}")
    dataset_required = {
        "dataset_id",
        "dataset_variant",
        "sampling_rate_hz",
        "samples_per_recording",
        "channel_names",
        "channel_units",
        "timestamp_rule",
    }
    missing = sorted(dataset_required - raw["dataset"].keys())
    if missing:
        raise ValueError(f"protocol dataset missing keys: {', '.join(missing)}")
    split_required = {
        "reference_range",
        "calibration_range",
        "healthy_holdout_range",
        "evaluation_range",
    }
    missing = sorted(split_required - raw["split"].keys())
    if missing:
        raise ValueError(f"protocol split missing keys: {', '.join(missing)}")
    return Protocol(path.resolve(), raw, hashlib.sha256(payload).hexdigest())


def install_mcift(mcift_repo: Path | None) -> None:
    source: Path | None = None
    if mcift_repo is not None:
        source = mcift_repo.expanduser().resolve()
    else:
        repository_root = Path(__file__).resolve().parents[3]
        sibling_candidates = (
            (Path.cwd() / "../MCIFT").resolve(),
            (repository_root.parent / "MCIFT").resolve(),
        )
        source = next(
            (
                candidate
                for candidate in sibling_candidates
                if (candidate / "pyproject.toml").is_file()
            ),
            None,
        )
    if source is not None:
        if not (source / "pyproject.toml").is_file():
            raise FileNotFoundError(f"MCIFT checkout is invalid: {source}")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(source)], check=True)
        return
    if importlib.util.find_spec("mcift") is None:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "git+https://github.com/corpobear/MCIFT.git",
            ],
            check=True,
        )


def validate_mcift(protocol: Protocol) -> dict[str, Any]:
    import mcift
    from mcift.profiles import IMS_SIX_GATE_PROFILE_ID, VIBRATION_PROFILE_ID

    required = Version(str(protocol.mcift["minimum_version"]))
    installed = Version(mcift.__version__)
    if installed < required:
        raise RuntimeError(f"MCIFT {required} or newer required; installed {installed}")
    if IMS_SIX_GATE_PROFILE_ID != "mcift.gates.ims-six-gate.v1":
        raise RuntimeError("installed MCIFT lacks the required six-gate profile")
    if VIBRATION_PROFILE_ID != "mcift.exchange.vibration.v1":
        raise RuntimeError("installed MCIFT lacks the required vibration profile")
    if protocol.mcift["gate_profile"] != IMS_SIX_GATE_PROFILE_ID:
        raise ValueError("protocol must use mcift.gates.ims-six-gate.v1")
    if protocol.mcift["processing_profile"] != VIBRATION_PROFILE_ID:
        raise ValueError("protocol must use mcift.exchange.vibration.v1")
    package_root = Path(mcift.__file__).resolve().parents[2]
    return {
        "version": mcift.__version__,
        "git_commit": _git_value(package_root, ["rev-parse", "HEAD"]),
        "package_path": str(package_root),
        "processing_profile": VIBRATION_PROFILE_ID,
        "gate_profile": IMS_SIX_GATE_PROFILE_ID,
    }


def _git_value(root: Path, args: list[str]) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _memory_facts() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    cpu_name = platform.processor()
    if not cpu_name and platform.system() == "Windows":
        cpu_name = os.environ.get("PROCESSOR_IDENTIFIER", "unknown")
    return {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "operating_system": platform.platform(),
        "cpu_model": cpu_name or "unknown",
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "available_ram_bytes": memory.available,
        "total_ram_bytes": memory.total,
    }


def _ranges(protocol: Protocol, count: int, limited: bool) -> dict[str, tuple[int, int]]:
    if limited:
        if count < 8:
            raise ValueError("limited smoke run requires at least 8 recordings")
        cuts = [0, max(2, count // 5), max(4, count // 2), max(6, 3 * count // 5), count]
        ranges = {
            "reference": (cuts[0], cuts[1]),
            "calibration": (cuts[1], cuts[2]),
            "healthy_holdout": (cuts[2], cuts[3]),
            "evaluation": (cuts[3], cuts[4]),
        }
    else:
        ranges = {}
        for name in ("reference", "calibration", "healthy_holdout", "evaluation"):
            start, end = protocol.split[f"{name}_range"]
            ranges[name] = (int(start), count if end is None else int(end))
    ordered = [
        ranges[name] for name in ("reference", "calibration", "healthy_holdout", "evaluation")
    ]
    if any(start < 0 or end <= start or end > count for start, end in ordered):
        raise ValueError(f"split ranges invalid for {count} recordings: {ranges}")
    flattened = [set(range(start, end)) for start, end in ordered]
    if any(flattened[i] & flattened[j] for i in range(4) for j in range(i + 1, 4)):
        raise ValueError("split ranges overlap")
    if any(ordered[index][1] > ordered[index + 1][0] for index in range(3)):
        raise ValueError("split ranges are not chronological")
    return ranges


def split_manifest(files: list[IMSFile], ranges: dict[str, tuple[int, int]]) -> dict[str, Any]:
    result: dict[str, Any] = {"ranges_are_half_open": True, "splits": {}}
    for name, (start, end) in ranges.items():
        result["splits"][name] = {
            "start_index": start,
            "end_index_exclusive": end,
            "count": end - start,
            "first_timestamp": files[start].timestamp_utc,
            "last_timestamp": files[end - 1].timestamp_utc,
            "file_hashes": [item.sha256 for item in files[start:end]],
        }
    return result


def _load_many(
    files: list[IMSFile], protocol: Protocol
) -> tuple[list[npt.NDArray[np.float64]], float]:
    start = time.perf_counter()
    channels = len(protocol.dataset["channel_names"])
    rate = float(protocol.dataset["sampling_rate_hz"])
    windows = [load_recording(file, channels=channels, sampling_rate_hz=rate) for file in files]
    expected = int(protocol.dataset["samples_per_recording"])
    if any(window.shape != (expected, channels) for window in windows):
        raise ValueError(f"recordings must all have shape ({expected}, {channels})")
    return windows, time.perf_counter() - start


def _validate_recordings(files: list[IMSFile], protocol: Protocol) -> float:
    started = time.perf_counter()
    channels = len(protocol.dataset["channel_names"])
    samples = int(protocol.dataset["samples_per_recording"])
    rate = float(protocol.dataset["sampling_rate_hz"])
    for index, file in enumerate(files, start=1):
        window = load_recording(file, channels=channels, sampling_rate_hz=rate)
        if window.shape != (samples, channels):
            raise ValueError(
                f"recording {file.relative_path} has shape {window.shape}; "
                f"expected ({samples}, {channels})"
            )
        if index % 100 == 0 or index == len(files):
            print(f"validated {index} / {len(files)} IMS recordings")
    return time.perf_counter() - started


def _extract_result(
    result: Any, file: IMSFile, sequence_index: int, source_index: int
) -> dict[str, Any]:
    gates = {gate.name: gate for gate in result.gate_results}
    if tuple(gate.name for gate in result.gate_results) != EXPECTED_GATES:
        raise RuntimeError("MCIFT did not return the required ordered six gates")
    upper = np.triu_indices(result.edge_residuals.shape[0], k=1)
    confidence = dict(result.confidence_evidence)
    conventional = result.conventional_vibration
    features = {feature.feature_name: feature for feature in conventional.features}
    g6 = gates["conventional_vibration_agreement"]
    evidence = dict(g6.evidence)
    triggered_features = list(evidence.get("triggered_features", ()))
    row: dict[str, Any] = {
        "timestamp": file.timestamp,
        "timestamp_utc": file.timestamp_utc,
        "relative_filename": file.relative_path,
        "file_sha256": file.sha256,
        "sequence_index": sequence_index,
        "source_index": source_index,
        "global_exchange_score": float(result.global_exchange_score),
        "maximum_local_edge_score": float(np.max(result.edge_residuals[upper])),
        "candidate_nodes": list(result.candidate_nodes),
        "candidate_edges": [list(edge) for edge in result.candidate_edges],
        "final_decision": result.final_decision,
        "passed_gate_count": confidence["passed_gate_count"],
        "available_gate_count": confidence["available_gate_count"],
        "screening_positive": bool(confidence["screening_positive"]),
        "persistent_mcift_warning": bool(confidence["persistent_mcift_warning"]),
        "high_confidence_ims_warning": confidence["high_confidence_ims_warning"] is True,
        "high_confidence_available": confidence["high_confidence_ims_warning"] is not None,
        "g6_triggered_features": triggered_features,
        "g6_triggered_channels": list(evidence.get("triggered_channels", ())),
        "g6_same_channel_multi_feature_agreement": bool(
            evidence.get("same_channel_multi_feature_agreement", False)
        ),
        "g6_at_least_two_triggered_features": len(triggered_features) >= 2,
        "g6_rms_only": "centered_rms" in triggered_features,
        "g6_kurtosis_only": "excess_kurtosis" in triggered_features,
        "g6_crest_factor_only": "crest_factor" in triggered_features,
        "g6_values_by_feature_and_channel": evidence.get("values_by_feature_and_channel", {}),
        "g6_thresholds_by_feature_and_channel": evidence.get(
            "thresholds_by_feature_and_channel", {}
        ),
        "warnings": list(result.warnings),
        "diagnostics": list(result.diagnostics),
    }
    for name, gate in gates.items():
        prefix = f"gate_{name}"
        row[f"{prefix}_available"] = gate.available
        row[f"{prefix}_passed"] = gate.passed
        row[f"{prefix}_value"] = gate.value
        row[f"{prefix}_threshold"] = gate.threshold
        row[f"{prefix}_evidence"] = dict(gate.evidence)
    row["conventional_feature_positive_flags"] = {
        name: feature.positive_flags.tolist() for name, feature in features.items()
    }
    return cast(dict[str, Any], _jsonable(row))


def _write_rows(path_jsonl: Path, path_csv: Path, rows: list[dict[str, Any]]) -> None:
    path_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with path_jsonl.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    if not rows:
        path_csv.write_text("", encoding="utf-8")
        return
    with path_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, sort_keys=True)
                    if isinstance(value, dict | list)
                    else value
                    for key, value in row.items()
                }
            )


def _evaluate_sequence(
    monitor: Any,
    files: list[IMSFile],
    source_indices: list[int],
    protocol: Protocol,
    *,
    window_transform: Callable[[npt.NDArray[np.float64], int], npt.NDArray[np.float64]]
    | None = None,
    sequence_indices: list[int] | None = None,
    append_path: Path | None = None,
    resume: bool = False,
    progress_path: Path | None = None,
    phase: str = "evaluation",
) -> tuple[list[dict[str, Any]], float]:
    from mcift import MCIFTHistory

    history = MCIFTHistory(maxlen=int(protocol.mcift["history_maxlen"]))
    channels = len(protocol.dataset["channel_names"])
    rate = float(protocol.dataset["sampling_rate_hz"])
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    completed = 0
    if resume and append_path is not None and append_path.is_file():
        rows = [
            json.loads(line)
            for line in append_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(rows) > len(files):
            raise ValueError("resume results contain more rows than the evaluation split")
        for offset, row in enumerate(rows):
            file = files[offset]
            source_index = source_indices[offset]
            if row.get("file_sha256") != file.sha256 or row.get("source_index") != source_index:
                raise ValueError("resume results do not match the frozen evaluation sequence")
            window = load_recording(file, channels=channels, sampling_rate_hz=rate)
            if window_transform is not None:
                window = window_transform(window, offset)
            sequence_index = sequence_indices[offset] if sequence_indices else source_index
            _, history = monitor.evaluate_with_history(
                window, history=history, sequence_index=sequence_index
            )
        completed = len(rows)
    append_stream = None
    if append_path is not None:
        append_path.parent.mkdir(parents=True, exist_ok=True)
        append_stream = append_path.open("a" if completed else "w", encoding="utf-8", newline="\n")
    total = len(files)
    if progress_path is not None:
        _atomic_json(
            progress_path,
            {
                "phase": phase,
                "status": "running",
                "processed": completed,
                "total": total,
                "percent": completed / total * 100.0 if total else 100.0,
                "elapsed_seconds": 0.0,
                "estimated_remaining_seconds": None,
                "updated_at_utc": datetime.now(UTC).isoformat(),
            },
        )
    try:
        for offset in range(completed, total):
            file = files[offset]
            source_index = source_indices[offset]
            window = load_recording(file, channels=channels, sampling_rate_hz=rate)
            if window_transform is not None:
                window = window_transform(window, offset)
            sequence_index = sequence_indices[offset] if sequence_indices else source_index
            result, history = monitor.evaluate_with_history(
                window, history=history, sequence_index=sequence_index
            )
            row = _extract_result(result, file, sequence_index, source_index)
            row["evaluation_elapsed_seconds"] = time.perf_counter() - started
            rows.append(row)
            if append_stream is not None:
                append_stream.write(json.dumps(row, sort_keys=True) + "\n")
                append_stream.flush()
                os.fsync(append_stream.fileno())
            elapsed = time.perf_counter() - started
            processed_now = offset + 1 - completed
            rate_now = processed_now / elapsed if elapsed else 0.0
            remaining = (total - offset - 1) / rate_now if rate_now else 0.0
            if progress_path is not None and (
                offset == completed or (offset + 1) % 10 == 0 or offset + 1 == total
            ):
                _atomic_json(
                    progress_path,
                    {
                        "phase": phase,
                        "status": "complete" if offset + 1 == total else "running",
                        "processed": offset + 1,
                        "total": total,
                        "percent": (offset + 1) / total * 100.0,
                        "elapsed_seconds": elapsed,
                        "estimated_remaining_seconds": remaining,
                        "recordings_per_second": rate_now,
                        "resident_memory_bytes": psutil.Process().memory_info().rss,
                        "updated_at_utc": datetime.now(UTC).isoformat(),
                    },
                )
            if (offset + 1) % 100 == 0 or offset + 1 == total:
                rss = psutil.Process().memory_info().rss
                print(
                    f"processed {offset + 1} / {total}; elapsed {elapsed:.1f}s; "
                    f"estimated remaining {remaining:.1f}s; "
                    f"current RSS {rss / 2**20:.1f} MiB"
                )
    finally:
        if append_stream is not None:
            append_stream.close()
    return rows, time.perf_counter() - started


def _time_permutation_rows(
    monitor: Any,
    files: list[IMSFile],
    source_indices: list[int],
    protocol: Protocol,
    seed: int,
    progress_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[list[int]], float]:
    channels = len(protocol.dataset["channel_names"])
    rng = np.random.default_rng(seed)
    permutations: list[list[int]] = [
        [int(value) for value in rng.permutation(len(files))] for _ in range(channels)
    ]
    cache: dict[int, npt.NDArray[np.float64]] = {}

    def transform(_: npt.NDArray[np.float64], offset: int) -> npt.NDArray[np.float64]:
        columns = []
        for channel, permutation in enumerate(permutations):
            selected = permutation[offset]
            if selected not in cache:
                cache[selected] = load_recording(
                    files[selected],
                    channels=channels,
                    sampling_rate_hz=float(protocol.dataset["sampling_rate_hz"]),
                )
            columns.append(cache[selected][:, channel])
        result = np.column_stack(columns)
        cache.clear()
        return result

    rows, seconds = _evaluate_sequence(
        monitor,
        files,
        source_indices,
        protocol,
        window_transform=transform,
        sequence_indices=list(range(len(files))),
        progress_path=progress_path,
        phase="control_time_permutation",
    )
    return rows, permutations, seconds


def _baseline_rows(
    files: list[IMSFile],
    source_indices: list[int],
    protocol: Protocol,
    thresholds: dict[str, list[float]],
    split: str,
) -> list[dict[str, Any]]:
    channels = len(protocol.dataset["channel_names"])
    rate = float(protocol.dataset["sampling_rate_hz"])
    names = protocol.dataset["channel_names"]
    rows = []
    for file, index in zip(files, source_indices, strict=True):
        result = evaluate_baseline(
            load_recording(file, channels=channels, sampling_rate_hz=rate), thresholds
        )
        result.update(
            {
                "timestamp": file.timestamp,
                "timestamp_utc": file.timestamp_utc,
                "relative_filename": file.relative_path,
                "sequence_index": index,
                "split": split,
                "triggered_channel_names": [names[i] for i in result.pop("triggered_channels")],
            }
        )
        rows.append(result)
    return rows


def _plot(
    run_dir: Path,
    primary: list[dict[str, Any]],
    holdout: list[dict[str, Any]],
    controls: dict[str, list[dict[str, Any]]],
    baselines: list[dict[str, Any]],
    runtime: dict[str, Any],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = run_dir / "figures"
    figures.mkdir(exist_ok=True)

    def save(name: str, title: str, ylabel: str, series: list[tuple[str, list[float]]]) -> None:
        figure, axis = plt.subplots(figsize=(10, 4))
        for label, values in series:
            axis.plot(values, label=label)
        axis.set(title=title, xlabel="evaluation recording", ylabel=ylabel)
        if len(series) > 1:
            axis.legend()
        figure.tight_layout()
        figure.savefig(figures / name, dpi=120)
        plt.close(figure)

    global_threshold = float(primary[0]["gate_global_deformation_threshold"])
    save(
        "global_score.png",
        "Global exchange score",
        "score",
        [
            ("primary", [r["global_exchange_score"] for r in primary]),
            ("threshold", [global_threshold] * len(primary)),
        ],
    )
    local_threshold = float(primary[0]["gate_local_relationship_damage_threshold"])
    save(
        "maximum_local_edge_score.png",
        "Maximum local edge score",
        "score",
        [
            ("primary", [r["maximum_local_edge_score"] for r in primary]),
            ("threshold", [local_threshold] * len(primary)),
        ],
    )
    save(
        "six_gate_states.png",
        "Six gate states",
        "passed",
        [(name, [int(r[f"gate_{name}_passed"]) for r in primary]) for name in EXPECTED_GATES],
    )
    save(
        "final_decision_timeline.png",
        "Final decision timeline",
        "high confidence",
        [("primary", [int(r["high_confidence_ims_warning"]) for r in primary])],
    )
    for feature in ("centered_rms", "excess_kurtosis", "crest_factor"):
        channels = sorted(primary[0]["g6_values_by_feature_and_channel"][feature])
        series: list[tuple[str, list[float]]] = []
        for channel in channels:
            series.append(
                (
                    channel,
                    [r["g6_values_by_feature_and_channel"][feature][channel] for r in primary],
                )
            )
            threshold = primary[0]["g6_thresholds_by_feature_and_channel"][feature][channel]
            series.append((f"{channel} threshold", [float(threshold)] * len(primary)))
        save(
            f"g6_{feature}.png",
            f"G6 {feature} by channel",
            feature,
            series,
        )
    save(
        "first_warning_markers.png",
        "Warning states",
        "active",
        [
            (name, [int(r[name]) for r in primary])
            for name in (
                "screening_positive",
                "persistent_mcift_warning",
                "high_confidence_ims_warning",
            )
        ],
    )
    candidate_names = sorted({str(name) for row in primary for name in row["candidate_nodes"]})
    candidate_series: list[tuple[str, list[float]]] = [
        (name, [float(name in row["candidate_nodes"]) for row in primary])
        for name in candidate_names
    ] or [("none", [0.0] * len(primary))]
    save(
        "candidate_channel_timeline.png",
        "Candidate channels",
        "candidate",
        candidate_series,
    )
    save(
        "healthy_holdout_false_positives.png",
        "Healthy holdout positives",
        "active",
        [
            ("screening", [int(r["screening_positive"]) for r in holdout]),
            ("G6", [int(r["gate_conventional_vibration_agreement_passed"]) for r in holdout]),
        ],
    )
    shuffled = controls.get("shuffled", [])
    save(
        "primary_vs_shuffled.png",
        "Primary versus shuffled chronology",
        "persistent warning",
        [
            ("primary", [int(r["persistent_mcift_warning"]) for r in primary]),
            ("shuffled", [int(r["persistent_mcift_warning"]) for r in shuffled]),
        ],
    )
    save(
        "mcift_vs_baselines.png",
        "MCIFT versus conventional baselines",
        "active",
        [
            ("MCIFT", [int(r["persistent_mcift_warning"]) for r in primary]),
            ("baseline OR", [int(r["conventional_or_positive"]) for r in baselines]),
        ],
    )
    save(
        "throughput.png",
        "Cumulative evaluation throughput",
        "recordings per second",
        [
            (
                "throughput",
                [
                    (index + 1) / max(float(row["evaluation_elapsed_seconds"]), 1e-12)
                    for index, row in enumerate(primary)
                ],
            )
        ],
    )


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def run(args: argparse.Namespace) -> Path:
    total_start = time.perf_counter()
    protocol = load_protocol(Path(args.config))
    if getattr(args, "install_mcift", True):
        install_mcift(Path(args.mcift_repo) if args.mcift_repo else None)
    mcift_info = validate_mcift(protocol)
    root_text = args.dataset_root or os.environ.get("IMS_DATASET_ROOT")
    if not root_text:
        raise ValueError(
            "dataset path missing; pass --dataset-root or set IMS_DATASET_ROOT after manually "
            "downloading and extracting official NASA IMS Test Set 2"
        )
    dataset_root = Path(root_text)
    files, discovery_runtime = discover_ims_files(dataset_root, limit=args.limit_files)
    validation_seconds = _validate_recordings(files, protocol)
    limited = args.limit_files is not None
    ranges = _ranges(protocol, len(files), limited)
    resolved_split = split_manifest(files, ranges)
    print(
        yaml.safe_dump(
            {"protocol": protocol.raw, "resolved_split": resolved_split}, sort_keys=False
        )
    )
    manifest = {
        "dataset_id": protocol.dataset["dataset_id"],
        "dataset_variant": protocol.dataset["dataset_variant"],
        "dataset_root": str(dataset_root.resolve()),
        "recording_count": len(files),
        "validated_samples_per_recording": int(protocol.dataset["samples_per_recording"]),
        "validated_channel_count": len(protocol.dataset["channel_names"]),
        "files": [file.manifest_record() for file in files],
    }
    manifest_hash = _hash_json(manifest)
    output_root = Path(args.output_root).resolve() / "ims-set2"
    output_root.mkdir(parents=True, exist_ok=True)
    _atomic_json(output_root / "dataset_manifest.json", manifest)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "dataset_manifest_sha256": manifest_hash}, indent=2))
        return output_root

    benchmark_root = Path(__file__).resolve().parents[3]
    benchmark_commit = _git_value(benchmark_root, ["rev-parse", "HEAD"]) or "unknown"
    short_commit = benchmark_commit[:8]
    requested_run_id = getattr(args, "run_id", None)
    run_id = requested_run_id or (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{short_commit}")
    run_dir = output_root / run_id
    if args.resume and not requested_run_id:
        raise ValueError("--resume requires the original --run-id")
    if args.resume and not run_dir.is_dir():
        raise FileNotFoundError(f"resume run directory not found: {run_dir}")
    if run_dir.exists() and not args.resume:
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    for directory in ("figures", "logs"):
        (run_dir / directory).mkdir(exist_ok=True)
    _atomic_json(run_dir / "dataset_manifest.json", manifest)
    shutil.copy2(protocol.path, run_dir / "protocol_snapshot.yaml")
    _atomic_json(run_dir / "split_manifest.json", resolved_split)
    environment = {**_memory_facts(), "mcift": mcift_info, "benchmark_git_commit": benchmark_commit}
    _atomic_json(run_dir / "environment.json", environment)
    _atomic_json(
        run_dir / "live_progress.json",
        {
            "phase": "loading_reference_and_calibration",
            "status": "running",
            "updated_at_utc": datetime.now(UTC).isoformat(),
        },
    )

    from mcift import MCIFTMonitor

    reference_range = ranges["reference"]
    calibration_range = ranges["calibration"]
    reference, parse_reference = _load_many(files[slice(*reference_range)], protocol)
    calibration, parse_calibration = _load_many(files[slice(*calibration_range)], protocol)
    _atomic_json(
        run_dir / "live_progress.json",
        {
            "phase": "reference_fit",
            "status": "running",
            "updated_at_utc": datetime.now(UTC).isoformat(),
        },
    )
    fit_start = time.perf_counter()
    monitor = MCIFTMonitor.fit(
        reference,
        sampling_rate_hz=float(protocol.dataset["sampling_rate_hz"]),
        channel_names=protocol.dataset["channel_names"],
        channel_units=protocol.dataset["channel_units"],
        profile=protocol.mcift["processing_profile"],
        gate_profile=protocol.mcift["gate_profile"],
        allow_small_sample=limited,
    )
    fit_seconds = time.perf_counter() - fit_start
    _atomic_json(
        run_dir / "live_progress.json",
        {
            "phase": "chronological_six_gate_calibration",
            "status": "running",
            "updated_at_utc": datetime.now(UTC).isoformat(),
        },
    )
    calibration_start = time.perf_counter()
    monitor = monitor.calibrate(
        calibration,
        sequence_order="chronological",
        allow_small_sample=limited,
    )
    calibration_seconds = time.perf_counter() - calibration_start
    baseline_thresholds = calibrate_baselines(
        calibration, float(protocol.raw["analysis"]["baseline_quantile"])
    )
    del reference, calibration
    monitor_path = run_dir / "monitor.mcift"
    fitted_fingerprint = monitor.configuration_fingerprint
    if args.resume:
        saved_monitor = MCIFTMonitor.load(monitor_path)
        if saved_monitor.configuration_fingerprint != fitted_fingerprint:
            raise ValueError("resume refused: refitted monitor differs from saved monitor")
        monitor = saved_monitor
    else:
        monitor.save(monitor_path)
        monitor = MCIFTMonitor.load(monitor_path)
    monitor_fingerprint = monitor.configuration_fingerprint
    resume_state = {
        "configuration_sha256": protocol.sha256,
        "dataset_manifest_sha256": manifest_hash,
        "mcift_version": mcift_info["version"],
        "monitor_fingerprint": monitor_fingerprint,
    }
    resume_path = run_dir / "resume_state.json"
    if args.resume:
        existing_resume = json.loads(resume_path.read_text(encoding="utf-8"))
        if existing_resume != resume_state:
            raise ValueError("resume refused: critical input or monitor fingerprint changed")
    else:
        _atomic_json(resume_path, resume_state)

    holdout_start, holdout_end = ranges["healthy_holdout"]
    holdout_indices = list(range(holdout_start, holdout_end))
    holdout, holdout_seconds = _evaluate_sequence(
        monitor,
        files[holdout_start:holdout_end],
        holdout_indices,
        protocol,
        progress_path=run_dir / "live_progress.json",
        phase="healthy_holdout",
    )
    evaluation_start, evaluation_end = ranges["evaluation"]
    evaluation_files = files[evaluation_start:evaluation_end]
    evaluation_indices = list(range(evaluation_start, evaluation_end))
    primary, evaluation_seconds = _evaluate_sequence(
        monitor,
        evaluation_files,
        evaluation_indices,
        protocol,
        append_path=run_dir / "primary_results.jsonl",
        resume=bool(args.resume),
        progress_path=run_dir / "live_progress.json",
        phase="primary_evaluation",
    )
    holdout_baselines = _baseline_rows(
        files[holdout_start:holdout_end],
        holdout_indices,
        protocol,
        baseline_thresholds,
        "healthy_holdout",
    )
    baselines = _baseline_rows(
        evaluation_files,
        evaluation_indices,
        protocol,
        baseline_thresholds,
        "evaluation",
    )
    _write_rows(run_dir / "primary_results.jsonl", run_dir / "primary_results.csv", primary)
    _write_rows(
        run_dir / "healthy_holdout_results.jsonl",
        run_dir / "healthy_holdout_results.csv",
        holdout,
    )
    _write_rows(
        run_dir / "baseline_results.jsonl",
        run_dir / "baseline_results.csv",
        [*holdout_baselines, *baselines],
    )

    controls: dict[str, list[dict[str, Any]]] = {"healthy_only": holdout}
    control_metadata: dict[str, Any] = {
        "healthy_only": {"fresh_history": True, "chronological": True}
    }
    control_seconds = 0.0
    seed = int(protocol.raw["random_seed"])
    if not args.skip_controls:
        shuffled_offsets = list(range(len(evaluation_files)))
        random.Random(seed).shuffle(shuffled_offsets)
        shuffled_files = [evaluation_files[index] for index in shuffled_offsets]
        shuffled_sources = [evaluation_indices[index] for index in shuffled_offsets]
        shuffled, seconds = _evaluate_sequence(
            monitor,
            shuffled_files,
            shuffled_sources,
            protocol,
            sequence_indices=list(range(len(shuffled_files))),
            progress_path=run_dir / "live_progress.json",
            phase="control_shuffled_chronology",
        )
        controls["shuffled"] = shuffled
        control_seconds += seconds
        control_metadata["shuffled"] = {
            "seed": seed,
            "source_order": shuffled_sources,
            "fresh_history": True,
            "progression_validity": "destroyed; chronology control only",
        }
        permutation = list(range(len(protocol.dataset["channel_names"])))
        permutation = permutation[1:] + permutation[:1]
        channel_rows, seconds = _evaluate_sequence(
            monitor,
            evaluation_files,
            evaluation_indices,
            protocol,
            window_transform=lambda window, _: window[:, permutation],
            progress_path=run_dir / "live_progress.json",
            phase="control_channel_permutation",
        )
        controls["channel_permutation"] = channel_rows
        control_seconds += seconds
        control_metadata["channel_permutation"] = {
            "permutation": permutation,
            "seed": seed,
            "fresh_history": True,
        }
        time_rows, permutations, seconds = _time_permutation_rows(
            monitor,
            evaluation_files,
            evaluation_indices,
            protocol,
            seed,
            run_dir / "live_progress.json",
        )
        controls["time_permutation"] = time_rows
        control_seconds += seconds
        control_metadata["time_permutation"] = {
            "per_channel_source_offsets": permutations,
            "seed": seed,
            "fresh_history": True,
        }
        for name, rows in controls.items():
            if name == "healthy_only":
                continue
            _write_rows(
                run_dir / f"control_{name}_results.jsonl",
                run_dir / f"control_{name}_results.csv",
                rows,
            )
    else:
        for name in ("shuffled", "channel_permutation", "time_permutation"):
            _write_rows(
                run_dir / f"control_{name}_results.jsonl",
                run_dir / f"control_{name}_results.csv",
                [],
            )

    terminal = protocol.dataset.get("terminal_recording_timestamp")
    documented_failure_timestamp = protocol.dataset.get("documented_failure_timestamp")
    documented_failure_recording = protocol.dataset.get("documented_failure_recording")
    durations = protocol.raw["analysis"]["sustained_durations"]
    summary = {
        "scientific_status": "non-scientific engineering smoke test"
        if limited
        else "complete frozen protocol run",
        "disclaimer": DISCLAIMER,
        "profiles": {
            "processing": protocol.mcift["processing_profile"],
            "gates": protocol.mcift["gate_profile"],
        },
        "warning_timing": warning_timing(
            primary,
            durations,
            terminal,
            documented_failure_timestamp,
            documented_failure_recording,
        ),
        "healthy_holdout_false_positives": false_positive_metrics(holdout),
        "localization": localization_metrics(
            primary, protocol.raw["analysis"].get("damaged_bearing")
        ),
        "controls": {
            name: {
                "warning_timing": warning_timing(
                    rows,
                    durations,
                    terminal,
                    documented_failure_timestamp,
                    documented_failure_recording,
                ),
                "gate_pass_rates": {
                    gate: sum(bool(row[f"gate_{gate}_passed"]) for row in rows) / len(rows)
                    for gate in EXPECTED_GATES
                }
                if rows
                else {},
                "metadata": control_metadata[name],
            }
            for name, rows in controls.items()
        },
        "baseline_thresholds": baseline_thresholds,
        "baseline_healthy_holdout_false_positives": {
            key: {
                "positive_recordings": sum(bool(row[key]) for row in holdout_baselines),
                "false_positive_rate": sum(bool(row[key]) for row in holdout_baselines)
                / len(holdout_baselines),
            }
            for key in (
                "centered_rms_positive",
                "excess_kurtosis_positive",
                "crest_factor_positive",
                "maximum_absolute_amplitude_positive",
                "conventional_or_positive",
                "same_channel_two_feature_positive",
                "aggregate_positive",
            )
        },
        "baseline_first_warnings": {
            key: next((row["sequence_index"] for row in baselines if row[key]), None)
            for key in (
                "centered_rms_positive",
                "excess_kurtosis_positive",
                "crest_factor_positive",
                "maximum_absolute_amplitude_positive",
                "conventional_or_positive",
                "same_channel_two_feature_positive",
                "aggregate_positive",
            )
        },
    }
    _atomic_json(run_dir / "summary.json", summary)
    summary_md = (
        "# IMS Test Set 2 six-gate benchmark\n\n"
        f"> {DISCLAIMER}\n\n"
        f"Run status: **{summary['scientific_status']}**.\n\n"
        f"MCIFT: `{mcift_info['version']}`; monitor fingerprint: `{monitor_fingerprint}`.\n\n"
        "Warning timing and false-positive details are preserved in `summary.json`. Time before "
        "the terminal recording is not necessarily lead time before physical fault onset.\n"
    )
    _atomic_text(run_dir / "summary.md", summary_md)

    runtime = {
        **discovery_runtime,
        "dataset_validation_parse_seconds": validation_seconds,
        "parsing_seconds": parse_reference + parse_calibration,
        "reference_fit_seconds": fit_seconds,
        "calibration_seconds": calibration_seconds,
        "healthy_holdout_evaluation_seconds": holdout_seconds,
        "evaluation_seconds": evaluation_seconds,
        "controls_seconds": control_seconds,
        "recordings_per_second": len(primary) / evaluation_seconds if evaluation_seconds else None,
        "peak_resident_memory_bytes": getattr(
            psutil.Process().memory_info(),
            "peak_wset",
            psutil.Process().memory_info().rss,
        ),
        "total_wall_clock_seconds_before_export": time.perf_counter() - total_start,
    }
    export_start = time.perf_counter()
    _plot(run_dir, primary, holdout, controls, baselines, runtime)
    runtime["result_export_seconds"] = time.perf_counter() - export_start
    runtime["total_wall_clock_seconds"] = time.perf_counter() - total_start
    runtime["output_directory_size_bytes"] = _directory_size(run_dir)
    _atomic_json(run_dir / "runtime.json", runtime)
    run_manifest = {
        "run_id": run_id,
        "status": "complete",
        "non_scientific_limited_run": limited,
        "dataset_manifest_sha256": manifest_hash,
        "configuration_sha256": protocol.sha256,
        "mcift": mcift_info,
        "benchmark_git_commit": benchmark_commit,
        "random_seed": seed,
        "split_boundaries": resolved_split["splits"],
        "monitor_fingerprint": monitor_fingerprint,
        "processing_profile": protocol.mcift["processing_profile"],
        "gate_profile": protocol.mcift["gate_profile"],
        "controls_skipped": bool(args.skip_controls),
        "disclaimer": DISCLAIMER,
    }
    _atomic_json(run_dir / "run_manifest.json", run_manifest)
    _atomic_json(
        run_dir / "live_progress.json",
        {
            "phase": "run_complete",
            "status": "complete",
            "percent": 100.0,
            "total_wall_clock_seconds": runtime["total_wall_clock_seconds"],
            "updated_at_utc": datetime.now(UTC).isoformat(),
        },
    )
    print(f"complete: {run_dir}")
    return run_dir


def validate_dataset(args: argparse.Namespace) -> int:
    protocol = load_protocol(Path(args.config))
    validate_mcift(protocol)
    root = args.dataset_root or os.environ.get("IMS_DATASET_ROOT")
    if not root:
        raise ValueError("pass --dataset-root or set IMS_DATASET_ROOT")
    files, timings = discover_ims_files(Path(root), limit=args.limit_files)
    ranges = _ranges(protocol, len(files), args.limit_files is not None)
    parse_seconds = _validate_recordings(files, protocol)
    print(
        json.dumps(
            {
                "valid": True,
                "recordings": len(files),
                "split": split_manifest(files, ranges),
                "timings": {**timings, "validation_parse_seconds": parse_seconds},
            },
            indent=2,
        )
    )
    return 0


def show_split(args: argparse.Namespace) -> int:
    protocol = load_protocol(Path(args.config))
    print(yaml.safe_dump(protocol.split, sort_keys=False))
    return 0


def benchmark_parser(args: argparse.Namespace) -> int:
    protocol = load_protocol(Path(args.config))
    root = args.dataset_root or os.environ.get("IMS_DATASET_ROOT")
    if not root:
        raise ValueError("pass --dataset-root or set IMS_DATASET_ROOT")
    files, _ = discover_ims_files(Path(root), limit=args.limit_files or 50)
    started = time.perf_counter()
    _load_many(files, protocol)
    elapsed = time.perf_counter() - started
    estimate = elapsed / len(files) * 984
    print(
        json.dumps(
            {"files": len(files), "seconds": elapsed, "estimated_full_parse_seconds": estimate},
            indent=2,
        )
    )
    return 0


def summarize(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    print(json.dumps(summary, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Local NASA IMS Test Set 2 six-gate benchmark")
    commands = root.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser, dataset: bool = True) -> None:
        command.add_argument("--config", default="configs/ims-set2-v1.yaml")
        if dataset:
            command.add_argument("--dataset-root")
            command.add_argument("--limit-files", type=int)

    run_command = commands.add_parser("run")
    common(run_command)
    run_command.add_argument("--mcift-repo")
    run_command.add_argument("--output-root", default="artifacts")
    run_command.add_argument("--dry-run", action="store_true")
    run_command.add_argument("--skip-controls", action="store_true")
    run_command.add_argument("--resume", action="store_true")
    run_command.add_argument("--run-id")
    validate = commands.add_parser("validate-dataset")
    common(validate)
    show = commands.add_parser("show-split")
    common(show, dataset=False)
    parser_bench = commands.add_parser("benchmark-parser")
    common(parser_bench)
    summary = commands.add_parser("summarize")
    summary.add_argument("--run-dir", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "run":
        run(args)
        return 0
    if args.command == "validate-dataset":
        return validate_dataset(args)
    if args.command == "show-split":
        return show_split(args)
    if args.command == "benchmark-parser":
        return benchmark_parser(args)
    if args.command == "summarize":
        return summarize(args)
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
