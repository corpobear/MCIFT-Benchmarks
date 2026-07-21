from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import yaml
from jsonschema import Draft202012Validator

from mcift_benchmarks.datasets.ims import discover_ims_files, timestamp_from_name
from mcift_benchmarks.evaluation.ims_metrics import (
    calibrate_baselines,
    false_positive_metrics,
    first_sustained,
    localization_metrics,
    positive_runs,
    warning_timing,
)
from mcift_benchmarks.ims import (
    EXPECTED_GATES,
    _ranges,
    load_protocol,
    run,
    split_manifest,
    validate_mcift,
)


def _write_protocol(path: Path, samples: int = 128) -> None:
    value = {
        "benchmark": {"name": "synthetic-ims", "version": "test"},
        "dataset": {
            "dataset_id": "synthetic-ims",
            "dataset_variant": "test-set-2-shape",
            "sampling_rate_hz": 20000,
            "samples_per_recording": samples,
            "channel_names": ["bearing_1", "bearing_2", "bearing_3", "bearing_4"],
            "channel_units": ["unknown_raw_acceleration_unit"] * 4,
            "timestamp_rule": "filename-%Y.%m.%d.%H.%M.%S",
            "documented_failure_timestamp": None,
            "documented_failure_recording": None,
            "terminal_recording_timestamp": None,
        },
        "split": {
            "reference_range": [0, 4],
            "calibration_range": [4, 10],
            "healthy_holdout_range": [10, 12],
            "evaluation_range": [12, None],
        },
        "mcift": {
            "processing_profile": "mcift.exchange.vibration.v1",
            "gate_profile": "mcift.gates.ims-six-gate.v1",
            "minimum_version": "0.1.0.dev3",
            "history_maxlen": 32,
            "calibration_sequence_order": "chronological",
        },
        "analysis": {
            "sustained_durations": [3, 5, 10],
            "damaged_bearing": "bearing_1",
            "baseline_quantile": 0.995,
        },
        "output": {"root": "artifacts"},
        "random_seed": 20260101,
        "seed": 20260101,
    }
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _write_dataset(root: Path, count: int = 20, samples: int = 128) -> None:
    root.mkdir()
    start = datetime(2004, 2, 12, 10, 0, 0)
    x = np.linspace(0.0, 8.0 * np.pi, samples, endpoint=False)
    for index in range(count):
        stamp = (start + timedelta(minutes=10 * index)).strftime("%Y.%m.%d.%H.%M.%S")
        scale = 1.0 if index < 12 else 1.0 + (index - 11) * 0.12
        values = np.column_stack(
            [
                scale * np.sin(x + channel * 0.31) + 0.02 * np.cos((channel + 2) * x + index * 0.07)
                for channel in range(4)
            ]
        )
        np.savetxt(root / stamp, values, fmt="%.12f", delimiter="\t")
    (root / "README.txt").write_text("metadata, not a recording", encoding="utf-8")


def test_timestamp_parsing_and_chronological_manifest(tmp_path: Path) -> None:
    dataset = tmp_path / "data"
    _write_dataset(dataset, 4)
    files, _ = discover_ims_files(dataset)
    assert timestamp_from_name(files[0].path) < timestamp_from_name(files[-1].path)
    assert files[0].sha256 != files[1].sha256
    assert all(file.size_bytes > 0 for file in files)


def test_duplicate_timestamp_is_rejected(tmp_path: Path) -> None:
    dataset = tmp_path / "data"
    _write_dataset(dataset, 2)
    nested = dataset / "nested"
    nested.mkdir()
    original = next(dataset.glob("2004.*"))
    (nested / original.name).write_bytes(original.read_bytes())
    with pytest.raises(ValueError, match="duplicate IMS timestamps"):
        discover_ims_files(dataset)


def test_split_is_disjoint_chronological_and_hashed(tmp_path: Path) -> None:
    dataset = tmp_path / "data"
    _write_dataset(dataset, 20)
    files, _ = discover_ims_files(dataset)
    protocol_path = tmp_path / "protocol.yaml"
    _write_protocol(protocol_path)
    protocol = load_protocol(protocol_path)
    ranges = _ranges(protocol, 20, limited=True)
    manifest = split_manifest(files, ranges)
    assert [manifest["splits"][name]["start_index"] for name in ranges] == [0, 4, 10, 12]
    all_hashes = [value for split in manifest["splits"].values() for value in split["file_hashes"]]
    assert len(all_hashes) == len(set(all_hashes)) == 20


