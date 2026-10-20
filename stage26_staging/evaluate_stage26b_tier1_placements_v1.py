"""Independently evaluate Stage26b Tier-1 multi-fibre geometry preflights."""

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_tier1_placement_preflight_v1.json"
PLACEMENT_ROOT = PROJECT / "stage26_placements" / "stage26b_dry_multifibre_20260814" / "tier1_preflight_01"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_dry_multifibre_20260814" / "tier1_placement_evaluation_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def periodic_delta(a, b, lengths):
    delta = a - b
    return delta - np.round(delta / lengths) * lengths


def evaluate_case(case, cfg, sand_centres, sand_radii, sand_ids):
    path = PLACEMENT_ROOT / case["case_id"] / "placement.json"
    placement = load_json(path)
    lengths = np.array(placement["cell_dimensions_m"], dtype=float)
    radius = float(placement["member_radius_m"])
    max_penetration = cfg["acceptance"]["maximum_sand_fibre_penetration_over_member_radius"] * radius
    target_penetration = cfg["search"]["target_anchor_penetration_over_member_radius"] * radius
    fibres = placement["fibres"]
    checks = {
        "placement_passed": placement.get("passed") is True,
        "case_binding": placement["case"] == case,
        "config_binding": placement["source_hashes"]["config"] == digest(CONFIG),
        "fibre_count_exact": len(fibres) == placement["fibre_count"] == case["fibre_count"],
        "members_per_fibre_exact": all(len(row["member_centres_m"]) == cfg["acceptance"]["members_per_fibre"] for row in fibres),
        "all_members_inside_primary_cell": True,
        "sand_penetration_within_limit": True,
        "exact_two_contacts_per_fibre": True,
        "declared_contact_ids_match_geometry": True,
        "anchor_penetrations_match_target": True,
        "force_residual_within_limit": True,
        "moment_residual_within_limit": True,
        "zero_fibre_fibre_overlap": True,
        "anchor_multiplicity_within_limit": True,
        "no_yade_or_flow_authority": not any(placement["authority"][key] for key in (
            "multi_fibre_yade_execution_authorized", "flow_execution_authorized",
            "transient_two_way_coupling_authorized", "deformation_coupled_flow_authorized",
            "production_parametric_study_authorized")),
    }
    recomputed = []
    all_members = []
    anchor_usage = Counter()
    for fibre in fibres:
        members = np.array(fibre["member_centres_m"], dtype=float)
        all_members.append(members)
        checks["all_members_inside_primary_cell"] &= bool(np.all(members - radius >= 0.0) and np.all(members + radius <= lengths))
        delta = members[:, None, :] - sand_centres[None, :, :]
        delta -= np.round(delta / lengths) * lengths
        clearance = np.linalg.norm(delta, axis=2) - radius - sand_radii[None, :]
        minimum_clearance = float(clearance.min())
        contacted = np.flatnonzero(clearance.min(axis=0) <= 1e-10)
        contacted_ids = [int(sand_ids[index]) for index in contacted]
        anchor_ids = [int(value) for value in fibre["anchor_sand_body_ids"]]
        anchor_usage.update(anchor_ids)
        checks["sand_penetration_within_limit"] &= minimum_clearance >= -max_penetration - 1e-12
        checks["exact_two_contacts_per_fibre"] &= len(contacted) == 2
        checks["declared_contact_ids_match_geometry"] &= set(contacted_ids) == set(anchor_ids) == set(fibre["initial_contacted_sand_body_ids"])
        anchor_members = fibre["anchor_member_indices"]
        anchor_indices = fibre["anchor_sand_indices"]
        anchor_clearances = [float(clearance[member_index, sand_index]) for member_index, sand_index in zip(anchor_members, anchor_indices)]
        checks["anchor_penetrations_match_target"] &= max(abs(value + target_penetration) for value in anchor_clearances) <= 1e-10
        com = members.mean(axis=0)
        forces = []
        moments = []
        for member_index, sand_index in zip(anchor_members, anchor_indices):
            vector = periodic_delta(members[member_index], sand_centres[sand_index], lengths)
            force = vector / np.linalg.norm(vector)
            forces.append(force)
            moments.append(np.cross(members[member_index] - com, force))
        force_scale = sum(np.linalg.norm(force) for force in forces)
        force_residual = float(np.linalg.norm(np.sum(forces, axis=0)) / force_scale)
        lever = np.linalg.norm(members[anchor_members[-1]] - members[anchor_members[0]])
        moment_residual = float(np.linalg.norm(np.sum(moments, axis=0)) / (lever * force_scale))
        checks["force_residual_within_limit"] &= force_residual <= cfg["acceptance"]["maximum_force_residual_relative_per_fibre"] + 1e-12
        checks["moment_residual_within_limit"] &= moment_residual <= cfg["acceptance"]["maximum_moment_residual_relative_per_fibre"] + 1e-12
        recomputed.append({
            "fibre_index": fibre["fibre_index"],
            "minimum_sand_clearance_m": minimum_clearance,
            "contacted_sand_body_ids": contacted_ids,
            "force_residual_relative": force_residual,
            "moment_residual_relative": moment_residual,
        })
    pair_clearances = []
    for i in range(len(all_members)):
        for j in range(i + 1, len(all_members)):
            delta = all_members[i][:, None, :] - all_members[j][None, :, :]
            delta -= np.round(delta / lengths) * lengths
            pair_clearances.append(float((np.linalg.norm(delta, axis=2) - 2.0 * radius).min()))
    minimum_fibre_clearance = min(pair_clearances) if pair_clearances else None
    if minimum_fibre_clearance is not None:
        checks["zero_fibre_fibre_overlap"] &= minimum_fibre_clearance >= cfg["acceptance"]["minimum_fibre_fibre_clearance_m"] - 1e-12
    maximum_anchor_multiplicity = max(anchor_usage.values())
    checks["anchor_multiplicity_within_limit"] &= maximum_anchor_multiplicity <= cfg["acceptance"]["maximum_anchor_multiplicity"]
    return {
        "case_id": case["case_id"],
        "passed": all(checks.values()),
        "placement_path": str(path),
        "placement_sha256": digest(path),
        "checks": checks,
        "recomputed_fibres": recomputed,
        "minimum_fibre_fibre_clearance_m": minimum_fibre_clearance,
        "maximum_anchor_multiplicity": maximum_anchor_multiplicity,
    }


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable Tier-1 placement evaluation already exists")
    cfg = load_json(CONFIG)
    if cfg["status"] != "authorized_tier1_placement_preflight_only":
        raise RuntimeError("unexpected configuration status")
    for key, path_text in cfg["sources"].items():
        if key.endswith("_sha256"):
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected and digest(Path(path_text)) != expected:
            raise RuntimeError("source hash mismatch: " + key)
    stage26a = load_json(Path(cfg["sources"]["stage26a_design_config"]))
    result_path = Path(stage26a["source"]["stage25_selected_result"])
    if digest(result_path) != stage26a["source"]["stage25_selected_result_sha256"]:
        raise RuntimeError("Stage25 result hash mismatch")
    result = load_json(result_path)
    sand_centres = np.array([row["position_m"] for row in result["particles"]], dtype=float)
    sand_radii = np.array([row["radius_m"] for row in result["particles"]], dtype=float)
    sand_ids = np.array([int(row["body_id"]) for row in result["particles"]], dtype=int)
    cases = [evaluate_case(case, cfg, sand_centres, sand_radii, sand_ids) for case in cfg["cases"]]
    evaluation = {
        "schema": "lbs.stage26b-tier1-placement-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": all(case["passed"] for case in cases),
        "status": "tier1_geometry_preflight_passed" if all(case["passed"] for case in cases) else "tier1_geometry_preflight_failed",
        "config_path": str(CONFIG),
        "config_sha256": digest(CONFIG),
        "evaluator_sha256": digest(Path(__file__)),
        "cases": cases,
        "authority": cfg["authority"],
        "claim_boundary": cfg["claim_boundary"],
        "next_required_handoff": "Visual audit, then a separately frozen Tier-1 YADE dry-relaxation execution authorization.",
    }
    if not evaluation["passed"]:
        raise RuntimeError("independent Tier-1 placement evaluation failed")
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "case_count": len(cases), "evaluation_sha256": digest(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
