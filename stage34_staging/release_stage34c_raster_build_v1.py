#!/usr/bin/env python3
"""Issue the fail-closed Stage34C raster-build authority from corrected audit v3."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
AUDIT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_03/placement_audit.json"
AUDIT_COMPLETION = AUDIT.parent / "completion.json"
PLACEMENT = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_search_02/placement_manifest.json"
PLACEMENT_COMPLETION = PLACEMENT.parent / "completion.json"
OUTPUT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_04"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable release: {OUTPUT}")
    audit, audit_done, placement, placement_done = map(load, (AUDIT, AUDIT_COMPLETION, PLACEMENT, PLACEMENT_COMPLETION))
    checks = {
        "corrected_audit_passed": audit.get("passed") is True and audit_done.get("passed") is True,
        "corrected_completion_binds_audit": audit_done.get("placement_audit_sha256") == sha(AUDIT),
        "corrected_audit_binds_placement": audit["source_bindings"]["placement"]["sha256"] == sha(PLACEMENT),
        "placement_completion_passed": placement_done.get("passed") is True,
        "placement_completion_binds_manifest": placement_done.get("placement_manifest_sha256") == sha(PLACEMENT),
        "raster_build_authorized_upstream": audit["authority"].get("raster_geometry_build") is True,
        "gpu_flow_still_forbidden": audit["authority"].get("gpu_flow_execution") is False,
        "all_selected_screens_pass": all(
            state["raster_screen"][level]["passed"]
            for packing in placement["packings"].values()
            for state in packing["blocks"].values()
            for level in ("frag2", "frag3")
        ),
    }
    passed = all(checks.values())
    authority = {
        "geometry_rasterization": passed,
        "raster_geometry_build": passed,
        "independent_raster_audit": False,
        "gpu_flow_execution": False,
        "cpd6_flow_execution": False,
        "mechanics_or_coupling": False,
    }
    release = {
        "schema": "lbs.stage34c-raster-build-release.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_raster_build_release" if passed else "failed_raster_build_release",
        "checks": checks,
        "source_bindings": {
            "corrected_audit": {"path": str(AUDIT.resolve()), "sha256": sha(AUDIT)},
            "corrected_audit_completion": {"path": str(AUDIT_COMPLETION.resolve()), "sha256": sha(AUDIT_COMPLETION)},
            "placement": {"path": str(PLACEMENT.resolve()), "sha256": sha(PLACEMENT)},
            "placement_completion": {"path": str(PLACEMENT_COMPLETION.resolve()), "sha256": sha(PLACEMENT_COMPLETION)},
            "release_script": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())},
        },
        "authority": authority,
        "claim_boundary": placement["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    release_path = OUTPUT / "placement_audit.json"
    release_path.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {
        "schema": release["schema"] + ".completion",
        "passed": passed,
        "status": release["status"],
        "placement_audit_sha256": sha(release_path),
        "checks": checks,
        "authority": authority,
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "status": release["status"], "failed_checks": [k for k, v in checks.items() if not v]}, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
