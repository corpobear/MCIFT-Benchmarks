import pytest

from mcift_benchmarks.config import load_config, unresolved_paths
from mcift_benchmarks.provenance import validate_publication_manifest


def test_publication_rejects_missing_provenance() -> None:
    with pytest.raises(ValueError, match="missing provenance"):
        validate_publication_manifest({"status": "approved"})


def test_approved_config_has_no_scientific_gaps() -> None:
    config = load_config("benchmarks/configs/ims-set2-v1.yaml")
    gaps = unresolved_paths(config.raw)
    assert gaps == []
