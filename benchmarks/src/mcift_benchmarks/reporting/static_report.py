from __future__ import annotations

import html
import json
from pathlib import Path

from mcift_benchmarks.provenance import load_manifest, validate_publication_manifest


def build_static_report(run_dir: Path, output: Path) -> None:
    manifest = load_manifest(run_dir / "manifest.json")
    validate_publication_manifest(manifest)
    payload = html.escape(json.dumps(manifest, indent=2, sort_keys=True))
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>MCIFT benchmark</title>"
        "<link rel='stylesheet' href='../assets/style.css'></head><body>"
        f"<h1>{html.escape(str(manifest['benchmark_name']))}</h1>"
        "<p>Reviewed benchmark release. See provenance below.</p>"
        f"<pre>{payload}</pre></body></html>",
        encoding="utf-8",
    )
