#!/usr/bin/env python3
"""Single-owner background supervisor for the immutable Stage27b GPU run."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = "stage27b_stage26x_mechanics_hydraulic_cpd4_20260824"
SUPERVISOR = ROOT / "stage27_supervisors" / STUDY / "gpu_confirmation_01"
OUTPUT = ROOT / "stage27_runs" / STUDY / "gpu_confirmation_01"
RUNNER = ROOT / "stage27_staging/run_stage27b_cpd4_confirmation_v1.py"
CONFIG = ROOT / "stage27_designs" / STUDY / "geometry_01/resolved_config.json"
HANDOFF = ROOT / "stage27_evaluations" / STUDY / "design_audit_01/execution_handoff.json"

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def main() -> int:
    if SUPERVISOR.exists() or OUTPUT.exists():
        raise FileExistsError("immutable supervisor or output already exists")
    SUPERVISOR.mkdir(parents=True)
    command = [sys.executable, str(RUNNER), "--config", str(CONFIG), "--handoff", str(HANDOFF), "--output", str(OUTPUT)]
    write(SUPERVISOR / "launch_manifest.json", {"schema": "lbs.stage27b-cpd4-supervisor.v1", "status": "running", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "command": command, "runner_sha256": digest(RUNNER), "config_sha256": digest(CONFIG), "handoff_sha256": digest(HANDOFF)})
    (SUPERVISOR / "status.txt").write_text("running\n", encoding="utf-8")
    with (SUPERVISOR / "stdout.log").open("wb") as stdout, (SUPERVISOR / "stderr.log").open("wb") as stderr:
        code = subprocess.call(command, cwd=ROOT, stdout=stdout, stderr=stderr)
    (SUPERVISOR / "exit_code.txt").write_text(str(code) + "\n", encoding="utf-8")
    status = "completed" if code == 0 and (OUTPUT / "completion.json").is_file() else "failed"
    (SUPERVISOR / "status.txt").write_text(status + "\n", encoding="utf-8")
    return code

if __name__ == "__main__":
    raise SystemExit(main())

