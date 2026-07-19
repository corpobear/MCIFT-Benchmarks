# ruff: noqa: E501
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_COMMIT = "731c249288d67dac4e3a10792980ec99be1de34d"
EXPECTED_RUN_ID = "ims-20260718-approved-v1"
EXPECTED_BENCHMARK = "ims-early-warning"
EXPECTED_VERSION = "ims-set2-v1"
EXPECTED_SCORES_SHA256 = "d6c717e0bfeb3d7a97e57910feae7a0fc02a890c917db4fc8b10676082727ed8"
EXPECTED_SUMMARY_SHA256 = "1c6a08585b88013ebce956988f2189fd06fba2eb86a1d1ad0c965508bf4b5b08"
EXPECTED_THRESHOLDS = {
    "mcift": 0.3310462580442802,
    "conventional": 5.841765941775609,
}
SOURCE_ROOT = "https://github.com/corpobear/MCIFT-Benchmarks/blob/" + EXPECTED_COMMIT


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _source(path: str, lines: str) -> str:
    return f"{SOURCE_ROOT}/{path}#L{lines}"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _parse_bool(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"unexpected Boolean value in scores.csv: {value!r}")


def _stable_start(mask: list[bool], consecutive: int = 3) -> int | None:
    run = 0
    for index, active in enumerate(mask):
        run = run + 1 if active else 0
        if run >= consecutive:
            return index - consecutive + 1
    return None


def _positive_runs(mask: Iterable[bool]) -> int:
    count = 0
    previous = False
    for active in mask:
        if active and not previous:
            count += 1
        previous = active
    return count


def _iso_timestamp(value: str) -> str:
    return datetime.strptime(value, "%Y.%m.%d.%H.%M.%S").replace(tzinfo=None).isoformat()


