from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import numpy as np
import numpy.typing as npt


def first_true(values: Iterable[bool]) -> int | None:
    return next((index for index, value in enumerate(values) if value), None)


def first_sustained(values: Iterable[bool], duration: int) -> int | None:
    if duration < 1:
        raise ValueError("duration must be positive")
    run = 0
    for index, value in enumerate(values):
        run = run + 1 if value else 0
        if run >= duration:
            return index - duration + 1
    return None


def positive_runs(values: Iterable[bool]) -> tuple[int, int]:
    events = longest = current = 0
    previous = False
    for value in values:
        if value:
            current += 1
            longest = max(longest, current)
            if not previous:
                events += 1
        else:
            current = 0
        previous = value
    return events, longest


def false_positive_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"recording_count": 0}
    keys = {
        "g1": "gate_global_deformation_passed",
        "g2": "gate_local_relationship_damage_passed",
        "g6_basic_any_feature_any_channel": "gate_conventional_vibration_agreement_passed",
        "screening": "screening_positive",
        "persistent_warning": "persistent_mcift_warning",
        "high_confidence": "high_confidence_ims_warning",
        "g6_same_channel_two_feature": "g6_same_channel_multi_feature_agreement",
        "g6_at_least_two_features": "g6_at_least_two_triggered_features",
        "g6_rms_only": "g6_rms_only",
        "g6_kurtosis_only": "g6_kurtosis_only",
        "g6_crest_factor_only": "g6_crest_factor_only",
    }
    output: dict[str, Any] = {
        "recording_count": len(rows),
        "g6_rule": "basic G6: any feature on any channel",
        "exploratory_sensitivity_analyses": [
            "same-channel two-feature agreement",
            "at least two triggered features",
            "RMS-only",
            "kurtosis-only",
            "crest-factor-only",
        ],
    }
    for label, key in keys.items():
        mask = [bool(row.get(key, False)) for row in rows]
        events, longest = positive_runs(mask)
        count = sum(mask)
        output[label] = {
            "false_positive_rate": count / len(rows),
            "positive_recordings": count,
            "positive_events": events,
            "longest_positive_run": longest,
        }
    output["triggered_feature_counts"] = dict(
        Counter(name for row in rows for name in row.get("g6_triggered_features", []))
    )
    output["triggered_channel_counts"] = dict(
        Counter(name for row in rows for name in row.get("g6_triggered_channels", []))
    )
    return output


def warning_timing(
    rows: list[dict[str, Any]],
    durations: Iterable[int],
    terminal_timestamp: str | None,
    documented_failure_timestamp: str | None = None,
    documented_failure_recording: int | str | None = None,
) -> dict[str, Any]:
    states = {
        "screening_positive": "screening_positive",
        "persistent_mcift_warning": "persistent_mcift_warning",
        "high_confidence_ims_warning": "high_confidence_ims_warning",
    }
    output: dict[str, Any] = {}
    for label, key in states.items():
        mask = [bool(row.get(key, False)) for row in rows]
        first = first_true(mask)
        state: dict[str, Any] = {"first_evaluation_offset": first}
        if first is not None:
            row = rows[first]
            state.update(
                {
                    "first_sequence_index": row["sequence_index"],
                    "first_timestamp": row["timestamp"],
                }
            )
            anchor = terminal_timestamp or rows[-1]["timestamp_utc"]
            state["recordings_before_terminal_recording"] = len(rows) - first - 1
            state["time_before_terminal_recording_seconds"] = (
                datetime.fromisoformat(anchor.replace("Z", "+00:00"))
                - datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
            ).total_seconds()
            state["lead_time_caveat"] = (
                "Time before terminal recording is not necessarily lead time before "
                "physical fault onset."
            )
            if documented_failure_timestamp:
                state["time_before_documented_failure_seconds"] = (
                    datetime.fromisoformat(documented_failure_timestamp.replace("Z", "+00:00"))
                    - datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
                ).total_seconds()
            if isinstance(documented_failure_recording, int):
                state["recordings_before_documented_failure"] = documented_failure_recording - int(
                    row["sequence_index"]
                )
            elif isinstance(documented_failure_recording, str):
                anchor_index = next(
                    (
                        int(item["sequence_index"])
                        for item in rows
                        if item["relative_filename"] == documented_failure_recording
                        or item["timestamp"] == documented_failure_recording
                    ),
                    None,
                )
                if anchor_index is not None:
                    state["recordings_before_documented_failure"] = anchor_index - int(
                        row["sequence_index"]
                    )
        state["first_sustained"] = {
            str(duration): first_sustained(mask, duration) for duration in durations
        }
        output[label] = state
    return output


