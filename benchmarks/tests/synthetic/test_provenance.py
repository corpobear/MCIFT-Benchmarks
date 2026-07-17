import pytest

from mcift_benchmarks.provenance import validate_publication_manifest


def test_publication_rejects_missing_provenance() -> None:
    with pytest.raises(ValueError, match="missing provenance"):
        validate_publication_manifest({"status": "approved"})
