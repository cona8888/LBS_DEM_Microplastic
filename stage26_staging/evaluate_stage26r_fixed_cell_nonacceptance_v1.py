#!/usr/bin/env python3
"""Freeze the Stage26r clean fixed-cell result as an immutable nonacceptance."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "clean_radius_restoration_05"
SUPERVISOR = ROOT / "stage26_supervisors" / "stage26r_periodic_radius_restoration_20260819" / "clean_radius_restoration_05"
DESIGN = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_05" / "config.json"
RUNNER = ROOT / "stage26_staging" / "run_stage26r_periodic_radius_restoration_v3.py"
SMOKE = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "fixed_cell_smoke_04" / "result.json"
OUT = ROOT / "stage26_evaluations" / "stage26r_periodic_radius_restoration_20260819" / "clean_radius_restoration_evaluation_05"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    require(not OUT.exists(), f"refusing to overwrite {OUT}")
    required = [
        RUN / "result.json",
        RUN / "completion.json",
        RUN / "history.csv",
        SUPERVISOR / "launch_manifest.txt",
        SUPERVISOR / "runner_exit_code.txt",
        SUPERVISOR / "stdout.log",
        SUPERVISOR / "stderr.log",
        DESIGN,
        RUNNER,
        SMOKE,
    ]
    for path in required:
        require(path.is_file(), f"missing required evidence: {path}")

    result = read_json(RUN / "result.json")
    completion = read_json(RUN / "completion.json")
    smoke = read_json(SMOKE)
    design = read_json(DESIGN)
    exit_code = int((SUPERVISOR / "runner_exit_code.txt").read_text(encoding="utf-8").strip())
    stderr = (SUPERVISOR / "stderr.log").read_text(encoding="utf-8", errors="replace")

    require(sha256(RUN / "result.json") == completion["result"]["sha256"], "completion/result hash mismatch")
    require(sha256(RUN / "history.csv") == result["artifacts"]["history"]["sha256"], "result/history hash mismatch")
    require(sha256(DESIGN) == result["source_hashes"]["config"], "design hash mismatch")
    require(sha256(RUNNER) == result["source_hashes"]["runner"], "runner hash mismatch")
    require(smoke.get("passed") is True, "fixed-cell synchronization smoke did not pass")
    require(result["status"] == completion["status"] == "fixed_cell_hold_not_qualified", "unexpected status")
    require(result["passed"] is False and completion["passed"] is False, "nonacceptance was not preserved")
    require(exit_code == 2, "expected fail-closed runner exit code 2")
    require("Traceback" not in stderr and "Exception" not in stderr, "unexpected software exception in stderr")

    terminal = result["terminal"]
    exact_geometry = (
        result["checks"]["unchanged_cell"]
        and result["checks"]["void_ratio"]
        and result["checks"]["exact_radii"]
        and terminal["maximum_relative_cell_dimension_change"] == 0.0
        and terminal["maximum_relative_radius_error"] <= 1.0e-12
    )
    unjammed = (
        terminal["mean_stress_pa_compression_positive"] == 0.0
        and terminal["real_contact_count"] == 0
        and terminal["load_bearing_particle_count"] == 0
        and terminal["coordination_excluding_rattlers"] == 0.0
        and terminal["rattler_fraction"] == 1.0
    )
    require(exact_geometry, "fixed-cell/radius restoration geometry was not exact")
    require(unjammed, "terminal state does not match the observed unjamming mechanism")

    OUT.mkdir(parents=True)
    sources = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in required}
    evaluation = {
        "schema": "lbs.stage26r-fixed-cell-nonacceptance-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "classification": "verified_physical_protocol_nonacceptance",
        "finding": (
            "The density-matched 216-sphere state retains exact cell dimensions, void ratio, and restored radii, "
            "but loses every contact and all confining stress when the periodic cell is held fixed. The earlier "
            "cell-drift defect is corrected; the remaining failure is an unjammed state that depended on the "
            "active stress controller, not a software integration error."
        ),
        "checks": {
            "source_chain_bound": True,
            "synchronization_smoke_passed": True,
            "fixed_cell_exact": True,
            "restored_radii_exact": True,
            "void_ratio_retained": True,
            "terminal_unjamming_observed": True,
            "no_software_exception": True,
            "nonacceptance_preserved": True,
        },
        "terminal": terminal,
        "decision": {
            "repeat_radius_restoration": False,
            "use_fixed_cell_state_for_mixture": False,
            "use_stage25_stress_controlled_state_for_future_sand_mechanics": True,
            "standalone_flexible_fibre_cantilever_design_authorized": True,
            "standalone_flexible_fibre_cantilever_execution_authorized": False,
            "sand_fibre_mixture_authorized": False,
            "flow_authorized": False,
        },
        "claim_boundary": (
            "Protocol diagnosis for one 216-sphere periodic state only; no fibre, mixture, permeability, "
            "representative-volume, deformation, or production-parametric claim."
        ),
        "source_hashes": sources,
        "design_metadata": {
            "schema": design.get("schema"),
            "case_id": design.get("case_id"),
        },
    }
    evaluation_path = OUT / "evaluation.json"
    evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    checkpoint = {
        "schema": "lbs.stage26r-fixed-cell-nonacceptance-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "stage26r_closed_nonaccepting",
        "evaluation": {
            "path": str(evaluation_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(evaluation_path),
        },
        "next_gate": (
            "A separately frozen Stage26s contract may authorize only a standalone, nonperiodic flexible-fibre "
            "cantilever verification. Sand-mixture and flow execution remain prohibited."
        ),
    }
    checkpoint_path = OUT / "checkpoint_manifest.json"
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"evaluation": str(evaluation_path), "evaluation_sha256": sha256(evaluation_path),
                      "checkpoint": str(checkpoint_path), "checkpoint_sha256": sha256(checkpoint_path)}, indent=2))


if __name__ == "__main__":
    main()
