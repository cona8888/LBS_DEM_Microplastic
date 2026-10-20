#!/usr/bin/env python3
"""Persistent single-job supervisor for the immutable Stage24e GPU run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--supervisor-root", type=Path, required=True)
    args = parser.parse_args()
    config, runner = args.config.resolve(), args.runner.resolve()
    output, supervisor = args.output.resolve(), args.supervisor_root.resolve()
    if output.exists() or supervisor.exists():
        raise FileExistsError("refusing to overwrite Stage24e output or supervisor evidence")
    supervisor.mkdir(parents=True)
    command = [sys.executable, str(runner), "--config", str(config), "--output", str(output)]
    launch = {
        "schema": "lbs.stage24e-lbs-f37-selected-cpd4-gpu.v1.launch",
        "timestamp_utc": now(),
        "supervisor_pid": os.getpid(),
        "command": command,
        "config_sha256": digest(config),
        "runner_sha256": digest(runner),
        "supervisor_sha256": digest(Path(__file__).resolve()),
        "output": str(output),
    }
    atomic_json(supervisor / "launch_manifest.json", launch)
    stdout_path, stderr_path = supervisor / "run.stdout.log", supervisor / "run.stderr.log"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        atomic_json(supervisor / "status.json", {**launch, "status": "running", "child_pid": process.pid})
        return_code = process.wait()
    final = {
        **launch,
        "status": "completed" if return_code == 0 else "failed_preserved",
        "child_pid": process.pid,
        "return_code": return_code,
        "completed_utc": now(),
        "stdout_sha256": digest(stdout_path),
        "stderr_sha256": digest(stderr_path),
        "completion_sha256": digest(output / "completion.json") if (output / "completion.json").exists() else None,
        "failure_sha256": digest(output / "failure.json") if (output / "failure.json").exists() else None,
    }
    atomic_json(supervisor / "status.json", final)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
