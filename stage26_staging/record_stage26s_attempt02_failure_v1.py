#!/usr/bin/env python3
"""Freeze Stage26s attempt-02 as a bending-timestep instability diagnosis."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage26_runs" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_02"
SUP = ROOT / "stage26_supervisors" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_02"
OUT = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_02_failure"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite {OUT}")
result_path = RUN / "result.json"
completion_path = RUN / "completion.json"
for path in (result_path, completion_path, SUP / "runner_exit_code.txt", SUP / "stdout.log", SUP / "stderr.log"):
    if not path.is_file():
        raise RuntimeError(f"missing {path}")
result = json.loads(result_path.read_text(encoding="utf-8"))
completion = json.loads(completion_path.read_text(encoding="utf-8"))
if completion["result"]["sha256"] != sha(result_path):
    raise RuntimeError("result binding mismatch")
if result["passed"] or result["status"] != "cantilever_not_qualified":
    raise RuntimeError("unexpected attempt status")
by_n = {m["node_count"]: m for m in result["meshes"]}
if by_n[19]["analytical_relative_error"] >= 0.01:
    raise RuntimeError("coarse mesh did not demonstrate the expected constitutive response")
if by_n[73]["terminal_deflection_over_length"] <= 1.0:
    raise RuntimeError("fine-mesh instability signature absent")

segment = by_n[73]["segment_length_m"]
E = result["inputs"]["young_pa"]
I = result["analytical"]["second_moment_area_m4"]
transverse_stiffness = 12.0 * E * I / segment ** 3
payload = {
    "schema": "lbs.stage26s-cantilever-attempt-failure.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "attempt": "cantilever_02",
    "classification": "fine_mesh_timestep_instability",
    "physics_result": False,
    "finding": (
        "The 19-node response agreed with Euler-Bernoulli theory, while the 73-node response diverged. "
        "The timestep used axial EA/L scaling and omitted the more restrictive transverse beam stiffness 12EI/L^3."
    ),
    "diagnostic": {
        "mesh_19_analytical_relative_error": by_n[19]["analytical_relative_error"],
        "mesh_73_segment_length_m": segment,
        "mesh_73_transverse_stiffness_n_per_m": transverse_stiffness,
        "mesh_73_diverged_deflection_over_length": by_n[73]["terminal_deflection_over_length"],
    },
    "permitted_correction": (
        "Use the maximum of axial and 12EI/L^3 stiffness for timestep selection and preserve comparable physical ramp/hold durations across meshes."
    ),
    "scientific_gate_changes_authorized": False,
    "source_hashes": {
        "result": sha(result_path),
        "completion": sha(completion_path),
        "stdout": sha(SUP / "stdout.log"),
        "stderr": sha(SUP / "stderr.log"),
        "exit_code": sha(SUP / "runner_exit_code.txt"),
    },
}
OUT.mkdir(parents=True)
path = OUT / "failure.json"
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"failure": str(path), "sha256": sha(path)}, indent=2))
