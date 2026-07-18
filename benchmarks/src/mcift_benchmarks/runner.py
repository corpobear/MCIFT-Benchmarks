from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest

from mcift_benchmarks.config import BenchmarkConfig
from mcift_benchmarks.datasets import exathlon, ims
from mcift_benchmarks.evaluation.anomaly_events import event_confusion
from mcift_benchmarks.evaluation.early_warning import stable_warning
from mcift_benchmarks.features.conventional import (
    band_energy,
    crest_factor,
    peak_to_peak,
    rms,
    sample_kurtosis,
    spectral_entropy,
)
from mcift_benchmarks.features.mcift_adapter import InferredExchangeAdapter
from mcift_benchmarks.provenance import dependency_versions, sha256_file, utc_now
from mcift_benchmarks.storage import blob_client

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class MciftCalibration:
    adapter: InferredExchangeAdapter
    reference_scale: FloatArray
    reference_exchange: FloatArray


def _robust_scale(values: FloatArray, axis: int | None = None) -> FloatArray:
    median = np.median(values, axis=axis, keepdims=axis is not None)
    mad = np.median(np.abs(values - median), axis=axis)
    scale = np.asarray(1.4826 * mad, dtype=np.float64)
    fallback = np.asarray(np.std(values, axis=axis), dtype=np.float64)
    return np.where(scale > 1e-12, scale, np.where(fallback > 1e-12, fallback, 1.0))


def _pairwise_differences(values: FloatArray) -> FloatArray:
    indices = np.triu_indices(len(values), k=1)
    return np.asarray(np.abs(values[:, None] - values[None, :])[indices], dtype=np.float64)


def calibrate_mcift(
    windows: list[FloatArray], sampling_rate_hz: float, reference_scale: FloatArray
) -> MciftCalibration:
    if not windows:
        raise ValueError("MCIFT calibration requires reference windows")
    probe = InferredExchangeAdapter(1.0, 1.0)
    observations = [
        probe.transform_window(window, sampling_rate_hz, reference_scale) for window in windows
    ]
    information_differences = np.concatenate(
        [_pairwise_differences(item.information) for item in observations]
    )
    frequency_differences = np.concatenate(
        [_pairwise_differences(item.angular_frequency) for item in observations]
    )
    sigma_information = float(_robust_scale(information_differences))
    sigma_frequency = float(_robust_scale(frequency_differences))
    adapter = InferredExchangeAdapter(sigma_information, sigma_frequency)
    exchanges = np.stack(
        [
            adapter.transform_window(window, sampling_rate_hz, reference_scale).pairwise_exchange
            for window in windows
        ]
    )
    return MciftCalibration(
        adapter=adapter,
        reference_scale=reference_scale,
        reference_exchange=np.median(exchanges, axis=0),
    )


def mcift_score(window: FloatArray, sampling_rate_hz: float, model: MciftCalibration) -> float:
    exchange = model.adapter.transform_window(
        window, sampling_rate_hz, model.reference_scale
    ).pairwise_exchange
    upper = np.triu_indices(exchange.shape[0], k=1)
    return float(np.sqrt(np.mean(np.square(exchange[upper] - model.reference_exchange[upper]))))


def _quantile(values: list[float], probability: float = 0.995) -> float:
    if not values:
        raise ValueError("threshold calibration set is empty")
    return float(np.quantile(np.asarray(values, dtype=np.float64), probability))