def test_version_and_profiles_are_exact(tmp_path: Path) -> None:
    protocol_path = tmp_path / "protocol.yaml"
    _write_protocol(protocol_path)
    info = validate_mcift(load_protocol(protocol_path))
    assert info["version"] >= "0.1.0.dev3"
    assert info["gate_profile"] == "mcift.gates.ims-six-gate.v1"
    assert info["processing_profile"] == "mcift.exchange.vibration.v1"


def test_metrics_and_baseline_calibration_have_no_evaluation_input() -> None:
    calibration = [np.arange(64 * 4, dtype=float).reshape(64, 4) + index for index in range(5)]
    thresholds = calibrate_baselines(calibration, 0.9)
    assert set(thresholds) == {
        "centered_rms",
        "excess_kurtosis",
        "crest_factor",
        "maximum_absolute_amplitude",
    }
    assert first_sustained([False, True, True, True], 3) == 1
    assert positive_runs([True, True, False, True]) == (2, 2)


def test_false_positive_lead_time_and_localization_metrics() -> None:
    rows = [
        {
            "timestamp": f"t{i}",
            "timestamp_utc": f"2004-02-12T10:{i:02d}:00Z",
            "sequence_index": i,
            "screening_positive": i >= 1,
            "persistent_mcift_warning": i >= 2,
            "high_confidence_ims_warning": False,
            "gate_global_deformation_passed": i == 1,
            "gate_local_relationship_damage_passed": False,
            "gate_conventional_vibration_agreement_passed": False,
            "candidate_nodes": ["bearing_1"] if i >= 1 else [],
            "candidate_edges": [["bearing_1", "bearing_2"]] if i >= 1 else [],
            "g6_triggered_features": [],
            "g6_triggered_channels": [],
        }
        for i in range(4)
    ]
    assert false_positive_metrics(rows)["screening"]["positive_recordings"] == 3
    timing = warning_timing(rows, [2], None)
    assert timing["screening_positive"]["first_evaluation_offset"] == 1
    assert localization_metrics(rows, "bearing_1")["top_1_channel_accuracy"] == 1.0


def test_synthetic_end_to_end_and_output_schema(tmp_path: Path) -> None:
    dataset = tmp_path / "data"
    _write_dataset(dataset, 20)
    protocol_path = tmp_path / "protocol.yaml"
    _write_protocol(protocol_path)
    output = tmp_path / "artifacts"
    run_dir = run(
        Namespace(
            config=str(protocol_path),
            mcift_repo=None,
            dataset_root=str(dataset),
            limit_files=20,
            output_root=str(output),
            dry_run=False,
            skip_controls=False,
            resume=False,
            run_id="synthetic-test",
            install_mcift=False,
        )
    )
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["non_scientific_limited_run"] is True
    required = {
        "primary_results.csv",
        "primary_results.jsonl",
        "healthy_holdout_results.csv",
        "baseline_results.csv",
        "control_shuffled_results.csv",
        "control_channel_permutation_results.csv",
        "control_time_permutation_results.csv",
        "summary.json",
        "summary.md",
        "runtime.json",
    }
    assert required <= {path.name for path in run_dir.iterdir()}
    first = json.loads((run_dir / "primary_results.jsonl").read_text().splitlines()[0])
    assert {
        name.removeprefix("gate_").removesuffix("_available")
        for name in first
        if name.startswith("gate_") and name.endswith("_available")
    } == set(EXPECTED_GATES)
    schema_path = Path(__file__).parents[2] / "schemas" / "ims-recording-result.schema.json"
    Draft202012Validator(json.loads(schema_path.read_text())).validate(first)
    assert (run_dir / "monitor.mcift").is_dir()
    assert len(list((run_dir / "figures").glob("*.png"))) >= 10
    before = (run_dir / "primary_results.jsonl").read_text().splitlines()
    resumed = run(
        Namespace(
            config=str(protocol_path),
            mcift_repo=None,
            dataset_root=str(dataset),
            limit_files=20,
            output_root=str(output),
            dry_run=False,
            skip_controls=False,
            resume=True,
            run_id="synthetic-test",
            install_mcift=False,
        )
    )
    assert resumed == run_dir
    assert (run_dir / "primary_results.jsonl").read_text().splitlines() == before
