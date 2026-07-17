from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from mcift_benchmarks.provenance import load_manifest, sha256_file, validate_publication_manifest


def validate_release(release: Path, schema_path: Path) -> None:
    manifest = load_manifest(release / "manifest.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(manifest)
    validate_publication_manifest(manifest)
    for artifact in manifest["artifacts"]:
        path = (release / artifact["path"]).resolve()
        if release.resolve() not in path.parents:
            raise ValueError("artifact path escapes release directory")
        if sha256_file(path) != artifact["sha256"]:
            raise ValueError(f"checksum mismatch: {artifact['path']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    args = parser.parse_args()
    validate_release(args.release, args.schema)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