def _ims_baseline_vector(values: FloatArray) -> FloatArray:
    features: list[float] = []
    for channel in values.T:
        centered = channel - channel.mean()
        features.extend(
            [
                rms(centered),
                peak_to_peak(centered),
                sample_kurtosis(centered),
                crest_factor(centered),
                spectral_entropy(centered),
                band_energy(centered, 1, len(centered) // 4),
            ]
        )
    return np.asarray(features, dtype=np.float64)


def run_ims(config: BenchmarkConfig, input_uri: str) -> tuple[dict[str, Any], pd.DataFrame, str]:
    with tempfile.TemporaryDirectory(prefix="mcift-ims-") as directory:
        extracted, manifest_hash = ims.extract_set2(input_uri, Path(directory))
        paths = ims.recording_paths(extracted)
        reference_end = max(1, int(len(paths) * 0.10))
        calibration_end = max(reference_end + 1, int(len(paths) * 0.20))

        reference_recordings = [ims.load_recording(path) for path in paths[:reference_end]]
        channel_rms = np.asarray(
            [
                [rms(channel - channel.mean()) for channel in recording.T]
                for recording in reference_recordings
            ]
        )
        channel_scale = np.median(channel_rms, axis=0)
        channel_scale = np.where(channel_scale > 1e-12, channel_scale, 1.0)
        model = calibrate_mcift(reference_recordings, 20000.0, channel_scale)

        reference_baselines = np.stack(
            [_ims_baseline_vector(recording) for recording in reference_recordings]
        )
        baseline_center = np.median(reference_baselines, axis=0)
        baseline_scale = _robust_scale(reference_baselines, axis=0)

        rows: list[dict[str, Any]] = []
        for index, (timestamp, recording) in enumerate(ims.iter_recordings(paths)):
            baseline_vector = _ims_baseline_vector(recording)
            baseline_score = float(
                np.max(np.abs((baseline_vector - baseline_center) / baseline_scale))
            )
            rows.append(
                {
                    "recording_index": index,
                    "timestamp": timestamp,
                    "mcift_score": mcift_score(recording, 20000.0, model),
                    "conventional_score": baseline_score,
                }
            )
        frame = pd.DataFrame(rows)
        calibration = frame.iloc[reference_end:calibration_end]
        thresholds = {
            "mcift": _quantile(calibration["mcift_score"].tolist()),
            "conventional": _quantile(calibration["conventional_score"].tolist()),
        }
        for method, column in (("mcift", "mcift_score"), ("conventional", "conventional_score")):
            frame[f"{method}_positive"] = frame[column] > thresholds[method]
        warning_index = stable_warning(frame["mcift_positive"].to_numpy(dtype=np.bool_), 3)
        warning_timestamp = (
            None if warning_index is None else str(frame.iloc[warning_index]["timestamp"])
        )
        lead_recordings = None if warning_index is None else len(frame) - 1 - warning_index
        results = {
            "recordings": len(frame),
            "reference_recordings": reference_end,
            "calibration_recordings": calibration_end - reference_end,
            "thresholds": thresholds,
            "mcift_first_stable_warning": warning_timestamp,
            "mcift_lead_recordings_before_final_recording": lead_recordings,
            "mcift_false_alarms_before_calibration_end": int(
                frame.iloc[:calibration_end]["mcift_positive"].sum()
            ),
            "conventional_false_alarms_before_calibration_end": int(
                frame.iloc[:calibration_end]["conventional_positive"].sum()
            ),
            "sigma_information": model.adapter.sigma_information,
            "sigma_angular_frequency": model.adapter.sigma_angular_frequency,
        }
        return results, frame, manifest_hash


def _windows(
    trace: exathlon.Trace, size: int = 60, stride: int = 30
) -> list[tuple[int, int, FloatArray]]:
    return [
        (
            int(trace.timestamps[start]),
            int(trace.timestamps[start + size - 1]),
            trace.values[start : start + size],
        )
        for start in range(0, len(trace.values) - size + 1, stride)
    ]


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _actual_events(ground_truth: pd.DataFrame, trace_name: str) -> list[tuple[int, int]]:
    selected = ground_truth[ground_truth["trace_name"] == trace_name]
    events: list[tuple[int, int]] = []
    for row in selected.itertuples(index=False):
        end = row.root_cause_end if pd.isna(row.extended_effect_end) else row.extended_effect_end
        events.append((int(row.root_cause_start), int(end) + 1))
    return events


def run_exathlon(
    config: BenchmarkConfig, input_uri: str
) -> tuple[dict[str, Any], pd.DataFrame, str]:
    entries, manifest_hash, base_uri = exathlon.load_manifest(input_uri)
    selected = exathlon.scoped_entries(entries)
    ground_entry = next(
        entry for entry in selected if str(entry["path"]).endswith("ground_truth.zip")
    )
    ground_truth = exathlon.load_ground_truth(f"{base_uri}/{ground_entry['path']}")
    traces: list[exathlon.Trace] = []
    for entry in selected:
        original_path = str(entry["original_path"])
        if original_path.endswith("ground_truth.zip") or not original_path.endswith(".zip"):
            continue
        stem = original_path.removesuffix(".zip")
        segments = sorted(
            (
                candidate
                for candidate in selected
                if str(candidate["original_path"]).startswith(stem + ".z")
                and not str(candidate["original_path"]).endswith(".zip")
            ),
            key=lambda candidate: str(candidate["original_path"]),
        )
        part_uris = [f"{base_uri}/{candidate['path']}" for candidate in segments]
        part_uris.append(f"{base_uri}/{entry['path']}")
        traces.append(exathlon.load_trace(part_uris))
    traces.sort(key=lambda trace: trace.name)
    normal = [trace for trace in traces if trace.trace_type == 0]
    first = max(1, int(len(normal) * 0.60))
    second = max(first + 1, int(len(normal) * 0.80))
    reference_traces, calibration_traces = normal[:first], normal[first:second]
    evaluation_traces = [*normal[second:], *[trace for trace in traces if trace.trace_type != 0]]

    reference_records = np.concatenate([trace.values for trace in reference_traces])
    feature_center = np.median(reference_records, axis=0)
    feature_scale = _robust_scale(reference_records, axis=0)
    reference_windows = [window for trace in reference_traces for _, _, window in _windows(trace)]
    model = calibrate_mcift(reference_windows, 1.0, feature_scale)

    standardized_reference = (reference_records - feature_center) / feature_scale
    pca = PCA(n_components=5, random_state=int(config.raw["seed"])).fit(standardized_reference)
    forest = IsolationForest(
        n_estimators=200,
        contamination="auto",
        random_state=int(config.raw["seed"]),
        n_jobs=-1,
    ).fit(standardized_reference)

    def score_trace(trace: exathlon.Trace) -> list[dict[str, Any]]:
        standardized = (trace.values - feature_center) / feature_scale
        pca_error = np.mean(
            np.square(standardized - pca.inverse_transform(pca.transform(standardized))), axis=1
        )
        forest_score = -forest.decision_function(standardized)
        ewma_state = np.empty_like(standardized)
        ewma_state[0] = standardized[0]
        for index in range(1, len(standardized)):
            ewma_state[index] = 0.2 * standardized[index] + 0.8 * ewma_state[index - 1]
        records: list[dict[str, Any]] = []
        for start in range(0, len(trace.values) - 60 + 1, 30):
            end = start + 60
            records.append(
                {
                    "trace_name": trace.name,
                    "trace_type": trace.trace_type,
                    "start": int(trace.timestamps[start]),
                    "end": int(trace.timestamps[end - 1]) + 1,
                    "mcift_score": mcift_score(trace.values[start:end], 1.0, model),
                    "rolling_z_score": float(np.max(np.abs(standardized[start:end]))),
                    "ewma_score": float(
                        np.max(np.abs(standardized[start:end] - ewma_state[start:end]))
                    ),
                    "pca_score": float(np.mean(pca_error[start:end])),
                    "isolation_forest_score": float(np.mean(forest_score[start:end])),
                }
            )
        return records

    calibration_rows = [row for trace in calibration_traces for row in score_trace(trace)]
    score_columns = {
        "mcift": "mcift_score",
        "rolling_z": "rolling_z_score",
        "ewma": "ewma_score",
        "pca": "pca_score",
        "isolation_forest": "isolation_forest_score",
    }
    thresholds = {
        method: _quantile([float(row[column]) for row in calibration_rows])
        for method, column in score_columns.items()
    }
    rows = [row for trace in evaluation_traces for row in score_trace(trace)]
    frame = pd.DataFrame(rows)
    metrics: dict[str, Any] = {}
    for method, column in score_columns.items():
        frame[f"{method}_positive"] = frame[column] > thresholds[method]
        confusion = {"true_positive": 0, "false_positive": 0, "false_negative": 0}
        for trace in evaluation_traces:
            trace_rows = frame[frame["trace_name"] == trace.name]
            predicted = _merge_intervals(
                [
                    (int(row.start), int(row.end))
                    for row in trace_rows[trace_rows[f"{method}_positive"]].itertuples()
                ]
            )
            trace_confusion = event_confusion(predicted, _actual_events(ground_truth, trace.name))
            for key in confusion:
                confusion[key] += trace_confusion[key]
        precision = confusion["true_positive"] / max(
            1, confusion["true_positive"] + confusion["false_positive"]
        )
        recall = confusion["true_positive"] / max(
            1, confusion["true_positive"] + confusion["false_negative"]
        )
        metrics[method] = {
            **confusion,
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / max(1e-12, precision + recall),
        }
    results = {
        "reference_traces": len(reference_traces),
        "calibration_traces": len(calibration_traces),
        "evaluation_traces": len(evaluation_traces),
        "thresholds": thresholds,
        "event_metrics": metrics,
        "sigma_information": model.adapter.sigma_information,
        "sigma_angular_frequency": model.adapter.sigma_angular_frequency,
    }
    return results, frame, manifest_hash


def execute(config: BenchmarkConfig, input_uri: str, output_uri: str) -> dict[str, Any]:
    started = utc_now()
    benchmark_name = str(config.raw["benchmark"]["name"])
    if benchmark_name == "ims-early-warning":
        results, detail, manifest_hash = run_ims(config, input_uri)
    elif benchmark_name == "exathlon-anomaly-propagation":
        results, detail, manifest_hash = run_exathlon(config, input_uri)
    else:
        raise ValueError(f"unsupported benchmark: {benchmark_name}")
    run_id = output_uri.rstrip("/").rsplit("/", 1)[-1]
    with tempfile.TemporaryDirectory(prefix="mcift-results-") as directory:
        root = Path(directory)
        detail_path = root / "scores.csv"
        detail.to_csv(detail_path, index=False)
        summary = {
            "benchmark_name": benchmark_name,
            "benchmark_version": config.raw["benchmark"]["version"],
            "run_id": run_id,
            "provenance_manifest": "manifest.json",
            "results": results,
        }
        summary_path = root / "summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        artifacts = [
            {"path": "summary.json", "sha256": sha256_file(summary_path)},
            {"path": "scores.csv", "sha256": sha256_file(detail_path)},
        ]
        repository = Path(__file__).resolve().parents[4]
        git_commit = os.environ.get("MCIFT_GIT_COMMIT")
        if not git_commit:
            import subprocess

            git_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        manifest = {
            "benchmark_name": benchmark_name,
            "benchmark_version": config.raw["benchmark"]["version"],
            "dataset_name": config.raw["dataset"]["identifier"],
            "dataset_manifest_sha256": manifest_hash,
            "repository_url": "https://github.com/corpobear/MCIFT-Benchmarks",
            "git_commit": git_commit,
            "dirty_worktree": bool(os.environ.get("MCIFT_DIRTY_WORKTREE", "true") == "true"),
            "image_reference": os.environ.get("MCIFT_IMAGE_REFERENCE", "local-source-run"),
            "image_digest": os.environ.get("MCIFT_IMAGE_DIGEST", "sha256:" + "0" * 64),
            "config_path": str(config.path),
            "config_sha256": config.sha256,
            "python_version": __import__("platform").python_version(),
            "dependencies": dependency_versions(),
            "azure_resource_type": os.environ.get("MCIFT_RESOURCE_TYPE", "local-operator"),
            "azure_compute_size": os.environ.get("MCIFT_COMPUTE_SIZE", "operator-workstation"),
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "seed": int(config.raw["seed"]),
            "input_location": input_uri,
            "output_location": output_uri,
            "status": "completed",
            "artifacts": artifacts,
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for path in (summary_path, detail_path, manifest_path):
            destination = output_uri.rstrip("/") + "/" + path.name
            with path.open("rb") as handle:
                blob_client(destination).upload_blob(handle, overwrite=False)
    return {"run_id": run_id, "output": output_uri, "status": "completed"}
