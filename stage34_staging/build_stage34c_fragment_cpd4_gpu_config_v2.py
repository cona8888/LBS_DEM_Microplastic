#!/usr/bin/env python3
"""Supersede Stage34C config_01 solely to bind the corrected release-target supervisor."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage34c_cpd4_first_fragmentation_geometry_20260902"
OLD_CONFIG = ROOT / "stage34_designs" / STUDY / "gpu_config_01/resolved_config.json"
OLD_COMPLETION = OLD_CONFIG.parent / "completion.json"
OLD_RELEASE_AUDIT = ROOT / "stage34_evaluations" / STUDY / "execution_release_02/release_audit.json"
OLD_HANDOFF = OLD_RELEASE_AUDIT.parent / "handoff.json"
RUNNER = ROOT / "stage34_staging/run_stage34c_fragment_cpd4_gpu_v1.py"
SUPERVISOR = ROOT / "stage34_staging/supervise_stage34c_fragment_cpd4_gpu_v2.ps1"
OUTPUT = ROOT / "stage34_designs" / STUDY / "gpu_config_02"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def bind(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"required immutable evidence missing: {path}")
    return {"path": str(path), "sha256": sha(path)}


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable superseding configuration: {OUTPUT}")
    for path in (OLD_CONFIG, OLD_COMPLETION, OLD_RELEASE_AUDIT, OLD_HANDOFF, RUNNER, SUPERVISOR):
        if not path.is_file():
            raise RuntimeError(f"required immutable evidence missing: {path}")
    old, old_done, old_release, old_handoff = map(load, (OLD_CONFIG, OLD_COMPLETION, OLD_RELEASE_AUDIT, OLD_HANDOFF))
    if not (old_done.get("passed") and old_done.get("config_sha256") == sha(OLD_CONFIG)):
        raise RuntimeError("config_01 is not complete and hash-bound")
    if not (old_release.get("passed") and old_handoff.get("passed")
            and old_handoff["bindings"]["config_sha256"] == sha(OLD_CONFIG)):
        raise RuntimeError("execution_release_02 is not the accepted predecessor")
    old_supervisor = Path(old["lineage"]["supervisor"]["path"])
    if "execution_release_01" not in old_supervisor.read_text(encoding="utf-8"):
        raise RuntimeError("the predecessor supervisor-path defect is not reproduced")
    if "execution_release_03" not in SUPERVISOR.read_text(encoding="utf-8"):
        raise RuntimeError("corrected supervisor does not target the planned superseding handoff")

    config = copy.deepcopy(old)
    config["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    config["lineage"]["builder"] = bind(Path(__file__).resolve())
    config["lineage"]["supervisor"] = bind(SUPERVISOR)
    config["lineage"]["superseded_config_01"] = bind(OLD_CONFIG)
    config["lineage"]["superseded_config_01_completion"] = bind(OLD_COMPLETION)
    config["lineage"]["superseded_execution_release_02_audit"] = bind(OLD_RELEASE_AUDIT)
    config["lineage"]["superseded_execution_release_02_handoff"] = bind(OLD_HANDOFF)
    config["checks"]["superseding_supervisor_targets_execution_release_03"] = True
    config["checks"]["physics_geometry_solver_and_order_unchanged_from_config_01"] = True
    config["supersedes"] = {
        "reason": "config_01 bound a supervisor that targeted the preserved failed execution_release_01; no run was launched",
        "configuration": bind(OLD_CONFIG), "completion": bind(OLD_COMPLETION),
        "release_audit": bind(OLD_RELEASE_AUDIT), "handoff": bind(OLD_HANDOFF),
        "unchanged": ["research_question", "claim_boundary", "solver", "fluid", "execution", "acceptance",
                      "analysis", "geometry", "intact_contexts", "matched_clean_controls", "warm_starts", "run_order"],
    }
    config["authority"]["independent_gpu_release"] = False
    config["authority"]["gpu_cpd4_execution"] = False

    for key in config["supersedes"]["unchanged"]:
        if key == "run_order":
            before = [row["case_id"] for row in sorted(old["geometry"]["cases"], key=lambda row: row["run_order"])]
            after = [row["case_id"] for row in sorted(config["geometry"]["cases"], key=lambda row: row["run_order"])]
        else:
            before, after = old[key], config[key]
        if before != after:
            raise RuntimeError(f"unauthorized config change while correcting supervisor: {key}")

    OUTPUT.mkdir(parents=True)
    config_path = OUTPUT / "resolved_config.json"
    write(config_path, config)
    completion = {
        "schema": config["schema"] + ".config-completion.v2",
        "status": "passed_fragment_cpd4_configuration_supervisor_correction",
        "passed": True, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": sha(config_path), "case_count": len(config["geometry"]["cases"]),
        "run_order": [row["case_id"] for row in sorted(config["geometry"]["cases"], key=lambda row: row["run_order"])],
        "superseded_config_sha256": sha(OLD_CONFIG),
        "authority": config["authority"], "claim_boundary": config["claim_boundary"],
    }
    write(OUTPUT / "completion.json", completion)
    print(json.dumps({"passed": True, "config": str(config_path), "config_sha256": sha(config_path),
                      "completion": str(OUTPUT / 'completion.json'), "run_order": completion["run_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