def _read_scores(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = {
        "recording_index",
        "timestamp",
        "mcift_score",
        "conventional_score",
        "mcift_positive",
        "conventional_positive",
    }
    if not rows or set(rows[0]) != expected:
        raise ValueError("unexpected scores.csv schema")
    return rows


def _comparison(rows: list[dict[str, str]]) -> dict[str, Any]:
    methods: dict[str, dict[str, Any]] = {}
    for method in ("mcift", "conventional"):
        mask = [_parse_bool(row[f"{method}_positive"]) for row in rows]
        start = _stable_start(mask)
        if start is None:
            raise ValueError(f"no stable warning for {method}")
        lead = len(rows) - 1 - start
        methods[method] = {
            "stable_run_start_index": start,
            "stable_run_start_timestamp": _iso_timestamp(rows[start]["timestamp"]),
            "lead_recordings_before_final": lead,
            "lead_minutes_before_final": lead * 10,
            "positive_recordings": sum(mask),
            "separate_positive_runs": _positive_runs(mask),
            "threshold_crossings_before_calibration_end": sum(mask[:196]),
        }
    mcift = methods["mcift"]
    conventional = methods["conventional"]
    return {
        "schema_version": "2.0",
        "source_file": "scores.csv",
        "stable_warning_rule": {
            "consecutive_positive_recordings": 3,
            "reported_timestamp_semantics": "first positive in the first qualifying run",
            "recording_interval_minutes_observed": 10,
            "three_observation_timestamp_span_minutes": 20,
        },
        "mcift": mcift,
        "conventional": conventional,
        "comparison": {
            "mcift_warning_lead_advantage_recordings": (
                mcift["lead_recordings_before_final"] - conventional["lead_recordings_before_final"]
            ),
            "mcift_warning_lead_advantage_minutes": (
                mcift["lead_minutes_before_final"] - conventional["lead_minutes_before_final"]
            ),
            "mcift_has_fewer_early_calibration_crossings": (
                mcift["threshold_crossings_before_calibration_end"]
                < conventional["threshold_crossings_before_calibration_end"]
            ),
            "conventional_has_fewer_fragmented_positive_runs": (
                conventional["separate_positive_runs"] < mcift["separate_positive_runs"]
            ),
            "superiority_verdict": "not established",
        },
    }


def _data_quality(rows: list[dict[str, str]]) -> dict[str, Any]:
    parsed = [datetime.strptime(row["timestamp"], "%Y.%m.%d.%H.%M.%S") for row in rows]
    intervals = [
        (current - previous).total_seconds() / 60
        for previous, current in zip(parsed[:-1], parsed[1:], strict=True)
    ]
    score_non_finite = sum(
        not math.isfinite(float(row[column]))
        for row in rows
        for column in ("mcift_score", "conventional_score")
    )
    return {
        "expected_recordings": 984,
        "loaded_recordings": len(rows),
        "missing_recordings": 984 - len(rows),
        "rejected_recordings": 0,
        "malformed_recordings_detected_by_loader": 0,
        "imputed_recordings": 0,
        "raw_waveform_non_finite_values": "Not verifiable from the preserved run",
        "derived_score_non_finite_values": score_non_finite,
        "duplicate_timestamps_in_scores": len(rows) - len({row["timestamp"] for row in rows}),
        "chronological_regressions_in_scores": sum(value < 0 for value in intervals),
        "reordered_timestamps_by_executed_code": 0,
        "observed_inter_recording_intervals": {
            "count": len(intervals),
            "minimum_minutes": min(intervals),
            "maximum_minutes": max(intervals),
            "ten_minute_count": sum(value == 10 for value in intervals),
            "other_count": sum(value != 10 for value in intervals),
        },
        "evidence_limit": (
            "The loader was fail-fast and produced 984 score rows, so no file was skipped, "
            "rejected, or imputed. It did not instrument raw non-finite-value counts."
        ),
    }


def _methodology(
    summary: dict[str, Any], manifest: dict[str, Any], rows: list[dict[str, str]], exported: str
) -> dict[str, Any]:
    results = summary["results"]
    data_quality = _data_quality(rows)
    cfg = "benchmarks/configs/ims-set2-v1.yaml"
    loader = "benchmarks/src/mcift_benchmarks/datasets/ims.py"
    runner = "benchmarks/src/mcift_benchmarks/runner.py"
    conventional = "benchmarks/src/mcift_benchmarks/features/conventional.py"
    adapter = "benchmarks/src/mcift_benchmarks/features/mcift_adapter.py"
    warning = "benchmarks/src/mcift_benchmarks/evaluation/early_warning.py"
    table = [
        {
            "item": "Selected IMS test set",
            "value": "Set 2 (2nd_test.rar)",
            "class": "executed configuration and code",
            "evidence_source": [_source(cfg, "8"), _source(loader, "71-L88")],
        },
        {
            "item": "Selected bearing",
            "value": "No single bearing selected; all four configured bearings enter both detectors",
            "class": "executed configuration and code",
            "evidence_source": [_source(cfg, "9"), _source(runner, "102-L114")],
        },
        {
            "item": "Selected source columns",
            "value": "All four columns, NumPy indices 0, 1, 2, 3; configured order bearing_1 through bearing_4",
            "class": "executed code plus configuration ordering",
            "evidence_source": [
                _source(cfg, "9"),
                _source(loader, "98-L102"),
                _source(runner, "102-L114"),
            ],
        },
        {
            "item": "Accelerometer direction",
            "value": "Not verifiable from the preserved run",
            "class": "evidence gap",
            "evidence_source": "No direction field exists in the executed config, loader, summary, or manifest.",
        },
        {
            "item": "Channel-selection rationale",
            "value": "Not documented; the code consumes every column rather than selecting one",
            "class": "evidence gap",
            "evidence_source": [_source(cfg, "9"), _source(runner, "102-L114")],
        },
        {
            "item": "End-of-test bearing fault",
            "value": "Not verifiable from the preserved run",
            "class": "evidence gap",
            "evidence_source": "The executed artifacts identify only the final experiment recording, not a bearing-specific fault label.",
        },
        {
            "item": "Raw recording structure",
            "value": "20,480 rows x 4 columns, 20,000 Hz, 1.024 s waveform duration, tab-delimited numeric text",
            "class": "executed configuration and fail-fast loader",
            "evidence_source": [_source(cfg, "9-L16"), _source(loader, "98-L102")],
        },
        {
            "item": "Recording timestamp",
            "value": "Unparsed source filename; observed format YYYY.MM.DD.HH.MM.SS",
            "class": "executed code and preserved scores",
            "evidence_source": [_source(loader, "105-L107"), "scores.csv timestamp column"],
        },
        {
            "item": "Recording interval",
            "value": "Not configured; post-hoc artifact audit found all 983 intervals equal to 10 minutes",
            "class": "observed preserved artifact",
            "evidence_source": "scores.csv timestamp audit",
        },
        {
            "item": "Conventional feature vector",
            "value": "24 values: six features in channel-major order for each of four centered channels",
            "class": "executed code",
            "evidence_source": [_source(runner, "100-L114"), _source(conventional, "8-L37")],
        },
        {
            "item": "Conventional score",
            "value": "maximum absolute per-feature robust standardized deviation from reference medians",
            "class": "executed code",
            "evidence_source": _source(runner, "135-L146"),
        },
        {
            "item": "MCIFT exchange matrix",
            "value": "4 x 4 symmetric matrix, zero diagonal, six unordered pair values",
            "class": "executed code",
            "evidence_source": _source(adapter, "68-L109"),
        },
        {
            "item": "MCIFT distance",
            "value": "root mean square difference over the six upper-triangle exchange entries",
            "class": "executed code; overrides imprecise config label",
            "evidence_source": [_source(cfg, "33"), _source(runner, "86-L91")],
        },
        {
            "item": "Reference partition",
            "value": "recording indices 0-97 inclusive (98 recordings)",
            "class": "executed code and summary",
            "evidence_source": [
                _source(runner, "121-L139"),
                "summary.json results.reference_recordings",
            ],
        },
        {
            "item": "Calibration partition",
            "value": "recording indices 98-195 inclusive (98 recordings); thresholds only",
            "class": "executed code and summary",
            "evidence_source": [
                _source(runner, "121-L160"),
                "summary.json results.calibration_recordings",
            ],
        },
        {
            "item": "Threshold quantile",
            "value": "NumPy 2.2.1 quantile q=0.995 with default linear method; strict score > threshold",
            "class": "executed code and dependency manifest",
            "evidence_source": [
                _source(runner, "94-L97"),
                _source(runner, "156-L162"),
                "provenance.redacted.json dependencies",
            ],
        },
        {
            "item": "Stable warning",
            "value": "first positive of first run of 3 consecutive strict exceedances; any negative resets counter",
            "class": "executed code",
            "evidence_source": [_source(warning, "7-L15"), _source(runner, "163-L167")],
        },
        {
            "item": "Run/scientific status",
            "value": "execution completed; scientific publication review unapproved",
            "class": "preserved manifest plus publication policy",
            "evidence_source": [
                "source manifest status",
                "provenance.redacted.json scientific_review_status",
            ],
        },
        {
            "item": "Raw data-quality counts",
            "value": data_quality,
            "class": "fail-fast inference plus post-hoc preserved-artifact audit",
            "evidence_source": [_source(loader, "91-L107"), "scores.csv audit"],
        },
    ]
    features = [
        {
            "name": "rms",
            "equation": "sqrt((1/N) * sum_n x_c[n]^2)",
            "units": "source amplitude units; physical unit not recorded",
            "category": "time-domain",
            "constants_and_edge_cases": "none",
            "implementation": _source(conventional, "8-L9"),
        },
        {
            "name": "peak_to_peak",
            "equation": "max_n(x_c[n]) - min_n(x_c[n])",
            "units": "source amplitude units; physical unit not recorded",
            "category": "time-domain",
            "constants_and_edge_cases": "none",
            "implementation": _source(conventional, "12-L13"),
        },
        {
            "name": "kurtosis",
            "algorithm": "scipy.stats.kurtosis(x_c, fisher=False, bias=False), SciPy 1.15.0",
            "units": "dimensionless Pearson kurtosis",
            "category": "time-domain",
            "constants_and_edge_cases": "unbiased finite-sample correction delegated to pinned SciPy; constant input returns NaN",
            "implementation": _source(conventional, "21-L22"),
        },
        {
            "name": "crest_factor",
            "equation": "max_n(abs(x_c[n])) / rms(x_c)",
            "units": "dimensionless",
            "category": "time-domain",
            "constants_and_edge_cases": "returns 0.0 when RMS is exactly zero",
            "implementation": _source(conventional, "16-L18"),
        },
        {
            "name": "spectral_entropy",
            "equation": "P_k=abs(rfft(x_c)_k)^2; p_k=P_k/sum(P); H=-sum_{p_k>0} p_k*log2(p_k)",
            "units": "bits (dimensionless)",
            "category": "frequency-domain",
            "constants_and_edge_cases": "no window or FFT normalization; zero total power returns 0.0; zero-probability bins omitted",
            "implementation": _source(conventional, "25-L32"),
        },
        {
            "name": "frequency_band_energy",
            "equation": "sum_{k=1}^{5119} abs(rfft(x_c)_k)^2",
            "units": "squared FFT-amplitude units; FFT is unnormalized",
            "category": "frequency-domain",
            "constants_and_edge_cases": "Python slice [1:5120], approximately 0.9765625 through 4999.0234375 Hz; no window, filtering, or normalization",
            "implementation": [_source(conventional, "35-L37"), _source(runner, "111")],
        },
    ]
    missing_policy = {
        "missing_recording_file": "Fails if discovered file count is not exactly 984; no skip or imputation.",
        "empty_file": "np.loadtxt or the exact-shape check fails; run stops.",
        "malformed_row": "np.loadtxt or the exact-shape check fails; run stops.",
        "non_numeric_value": "np.loadtxt fails; run stops.",
        "nan": "No explicit raw-input check. np.loadtxt accepts NaN; downstream behavior is partition- and operation-dependent, with no warning or imputation policy.",
        "positive_or_negative_infinity": "No explicit raw-input check. Values may propagate or trigger MCIFT reference-scale validation; no uniform policy exists.",
        "wrong_waveform_sample_count": "Exact shape (20480, 4) check fails; run stops.",
        "duplicate_timestamp": "No validation. Timestamp is an unparsed filename string; duplicate strings would continue as separate rows.",
        "out_of_order_timestamp": "Paths are lexicographically sorted; timestamps are not parsed or checked. No explicit temporal reorder policy exists.",
        "unexpected_column_count": "Exact shape (20480, 4) check fails; run stops.",
        "zero_variance_recording": "No rejection. RMS, peak-to-peak, crest factor, entropy, and band energy become zero, but SciPy kurtosis becomes NaN; downstream conventional score can become NaN. MCIFT has explicit scale/zero-power fallbacks.",
        "partially_readable_file": "If parsing or exact shape fails, run stops; there is no partial-record continuation path.",
        "logging": "No warning-only malformed-input path is implemented.",
        "implementation": _source(loader, "91-L107"),
    }
    return {
        "schema_version": "2.0",
        "benchmark_name": EXPECTED_BENCHMARK,
        "benchmark_version": EXPECTED_VERSION,
        "run_id": EXPECTED_RUN_ID,
        "methodology_source_commit": EXPECTED_COMMIT,
        "feature_extraction_version": "ims-set2-v1@" + EXPECTED_COMMIT,
        "exported_at_utc": exported,
        "scientific_review_status": "unapproved",
        "run_status": {
            "execution_status": manifest["status"],
            "run_id_approved_token": "internal artifact label only",
            "config_approval": "approved for execution, not scientific publication",
            "authoritative_publication_status": "scientific_review_status=unapproved",
            "explanation": (
                "The run ID was derived from the output location and was not interpreted by the "
                "runner. The source manifest says only that execution completed. The preserved run "
                "does not have the manifest status 'approved' required by publication validation."
            ),
        },
        "methodology_table": table,
        "selection": {
            "recording_set": 2,
            "bearings": [1, 2, 3, 4],
            "source_column_indices": [0, 1, 2, 3],
            "indexing": "zero-based in NumPy/Python; bearing labels in config are one-based",
            "accelerometer_direction": "Not verifiable from the preserved run",
            "selection_rationale": "Not documented; all four columns are consumed",
            "end_of_test_fault": "Not verifiable from the preserved run",
        },
        "raw_recording_structure": {
            "expected_samples": 20480,
            "expected_columns": 4,
            "sampling_frequency_hz": 20000,
            "recording_duration_seconds": 1.024,
            "expected_interval": "Not specified by executed configuration or loader",
            "observed_interval_minutes": 10,
            "observed_interval_count": 983,
            "format": "tab-delimited numeric text loaded as float64 by numpy.loadtxt",
            "timestamp_source": "recording filename",
            "timestamp_parsing_by_executed_code": "none",
            "observed_timestamp_format": "YYYY.MM.DD.HH.MM.SS",
            "loaded_all_984_files": True,
            "expected_vs_observed_deviation": "none visible to fail-fast file-count/shape checks",
        },
        "conventional_feature_pipeline": {
            "input_channels": 4,
            "preprocessing": "x_c[n] = x[n] - mean(x) independently for every channel and recording",
            "windowing": "none",
            "filtering": "none",
            "detrending": "per-recording arithmetic-mean removal only",
            "feature_order": "channel-major; listed six-feature sequence repeated for columns 0, 1, 2, 3",
            "feature_count": 24,
            "features": features,
            "final_score_equation": "score=max_{j=1..24} abs((f_j-median_ref_j)/scale_ref_j)",
            "implementation": _source(runner, "100-L146"),
        },
        "mcift_exchange_pipeline": {
            "input": "all four raw waveform columns",
            "reference_channel_scale": "s_c=median over recordings 0..97 of RMS(x_c-mean(x_c)); use 1.0 when s_c<=1e-12",
            "standardized_waveform": "z[n,c]=(x[n,c]-mean_n(x[:,c]))/s_c",
            "information": "I_c=ln(sqrt(mean_n(z[n,c]^2))+eps), eps=2.220446049250313e-16",
            "spectrum": "X[k,c]=rfft(z[:,c]); P[k,c]=abs(X[k,c])^2; P[0,c]=0",
            "angular_frequency": "omega_c=sum_k(2*pi*f_k*P[k,c])/sum_k(P[k,c]); 0 when total power is 0",
            "phase": "k*=argmax_k sum_c P[k,c]; phi_c=angle(X[k*,c])",
            "sigma_information": {
                "value": results["sigma_information"],
                "source": "robust scale of 588 absolute within-recording pairwise I differences from 98 reference recordings",
            },
            "sigma_angular_frequency": {
                "value": results["sigma_angular_frequency"],
                "source": "robust scale of 588 absolute within-recording pairwise omega differences from 98 reference recordings",
            },
            "sigma_scale_rule": "1.4826*MAD when >1e-12; otherwise population standard deviation when >1e-12; otherwise 1.0",
            "exchange_equation": "M_ij=g*exp(-(I_i-I_j)^2/(2*sigma_I^2))*exp(-(omega_i-omega_j)^2/(2*sigma_omega^2))*cos(phi_i-phi_j)^2",
            "constants": {"coupling_g": 1.0, "densification_eta": 1.0, "scale_floor": 1e-12},
            "matrix": {
                "shape": [4, 4],
                "channel_order": ["bearing_1", "bearing_2", "bearing_3", "bearing_4"],
                "symmetric": True,
                "directed": False,
                "diagonal": 0.0,
                "normalization": "no post-construction normalization; Gaussian and cosine-squared terms bound off-diagonal values to [0,1] for g=1",
            },
            "densification": "exp(eta*mean(M_ij for i<j)); calculated by adapter but not used in IMS score",
            "healthy_reference_matrix": "elementwise median of the 98 reference exchange matrices",
            "distance_equation_identifier": "upper_triangle_root_mean_square_exchange_distance_v1",
            "distance_equation": "sqrt((1/6)*sum_{i<j}(M_ij-reference_M_ij)^2)",
            "config_label_correction": "The config says Frobenius distance, but executed code computes upper-triangle RMS. This export follows code.",
            "fitted_values_not_preserved": [
                "reference channel scales",
                "4x4 reference exchange matrix",
            ],
            "implementation": [
                _source(adapter, "47-L109"),
                _source(runner, "42-L91"),
                _source(runner, "124-L133"),
            ],
        },
        "normalization": {
            "mcift": {
                "fit_partition": "recordings 0-97 only",
                "center": "per-recording, per-channel arithmetic mean",
                "scale": "per-channel median reference RMS with <=1e-12 fallback to 1.0",
                "global_or_per_feature": "per channel",
                "clipping_or_winsorization": "none",
                "recalculated_after_index_97": False,
                "calibration_98_195_effect": "threshold only",
                "fitted_channel_scales": "Not verifiable from the preserved run",
            },
            "conventional": {
                "fit_partition": "recordings 0-97 only",
                "center": "per-feature median over 98 reference feature vectors",
                "scale": "per-feature 1.4826*MAD; if <=1e-12 use population standard deviation; if still <=1e-12 use 1.0",
                "formula": "z_j=(f_j-center_j)/scale_j; score=max_j(abs(z_j))",
                "global_or_per_feature": "per feature (24 centers and scales)",
                "clipping_or_winsorization": "none",
                "recalculated_after_index_97": False,
                "calibration_98_195_effect": "threshold only",
                "fitted_centers_and_scales": "Not verifiable from the preserved run",
                "robust_standardized_meaning": "median/MAD with the documented standard-deviation and unit fallbacks",
            },
        },
        "thresholds": {
            "fit_partition": "recordings 98-195 inclusive",
            "probability": 0.995,
            "numpy_version": manifest["dependencies"]["numpy"],
            "quantile_method": "linear (NumPy 2.2.1 default): h=(n-1)q; interpolate between sorted floor(h) and ceil(h)",
            "for_n_98": "h=96.515, so 0.485*x_sorted[96] + 0.515*x_sorted[97]",
            "comparison": "strict score > threshold; equality/ties are negative",
            "mcift": results["thresholds"]["mcift"],
            "conventional": results["thresholds"]["conventional"],
            "frozen_during_evaluation": True,
        },
        "persistence_and_timing": {
            "consecutive_positive_count": 3,
            "negative_resets_counter": True,
            "partition_boundary_reset": False,
            "evaluation_scope": "the full 984-recording Boolean sequence, including reference and calibration",
            "returned_index": "first positive index of the first qualifying three-positive run",
            "reported_timestamp": "timestamp of that first positive, not the third confirming observation",
            "lead_recordings_formula": "983 - stable_warning_start_index",
            "lead_recordings_meaning": "number of later ten-minute timestamp intervals through the final recording",
            "lead_minutes_formula": "lead_recordings * 10",
            "mcift_lead_recordings": results["mcift_lead_recordings_before_final_recording"],
            "mcift_lead_minutes": results["mcift_lead_recordings_before_final_recording"] * 10,
            "three_recording_wording": "Three sampled observations at ten-minute spacing span 20 minutes from the first timestamp to the third timestamp.",
        },
        "missing_data_policy": missing_policy,
        "observed_data_quality": data_quality,
        "unverifiable_from_preserved_run": [
            "accelerometer direction",
            "bearing-specific end-of-test fault label",
            "reason for choosing the channels (the code uses all four)",
            "raw waveform non-finite-value count",
            "fitted conventional centers and scales",
            "fitted MCIFT channel scales and reference exchange matrix",
        ],
    }


def _dictionary(exported: str) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "exported_at_utc": exported,
        "files": {
            "summary.json": "Byte-identical preserved benchmark result summary.",
            "scores.csv": "Byte-identical per-recording detector scores and strict-threshold flags.",
            "comparison.json": "Derived stable-warning and fragmentation comparison; does not establish superiority.",
            "methodology.json": "Exact implementation-traced methodology, equations, evidence table, limitations, and data-quality policy.",
            "methodology-table.csv": "Flat Item/Value/Class/Evidence source rendering of methodology.json.methodology_table.",
            "provenance.redacted.json": "Allowlisted reproducibility facts with private locations and infrastructure fields removed.",
            "data-dictionary.json": "This file.",
        },
        "scores.csv": {
            "recording_index": "Zero-based index after lexicographic path sorting.",
            "timestamp": "Unparsed source filename; observed format YYYY.MM.DD.HH.MM.SS.",
            "mcift_score": "Upper-triangle RMS distance from frozen healthy-reference exchange matrix; exact equation in methodology.json.",
            "conventional_score": "Maximum absolute robust standardized value across 24 conventional features; exact pipeline in methodology.json.",
            "mcift_positive": "True only when mcift_score is strictly greater than 0.3310462580442802.",
            "conventional_positive": "True only when conventional_score is strictly greater than 5.841765941775609.",
        },
        "partitions": {
            "reference_indices": "0-97 inclusive",
            "calibration_indices": "98-195 inclusive",
            "evaluation_indices": "196-983 inclusive",
        },
        "status_fields": {
            "execution_status": "Whether the benchmark process completed.",
            "scientific_review_status": "Authoritative publication-review state; unapproved for this export.",
            "exported_at_utc": "UTC time this public export was generated, separate from run start/completion.",
            "methodology_source_commit": "Exact Git commit whose configuration and executed implementation were traced.",
        },
        "interpretation_limits": [
            "Final recording is an experiment endpoint, not a labelled degradation-onset timestamp.",
            "Three consecutive observations span 20 minutes between first and third timestamps.",
            "Warning lead is measured to the final recording only.",
            "These results do not establish MCIFT superiority.",
        ],
    }


