from __future__ import annotations

import json
from pathlib import Path

from mcift_benchmarks.ims_export import (
    EXPECTED_SCORES_SHA256,
    _comparison,
    _data_quality,
    _read_scores,
    _sha256,
)

REPOSITORY = Path(__file__).resolve().parents[3]
SCORES = REPOSITORY / "results" / "ims" / "ims-20260718-approved-v1" / "scores.csv"


def test_preserved_scores_and_derived_comparison() -> None:
    rows = _read_scores(SCORES)
    comparison = _comparison(rows)
    quality = _data_quality(rows)
    assert _sha256(SCORES) == EXPECTED_SCORES_SHA256
    assert comparison["mcift"]["stable_run_start_index"] == 532
    assert comparison["conventional"]["stable_run_start_index"] == 537
    assert comparison["comparison"]["superiority_verdict"] == "not established"
    assert quality["loaded_recordings"] == 984
    assert quality["duplicate_timestamps_in_scores"] == 0
    assert quality["observed_inter_recording_intervals"]["ten_minute_count"] == 983


def test_public_methodology_has_required_status_and_evidence() -> None:
    methodology_path = REPOSITORY / "exports" / "ims-data-handoff" / "methodology.json"
    if not methodology_path.exists():
        return
    methodology = json.loads(methodology_path.read_text(encoding="utf-8"))
    assert methodology["scientific_review_status"] == "unapproved"
    assert methodology["selection"]["bearings"] == [1, 2, 3, 4]
    assert methodology["selection"]["accelerometer_direction"].startswith("Not verifiable")
    assert methodology["thresholds"]["quantile_method"].startswith("linear")
    assert methodology["observed_data_quality"]["loaded_recordings"] == 984