def localization_metrics(rows: list[dict[str, Any]], damaged_bearing: str | None) -> dict[str, Any]:
    if not damaged_bearing:
        return {"available": False, "reason": "documented damaged bearing not configured"}
    positives = [row for row in rows if row.get("screening_positive")]
    candidate_hits = [damaged_bearing in row.get("candidate_nodes", []) for row in positives]
    edge_hits = [
        any(damaged_bearing in edge for edge in row.get("candidate_edges", [])) for row in positives
    ]
    first = next(
        (
            row["sequence_index"]
            for row in rows
            if damaged_bearing in row.get("candidate_nodes", [])
            or damaged_bearing in row.get("g6_triggered_channels", [])
        ),
        None,
    )
    top1 = [
        bool(row.get("candidate_nodes"))
        and row["candidate_nodes"][0] == damaged_bearing
        for row in positives
    ]
    top2 = [damaged_bearing in row.get("candidate_nodes", [])[:2] for row in positives]
    denominator = len(positives)
    return {
        "available": True,
        "documented_bearing": damaged_bearing,
        "first_correct_candidate_channel_sequence_index": first,
        "positive_recordings": denominator,
        "fraction_positive_recordings_containing_documented_bearing": (
            sum(candidate_hits) / denominator if denominator else None
        ),
        "top_1_channel_accuracy": sum(top1) / denominator if denominator else None,
        "top_2_channel_coverage": sum(top2) / denominator if denominator else None,
        "edge_incidence_fraction": sum(edge_hits) / denominator if denominator else None,
        "caveat": "Candidate edges are associations and do not establish causal localization.",
    }


def baseline_features(
    window: npt.NDArray[np.float64],
) -> dict[str, npt.NDArray[np.float64]]:
    centered = window - np.mean(window, axis=0, keepdims=True)
    rms = np.sqrt(np.mean(np.square(centered), axis=0))
    peak = np.max(np.abs(centered), axis=0)
    safe = np.where(rms > 1e-12, rms, 1.0)
    return {
        "centered_rms": rms,
        "excess_kurtosis": np.where(
            rms > 1e-12, np.mean(np.power(centered, 4), axis=0) / np.power(safe, 4) - 3.0, 0.0
        ),
        "crest_factor": np.where(rms > 1e-12, peak / safe, 0.0),
        "maximum_absolute_amplitude": peak,
    }


def calibrate_baselines(
    windows: list[npt.NDArray[np.float64]], quantile: float
) -> dict[str, list[float]]:
    if not windows:
        raise ValueError("baseline calibration requires windows")
    rows: dict[str, list[npt.NDArray[np.float64]]] = {}
    for window in windows:
        for name, values in baseline_features(window).items():
            rows.setdefault(name, []).append(values)
    return {
        name: np.quantile(np.stack(values), quantile, axis=0, method="linear").tolist()
        for name, values in rows.items()
    }


def evaluate_baseline(
    window: npt.NDArray[np.float64], thresholds: dict[str, list[float]]
) -> dict[str, Any]:
    features = baseline_features(window)
    flags = {
        name: values > np.asarray(thresholds[name], dtype=np.float64)
        for name, values in features.items()
    }
    conventional = flags["centered_rms"] | flags["excess_kurtosis"] | flags["crest_factor"]
    same_channel_two = (
        flags["centered_rms"].astype(int)
        + flags["excess_kurtosis"].astype(int)
        + flags["crest_factor"].astype(int)
    ) >= 2
    standardized = [
        features[name] / np.maximum(np.asarray(thresholds[name]), 1e-12) for name in features
    ]
    return {
        **{f"{name}_positive": bool(np.any(value)) for name, value in flags.items()},
        "conventional_or_positive": bool(np.any(conventional)),
        "same_channel_two_feature_positive": bool(np.any(same_channel_two)),
        "maximum_standardized_exceedance": float(np.max(np.stack(standardized))),
        "aggregate_positive": bool(np.max(np.stack(standardized)) > 1.0),
        "triggered_channels": np.flatnonzero(conventional).tolist(),
    }
