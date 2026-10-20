#!/usr/bin/env python3
"""Build two nested 1/2/4-fibre open-path blocks in each of three packings."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUTPUT = ROOT / "stage31_designs/stage31b_nested_concentration_replication_20260826/design_01"
EVALUATION = ROOT / "stage31_evaluations/stage31a_packing_replication_bridge_20260826/mechanics_evaluation_01/evaluation.json"
FIBRE_RADIUS = 50.0e-6
FIBRE_LENGTH = 0.9e-3
FIBRE_DENSITY = 940.0
SAND_DENSITY = 2650.0
MINIMUM_FIBRE_SURFACE_CLEARANCE = 25.0e-6

SOURCES = {
    "n216_s1": {
        "network": ROOT / "stage26_network_exports/stage26b_revision2_stage25_network_20260816/export_04/network.json",
        "paths": ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/path_search_01/path_candidates.json",
    },
    "n216_s2": {
        "network": ROOT / "stage31_network_exports/stage31b_pore_network_exports_20260826/n216_s2/network.json",
        "paths": ROOT / "stage31_designs/stage31b_pore_network_exports_20260826/path_search_n216_s2_01/path_candidates.json",
    },
    "n216_s3": {
        "network": ROOT / "stage31_network_exports/stage31b_pore_network_exports_20260826/n216_s3/network.json",
        "paths": ROOT / "stage31_designs/stage31b_pore_network_exports_20260826/path_search_n216_s3_01/path_candidates.json",
    },
}


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
    s_num, s_den = denominator, denominator
    t_num, t_den = denominator, denominator
    if denominator < 1.0e-30:
        s_num, s_den, t_num, t_den = 0.0, 1.0, e, c
    else:
        s_num, t_num = b * e - c * d, a * e - b * d
        if s_num < 0.0:
            s_num, t_num, t_den = 0.0, e, c
        elif s_num > s_den:
            s_num, t_num, t_den = s_den, e + b, c
    if t_num < 0.0:
        t_num = 0.0
        s_num = min(max(-d, 0.0), a)
        s_den = a
    elif t_num > t_den:
        t_num = t_den
        s_num = min(max(b - d, 0.0), a)
        s_den = a
    s = 0.0 if abs(s_num) < 1.0e-30 else s_num / s_den
    t = 0.0 if abs(t_num) < 1.0e-30 else t_num / t_den
    return float(np.linalg.norm(w + s * u - t * v))


def compatible(first: dict, second: dict) -> bool:
    no_shared_face_grains = set(first["face_body_ids"]).isdisjoint(second["face_body_ids"])
    centreline_clearance = segment_distance(first, second) - 2.0 * FIBRE_RADIUS
    return no_shared_face_grains and centreline_clearance >= MINIMUM_FIBRE_SURFACE_CLEARANCE


def ordered_quartet(candidates: tuple[dict, ...]) -> tuple[list[dict], float]:
    alignments = [abs(float(row["pull_direction"][0])) for row in candidates]
    target = sum(alignments) / 4.0
    best = None
    for order in itertools.permutations(range(4)):
        single = alignments[order[0]]
        pair = 0.5 * (alignments[order[0]] + alignments[order[1]])
        score = abs(single - target) + abs(pair - target)
        if best is None or score < best[0]:
            best = (score, order)
    assert best is not None
    return [candidates[index] for index in best[1]], float(best[0])


def select_blocks(rows: list[dict]) -> list[list[dict]]:
    open_rows = [
        row for row in rows
        if float(row["throat_to_fibre_radius_ratio"]) >= 1.25
        and float(row["minimum_sampled_swept_clearance_m"]) >= 2.0e-6
    ]
    quartets = []
    for indices in itertools.combinations(range(len(open_rows)), 4):
        raw = tuple(open_rows[index] for index in indices)
        if not all(compatible(first, second) for first, second in itertools.combinations(raw, 2)):
            continue
        ordered, nesting_score = ordered_quartet(raw)
        clearances = [segment_distance(a, b) - 2.0 * FIBRE_RADIUS for a, b in itertools.combinations(raw, 2)]
        throat = [float(row["throat_to_fibre_radius_ratio"]) for row in raw]
        score = nesting_score + 0.02 * float(np.std(throat)) - 10.0 * min(clearances)
        quartets.append((score, ordered))
    quartets.sort(key=lambda item: (item[0], [row["face_index"] for row in item[1]]))
    if not quartets:
        raise RuntimeError("no admissible four-fibre open-path block")
    first = quartets[0][1]
    first_faces = {int(row["face_index"]) for row in first}
    first_grains = set().union(*(set(row["face_body_ids"]) for row in first))
    second = None
    for _, candidate in quartets[1:]:
        faces = {int(row["face_index"]) for row in candidate}
        grains = set().union(*(set(row["face_body_ids"]) for row in candidate))
        if faces.isdisjoint(first_faces) and grains.isdisjoint(first_grains):
            second = candidate
            break
    if second is None:
        raise RuntimeError("two independent four-fibre blocks cannot be formed")
    return [first, second]


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable design: {OUTPUT}")
    evaluation = load(EVALUATION)
    if evaluation.get("passed") is not True:
        raise RuntimeError("Stage31a evaluation is not passed")
    cases, blocks, bindings = [], {}, {}
    run_order = []
    order_rank = 0
    for packing_index, (packing, source) in enumerate(SOURCES.items(), start=1):
        network, path_data = load(source["network"]), load(source["paths"])
        if network.get("passed") is not True or int(network["sand_particle_count"]) != 216:
            raise RuntimeError(f"invalid network: {packing}")
        if int(path_data["candidate_count"]) != len(path_data["candidates"]):
            raise RuntimeError(f"candidate count mismatch: {packing}")
        selected = select_blocks(path_data["candidates"])
        particles = network["particles"]
        sand_mass = sum(4.0 * math.pi * float(row["radius_m"]) ** 3 / 3.0 for row in particles) * SAND_DENSITY
        fibre_mass = math.pi * FIBRE_RADIUS ** 2 * FIBRE_LENGTH * FIBRE_DENSITY
        bindings[packing] = {
            "network": {"path": str(source["network"]), "sha256": digest(source["network"])},
            "paths": {"path": str(source["paths"]), "sha256": digest(source["paths"])},
            "sand_mass_kg": sand_mass,
        }
        blocks[packing] = {}
        clean_id = f"s31b_{packing}_clean"
        cases.append({"case_id": clean_id, "packing_id": packing, "placement_block": None, "fibre_count": 0, "achieved_dry_mass_percent": 0.0, "role": "packing_clean_control", "centrelines": []})
        for block_index, (block_name, rows) in enumerate(zip(("A", "B"), selected), start=1):
            block_records = []
            for rank, row in enumerate(rows, start=1):
                block_records.append({
                    "nested_rank": rank,
                    "face_index": int(row["face_index"]),
                    "face_body_ids": row["face_body_ids"],
                    "rear_m": row["rear_m"],
                    "tip_m": row["tip_m"],
                    "pull_direction": row["pull_direction"],
                    "throat_to_fibre_radius_ratio": row["throat_to_fibre_radius_ratio"],
                    "initial_minimum_surface_clearance_m": row["initial_minimum_surface_clearance_m"],
                })
            blocks[packing][block_name] = block_records
            for count in (1, 2, 4):
                case_id = f"s31b_{packing}_{block_name}_f{count:03d}_open"
                concentration = 100.0 * count * fibre_mass / sand_mass
                cases.append({
                    "case_id": case_id,
                    "packing_id": packing,
                    "placement_block": block_name,
                    "fibre_count": count,
                    "achieved_dry_mass_percent": concentration,
                    "role": "nested_zero_interfibre_contact_concentration_branch",
                    "centrelines": block_records[:count],
                })
                order_rank += 1
                run_order.append((hashlib.sha256(f"{packing_index}-{block_index}-{count}-stage31b".encode()).hexdigest(), case_id))

    run_order.sort()
    rank_by_case = {case_id: rank for rank, (_, case_id) in enumerate(run_order, start=1)}
    for case in cases:
        case["frozen_randomized_nonclean_run_order"] = rank_by_case.get(case["case_id"])
    manifest = {
        "schema": "lbs.stage31b-nested-concentration-replication.v1.design",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "geometry_design_complete_execution_not_authorized",
        "research_question": "Does the zero-interfibre-contact low-concentration permeability branch persist across three mechanics-qualified sand packings and two placement blocks per packing?",
        "design": {
            "packing_count": 3,
            "placement_blocks_per_packing": 2,
            "nonzero_concentrations_fibre_counts": [1, 2, 4],
            "hydraulic_case_count_if_later_authorized": len(cases),
            "nested_within_block": True,
            "topology_scope": "zero_interfibre_contact_open_path_branch_only",
        },
        "fibre": {"radius_m": FIBRE_RADIUS, "length_m": FIBRE_LENGTH, "density_kg_m3": FIBRE_DENSITY, "node_count": 37},
        "selection": {
            "minimum_initial_grain_surface_clearance_m": 2.0e-6,
            "minimum_interfibre_surface_clearance_m": MINIMUM_FIBRE_SURFACE_CLEARANCE,
            "minimum_throat_to_fibre_radius_ratio": 1.25,
            "face_grains_disjoint_within_and_between_blocks": True,
            "nested_order_balances_flow_axis_alignment": True,
        },
        "blocks": blocks,
        "cases": cases,
        "source_bindings": {
            "stage31a_evaluation": {"path": str(EVALUATION), "sha256": digest(EVALUATION)},
            **bindings,
            "builder": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).resolve())},
        },
        "authority": {"geometry_audit": True, "fibre_mechanics_execution": False, "flow": False, "permeability_claim": False, "coupling": False},
        "claim_boundary": "Deterministic nested placement design only. No fibre mechanics, flow, permeability inference, concentration law, migration, clogging, deformation, or coupling.",
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "design_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {
        "schema": "lbs.stage31b-nested-concentration-replication.v1.design-completion",
        "passed": len(cases) == 21 and all(len(blocks[p]) == 2 for p in blocks),
        "design_manifest_sha256": digest(path),
        "case_count": len(cases),
        "nonclean_case_count": sum(case["fibre_count"] > 0 for case in cases),
        "authority": manifest["authority"],
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(completion, sort_keys=True))
    if not completion["passed"]:
        raise SystemExit(4)


if __name__ == "__main__":
    main()

