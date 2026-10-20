#!/usr/bin/env python3
"""Freeze the pre-integration Stage26s attempt-01 construction failure."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
SUP = ROOT / "stage26_supervisors" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_01"
OUT = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_01_failure"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite {OUT}")
for name in ("launch_manifest.txt", "stdout.log", "stderr.log", "runner_exit_code.txt"):
    if not (SUP / name).is_file():
        raise RuntimeError(f"missing {name}")
stderr = (SUP / "stderr.log").read_text(encoding="utf-8", errors="replace")
if "No IGeomDispatcher in engines or inside InteractionLoop" not in stderr:
    raise RuntimeError("unexpected failure signature")
if (SUP / "runner_exit_code.txt").read_text(encoding="utf-8").strip() != "1":
    raise RuntimeError("unexpected exit code")
OUT.mkdir(parents=True)
payload = {
    "schema": "lbs.stage26s-cantilever-attempt-failure.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "attempt": "cantilever_01",
    "classification": "pre_integration_scene_construction_ordering_error",
    "physics_result": False,
    "finding": "Grid connections were created before YADE's IGeomDispatcher was installed; zero benchmark timesteps were integrated.",
    "permitted_correction": "Install the unchanged engine/dispatcher list before creating grid connections in a new runner and immutable design.",
    "gate_changes_authorized": False,
    "source_hashes": {name: sha(SUP / name) for name in ("launch_manifest.txt", "stdout.log", "stderr.log", "runner_exit_code.txt")},
}
path = OUT / "failure.json"
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"failure": str(path), "sha256": sha(path)}, indent=2))
