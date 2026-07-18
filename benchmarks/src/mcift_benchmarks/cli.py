from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from mcift_benchmarks.config import load_config, require_scientifically_resolved, unresolved_paths
from mcift_benchmarks.reporting.static_report import build_static_report
from mcift_benchmarks.storage import require_safe_blob_uri


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="MCIFT benchmark preparation CLI")
    commands = root.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-config")
    validate.add_argument("--config", required=True)
    inspect = commands.add_parser("inspect-input")
    inspect.add_argument("--dataset", choices=("ims", "exathlon"), required=True)
    inspect.add_argument("--input", required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--input", required=True)
    run.add_argument("--output", required=True)
    preflight = commands.add_parser("preflight-run")
    preflight.add_argument("--config", required=True)
    preflight.add_argument("--input", required=True)
    preflight.add_argument("--output", required=True)
    report = commands.add_parser("build-report")
    report.add_argument("--run", required=True)
    report.add_argument("--output", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "validate-config":
        config = load_config(args.config)
        print(json.dumps({"valid": True, "sha256": config.sha256}))
        return 0
    if args.command == "inspect-input":
        require_safe_blob_uri(args.input)
        path = urlparse(args.input).path
        if f"/datasets/{args.dataset}/" not in path:
            raise ValueError("input URI does not match selected dataset prefix")
        print(json.dumps({"dataset": args.dataset, "location_valid": True}))
        return 0
    if args.command == "run":
        config = load_config(args.config)
        require_safe_blob_uri(args.input)
        require_safe_blob_uri(args.output)
        require_scientifically_resolved(config)
        raise NotImplementedError("scientific run blocked until MCIFT adapter is reviewed")
    if args.command == "preflight-run":
        config = load_config(args.config)
        require_safe_blob_uri(args.input)
        require_safe_blob_uri(args.output)
        unresolved = unresolved_paths(config.raw)
        print(
            json.dumps(
                {
                    "ready": not unresolved,
                    "config_sha256": config.sha256,
                    "unresolved": unresolved,
                    "mcift_adapter_implemented": True,
                    "mcift_adapter_approved": "mcift.approval" not in unresolved,
                },
                indent=2,
            )
        )
        return 2 if unresolved else 0
    if args.command == "build-report":
        build_static_report(Path(args.run), Path(args.output))
        return 0
    raise AssertionError("unreachable")
