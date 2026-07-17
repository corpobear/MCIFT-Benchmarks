from __future__ import annotations

import hashlib
import json
import platform
from importlib.metadata import distributions
from pathlib import Path
from typing import Any

REQUIRED_PROVENANCE = {
    "benchmark_name",
    "benchmark_version",
    "dataset_name",
    "dataset_manifest_sha256",
    "repository_url",
    "git_commit",
    "dirty_worktree",
    "image_reference",
    "image_digest",
    "config_path",
    "config_sha256",
    "python_version",
    "dependencies",
    "azure_resource_type",
    "azure_compute_size",
    "started_at_utc",
    "completed_at_utc",
    "seed",
    "input_location",
    "output_location",
    "status",
    "artifacts",
}


def dependency_versions() -> dict[str, str]:
    return {
        dist.metadata["Name"]: dist.version for dist in distributions() if dist.metadata["Name"]
    }


def runtime_facts() -> dict[str, Any]:
    return {"python_version": platform.python_version(), "dependencies": dependency_versions()}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_publication_manifest(manifest: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_PROVENANCE - manifest.keys())
    if missing:
        raise ValueError(f"publication rejected; missing provenance: {', '.join(missing)}")
    if manifest["status"] != "approved":
        raise ValueError("publication rejected; run status is not approved")
    for artifact in manifest["artifacts"]:
        if not artifact.get("sha256"):
            raise ValueError("publication rejected; artifact checksum missing")


def load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    return value