def _write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Item", "Value", "Class", "Evidence source"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "Item": row["item"],
                    "Value": json.dumps(row["value"], ensure_ascii=False),
                    "Class": row["class"],
                    "Evidence source": json.dumps(row["evidence_source"], ensure_ascii=False),
                }
            )


def export_ims_run(source_run: Path, output_dir: Path, exported_at_utc: str | None = None) -> None:
    source_scores = source_run / "scores.csv"
    source_summary = source_run / "summary.json"
    source_manifest = source_run / "manifest.json"
    scores_hash = _sha256(source_scores)
    summary_hash = _sha256(source_summary)
    if scores_hash != EXPECTED_SCORES_SHA256:
        raise ValueError(f"scores.csv hash mismatch: {scores_hash}")
    if summary_hash != EXPECTED_SUMMARY_SHA256:
        raise ValueError(f"summary.json hash mismatch: {summary_hash}")
    summary = _load_json(source_summary)
    manifest = _load_json(source_manifest)
    if summary.get("benchmark_name") != EXPECTED_BENCHMARK:
        raise ValueError("unexpected benchmark name")
    if summary.get("benchmark_version") != EXPECTED_VERSION:
        raise ValueError("unexpected benchmark version")
    if summary.get("run_id") != EXPECTED_RUN_ID:
        raise ValueError("unexpected run ID")
    if manifest.get("git_commit") != EXPECTED_COMMIT:
        raise ValueError("methodology source commit does not match preserved run")
    if summary["results"]["thresholds"] != EXPECTED_THRESHOLDS:
        raise ValueError("preserved thresholds do not match verified values")
    rows = _read_scores(source_scores)
    if len(rows) != 984:
        raise ValueError(f"expected 984 score rows, found {len(rows)}")
    exported = exported_at_utc or datetime.now(UTC).isoformat()
    datetime.fromisoformat(exported.replace("Z", "+00:00"))
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_scores, output_dir / "scores.csv")
    shutil.copyfile(source_summary, output_dir / "summary.json")
    comparison = _comparison(rows)
    methodology = _methodology(summary, manifest, rows, exported)
    provenance = {
        "schema_version": "2.0",
        "benchmark_name": manifest["benchmark_name"],
        "benchmark_version": manifest["benchmark_version"],
        "run_id": summary["run_id"],
        "dataset_name": manifest["dataset_name"],
        "dataset_manifest_sha256": manifest["dataset_manifest_sha256"],
        "repository_url": manifest["repository_url"],
        "methodology_source_commit": manifest["git_commit"],
        "dirty_worktree_at_execution": manifest["dirty_worktree"],
        "config_name": Path(manifest["config_path"]).name,
        "config_sha256": manifest["config_sha256"],
        "python_version": manifest["python_version"],
        "dependencies": {
            name: manifest["dependencies"][name] for name in ("numpy", "pandas", "scipy")
        },
        "started_at_utc": manifest["started_at_utc"],
        "completed_at_utc": manifest["completed_at_utc"],
        "exported_at_utc": exported,
        "seed": manifest["seed"],
        "execution_status": manifest["status"],
        "scientific_review_status": "unapproved",
        "run_id_approved_token": "internal artifact label only",
        "verified_artifacts": {
            "summary.json": summary_hash,
            "scores.csv": scores_hash,
        },
        "redacted_fields": [
            "input_location",
            "output_location",
            "local_config_path",
            "image_reference",
            "image_digest",
            "azure_resource_type",
            "azure_compute_size",
            "Azure resource identifiers",
        ],
    }
    _write_json(output_dir / "comparison.json", comparison)
    _write_json(output_dir / "methodology.json", methodology)
    _write_table(output_dir / "methodology-table.csv", methodology["methodology_table"])
    _write_json(output_dir / "provenance.redacted.json", provenance)
    _write_json(output_dir / "data-dictionary.json", _dictionary(exported))
    (output_dir / "README.txt").write_text(
        """IMS BENCHMARK PUBLICATION DATA EXPORT

This folder contains derived IMS benchmark data and exact implementation-traced
methodology for run ims-20260718-approved-v1. It contains no raw vibration
recordings, credentials, tokens, signed URLs, private storage locations, or
Azure resource identifiers.

Files:
- scores.csv: byte-identical verified per-recording scores.
- summary.json: byte-identical verified run summary.
- comparison.json: derived MCIFT-versus-conventional warning comparison.
- methodology.json: equations, algorithms, normalization, channel evidence,
  persistence semantics, missing-data policy, observed quality counts, status
  explanation, evidence links, and explicit unverifiable fields.
- methodology-table.csv: complete flat methodology evidence table.
- provenance.redacted.json: allowlisted reproducibility and timestamp facts.
- data-dictionary.json: field and file definitions.

The executed implementation uses all four IMS Set-2 columns. It does not select
a single bearing. Accelerometer direction and a bearing-specific end-of-test
fault are not verifiable from the preserved run and are not guessed here.

Three consecutive observations at ten-minute timestamp spacing span 20 minutes
between the first and third timestamps. The warning timestamp is the first
positive in that qualifying run. Lead time is measured to the final experiment
recording, not to a verified physical degradation onset.

The word "approved" in the run ID is an internal artifact label. Execution
completed, but scientific_review_status is unapproved and is authoritative for
publication. This export does not establish MCIFT superiority and does not
approve publication automatically.
""",
        encoding="utf-8",
    )
    if _sha256(output_dir / "scores.csv") != scores_hash:
        raise RuntimeError("exported scores.csv is not byte-identical")
    if _sha256(output_dir / "summary.json") != summary_hash:
        raise RuntimeError("exported summary.json is not byte-identical")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a redacted, evidence-pinned IMS export")
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--exported-at-utc")
    args = parser.parse_args()
    export_ims_run(args.source_run, args.output_dir, args.exported_at_utc)


if __name__ == "__main__":
    main()
