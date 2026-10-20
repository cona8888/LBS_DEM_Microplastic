#!/usr/bin/env python3
"""Independent fail-closed audit of the Stage31b nested placement design."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN_DIR = ROOT / "stage31_designs/stage31b_nested_concentration_replication_20260826/design_01"
DESIGN = DESIGN_DIR / "design_manifest.json"
COMPLETION = DESIGN_DIR / "completion.json"
OUTPUT = ROOT / "stage31_evaluations/stage31b_nested_concentration_replication_20260826/design_audit_01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def segment_distance(first: dict, second: dict) -> float:
    p1, q1 = np.asarray(first["rear_m"]), np.asarray(first["tip_m"])
    p2, q2 = np.asarray(second["rear_m"]), np.asarray(second["tip_m"])
    u, v, w = q1 - p1, q2 - p2, p1 - p2
    a, b, c = float(u @ u), float(u @ v), float(v @ v)
    d, e = float(u @ w), float(v @ w)
    denominator = a * c - b * b
    if denominator < 1.0e-30:
        s_num, s_den, t_num, t_den = 0.0, 1.0, e, c
    else:
        s_num, s_den = b * e - c * d, denominator
        t_num, t_den = a * e - b * d, denominator
        if s_num < 0.0:
            s_num, t_num, t_den = 0.0, e, c
        elif s_num > s_den:
            s_num, t_num, t_den = s_den, e + b, c
    if t_num < 0.0:
        t_num, s_num, s_den = 0.0, min(max(-d, 0.0), a), a
    elif t_num > t_den:
        t_num, s_num, s_den = t_den, min(max(b - d, 0.0), a), a
    s = 0.0 if abs(s_num) < 1.0e-30 else s_num / s_den
    t = 0.0 if abs(t_num) < 1.0e-30 else t_num / t_den
    return float(np.linalg.norm(w + s * u - t * v))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    design, completion = load(DESIGN), load(COMPLETION)
    source_checks = {}
    for key, binding in design["source_bindings"].items():
        if key in {"n216_s1", "n216_s2", "n216_s3"}:
            source_checks[key + "_network"] = digest(Path(binding["network"]["path"])) == binding["network"]["sha256"]
            source_checks[key + "_paths"] = digest(Path(binding["paths"]["path"])) == binding["paths"]["sha256"]
        elif isinstance(binding, dict) and "path" in binding:
            source_checks[key] = digest(Path(binding["path"])) == binding["sha256"]
    checks = {
        "completion_passed": completion.get("passed") is True,
        "completion_binding": completion.get("design_manifest_sha256") == digest(DESIGN),
        "source_hashes": all(source_checks.values()),
        "three_packings": set(design["blocks"]) == {"n216_s1", "n216_s2", "n216_s3"},
        "two_blocks_each": all(set(value) == {"A", "B"} for value in design["blocks"].values()),
        "case_count": len(design["cases"]) == 21,
        "clean_count": sum(case["fibre_count"] == 0 for case in design["cases"]) == 3,
        "nonclean_count": sum(case["fibre_count"] > 0 for case in design["cases"]) == 18,
        "unique_case_ids": len({case["case_id"] for case in design["cases"]}) == 21,
        "unique_run_order": sorted(case["frozen_randomized_nonclean_run_order"] for case in design["cases"] if case["fibre_count"] > 0) == list(range(1, 19)),
        "authority_closed": design["authority"] == {"geometry_audit": True, "fibre_mechanics_execution": False, "flow": False, "permeability_claim": False, "coupling": False},
    }
    block_audits = []
    global_min_clearance = math.inf
    for packing, blocks in design["blocks"].items():
        seen_faces, seen_grains = set(), set()
        for block_name, rows in blocks.items():
            pair_clearances = [segment_distance(a, b) - 2.0 * design["fibre"]["radius_m"] for a, b in itertools.combinations(rows, 2)]
            minimum = min(pair_clearances)
            global_min_clearance = min(global_min_clearance, minimum)
            faces = {row["face_index"] for row in rows}
            grains = set().union(*(set(row["face_body_ids"]) for row in rows))
            audit_checks = {
                "four_paths": len(rows) == 4,
                "nested_rank": [row["nested_rank"] for row in rows] == [1, 2, 3, 4],
                "open_throats": all(row["throat_to_fibre_radius_ratio"] >= design["selection"]["minimum_throat_to_fibre_radius_ratio"] for row in rows),
                "initial_grain_clearance": all(row["initial_minimum_surface_clearance_m"] >= design["selection"]["minimum_initial_grain_surface_clearance_m"] for row in rows),
                "interfibre_clearance": minimum >= design["selection"]["minimum_interfibre_surface_clearance_m"] - 1.0e-12,
                "face_grains_disjoint_within_block": sum(len(row["face_body_ids"]) for row in rows) == len(grains),
                "faces_not_reused_between_blocks": faces.isdisjoint(seen_faces),
                "face_grains_not_reused_between_blocks": grains.isdisjoint(seen_grains),
            }
            seen_faces.update(faces)
            seen_grains.update(grains)
            block_audits.append({"packing_id": packing, "block": block_name, "passed": all(audit_checks.values()), "checks": audit_checks, "minimum_interfibre_surface_clearance_m": minimum, "flow_axis_alignment": [abs(row["pull_direction"][0]) for row in rows]})
    checks["all_blocks"] = all(item["passed"] for item in block_audits)
    for packing in design["blocks"]:
        for block in ("A", "B"):
            cases = {case["fibre_count"]: case for case in design["cases"] if case["packing_id"] == packing and case["placement_block"] == block}
            checks[f"{packing}_{block}_nested_cases"] = set(cases) == {1, 2, 4} and all(cases[count]["centrelines"] == design["blocks"][packing][block][:count] for count in (1, 2, 4))
            concentrations = [cases[count]["achieved_dry_mass_percent"] for count in (1, 2, 4)]
            checks[f"{packing}_{block}_positive_ordered_concentration"] = 0.0 < concentrations[0] < concentrations[1] < concentrations[2]
    passed = all(checks.values())
    audit = {
        "schema": "lbs.stage31b-nested-concentration-replication.v1.design-audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_geometry_design_audit" if passed else "failed_closed",
        "checks": checks,
        "source_checks": source_checks,
        "block_audits": block_audits,
        "metrics": {"minimum_interfibre_surface_clearance_m": global_min_clearance},
        "decision": "The 21-case nested design is geometrically admissible. A separate mechanics preflight may be built, but mechanics execution and flow remain unauthorized.",
        "authority": {"mechanics_preflight_design": passed, "fibre_mechanics_execution": False, "flow": False, "coupling": False},
        "claim_boundary": design["claim_boundary"],
        "source_hashes": {"design": digest(DESIGN), "completion": digest(COMPLETION), "auditor": digest(Path(__file__).resolve())},
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "design_audit.json"
    path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "checkpoint_manifest.json").write_text(json.dumps({"schema": "lbs.stage31b-design-audit.v1.checkpoint", "passed": passed, "audit_sha256": digest(path), "design_sha256": digest(DESIGN)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "status": audit["status"], "metrics": audit["metrics"]}, sort_keys=True))
    if not passed:
        raise SystemExit(4)


if __name__ == "__main__":
    main()

