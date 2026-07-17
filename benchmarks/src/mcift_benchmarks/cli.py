from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from mcift_benchmarks.config import load_config
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
        load_config(args.config)
        require_safe_blob_uri(args.input)
        require_safe_blob_uri(args.output)
        raise NotImplementedError("scientific run blocked until MCIFT adapter is reviewed")
    if args.command == "build-report":
        build_static_report(Path(args.run), Path(args.output))
        return 0
    raise AssertionError("unreachable")
