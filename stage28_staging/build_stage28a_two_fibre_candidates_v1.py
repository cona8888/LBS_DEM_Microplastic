#!/usr/bin/env python3
"""Select deterministic two-fibre placements for the Stage28a preflight."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from stage28a_geometry_math_v1 import (
    candidate_to_fibre,
    synchronous_distance_history,
)


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN = ROOT / "stage28_staging/stage28a_two_fibre_design_v1.json"
DESIGN_AUDIT = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/design_audit_01/design_audit.json"
STAGE26_CONFIG = ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/fixed_sand_design_02/config.json"
PATH_SEARCH = ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/path_search_01/path_candidates.json"
NETWORK = ROOT / "stage26_network_exports/stage26b_revision2_stage25_network_20260816/export_04/network.json"
STAGE26_RESULT = ROOT / "stage26_runs/stage26x_periodic_pore_geometry_20260823/fixed_sand_pilot_02/result.json"
HELPER = ROOT / "stage28_staging/stage28a_geometry_math_v1.py"
TEST = ROOT / "stage28_staging/test_stage28a_geometry_math_v1.py"
OUTPUT = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/candidate_geometry_01"
FIBRE_RADIUS_M = 50.0e-6
MAX_TRANSLATION_M = 0.52e-3
SAMPLES = 209


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def stage26_case_to_fibre(case: dict, fibre_id: str, archetype: str) -> dict:
    return {
        "fibre_id": fibre_id,
        "archetype": archetype,
        "rear_m": [float(value) for value in case["rear_m"]],
        "tip_m": [float(value) for value in case["tip_m"]],
        "pull_direction": [float(value) for value in case["pull_direction"]],
        "source_face_index": int(case["source_face_index"]),
        "source_orientation_sign": float(case["source_orientation_sign"]),
        "source_first_contact_translation_m": case["source_first_contact_translation_m"],
        "source": "stage26x_accepted_case",
    }


def pair_metrics(first: dict, second: dict, lengths, translations) -> dict:
    values = synchronous_distance_history(first, second, lengths, translations)
    minimum_index = int(np.argmin(values))
    contact_indices = np.where(values <= 2.0 * FIBRE_RADIUS_M)[0]
    return {
        "initial_periodic_centreline_distance_m": float(values[0]),
        "minimum_sampled_periodic_centreline_distance_m": float(values[minimum_index]),
        "translation_at_minimum_distance_m": float(translations[minimum_index]),
        "first_predicted_contact_translation_m": (
            float(translations[int(contact_indices[0])]) if contact_indices.size else None
        ),
        "minimum_sampled_surface_clearance_m": float(values[minimum_index] - 2.0 * FIBRE_RADIUS_M),
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable candidate output: {OUTPUT}")
    design = load(DESIGN)
    design_audit = load(DESIGN_AUDIT)
    stage26 = load(STAGE26_CONFIG)
    paths = load(PATH_SEARCH)
    network = load(NETWORK)
    stage26_result = load(STAGE26_RESULT)
    if not (design_audit.get("passed") and design_audit["authority"]["implementation_design"]):
        raise RuntimeError("Stage28a design audit does not authorize candidate construction")
    if not (stage26_result.get("passed") and len(stage26["cases"]) == 2):
        raise RuntimeError("Stage26x accepted pair is unavailable")

    lengths = np.asarray([network["cell_hsize_m"][i][i] for i in range(3)], dtype=float)
    translations = np.linspace(0.0, MAX_TRANSLATION_M, SAMPLES)
    stage26_cases = {case["case_id"]: case for case in stage26["cases"]}
    primary_open = stage26_case_to_fibre(stage26_cases["open"], "fibre_1", "open")
    primary_constricted = stage26_case_to_fibre(
        stage26_cases["constricted"], "fibre_2", "constricted"
    )

    open_candidates = []
    for row in paths["candidates"]:
        if (
            row["first_sampled_contact_translation_m"] is None
            and float(row["throat_to_fibre_radius_ratio"]) >= 1.25
            and float(row["minimum_sampled_swept_clearance_m"]) >= 2.0e-6
            and int(row["face_index"]) != int(primary_open["source_face_index"])
        ):
            fibre = candidate_to_fibre(row, "fibre_2")
            fibre["archetype"] = "open"
            fibre["source"] = "stage26x_path_search"
            open_candidates.append(fibre)
    if len(open_candidates) < 2:
        raise RuntimeError("insufficient independent open-path candidates")

    separated = []
    for candidate in open_candidates:
        metrics = pair_metrics(primary_open, candidate, lengths, translations)
        if metrics["minimum_sampled_periodic_centreline_distance_m"] >= 4.0 * FIBRE_RADIUS_M:
            separated.append((metrics["minimum_sampled_periodic_centreline_distance_m"], candidate, metrics))
    if not separated:
        raise RuntimeError("no separated open-open candidate satisfies the frozen clearance")
    _, secondary_open, separated_open_metrics = max(separated, key=lambda item: item[0])

    mixed_metrics = pair_metrics(primary_open, primary_constricted, lengths, translations)
    if mixed_metrics["minimum_sampled_periodic_centreline_distance_m"] < 4.0 * FIBRE_RADIUS_M:
        raise RuntimeError("accepted Stage26x open and constricted paths are not sufficiently separated")

    crossing_options = []
    candidate_pool = [primary_open] + open_candidates
    for first_index in range(len(candidate_pool)):
        for second_index in range(first_index + 1, len(candidate_pool)):
            first = dict(candidate_pool[first_index])
            second = dict(candidate_pool[second_index])
            first["fibre_id"] = "fibre_1"
            second["fibre_id"] = "fibre_2"
            metrics = pair_metrics(first, second, lengths, translations)
            contact_translation = metrics["first_predicted_contact_translation_m"]
            if (
                metrics["initial_periodic_centreline_distance_m"] >= 2.5 * FIBRE_RADIUS_M
                and contact_translation is not None
                and 0.10e-3 <= contact_translation <= 0.45e-3
                and metrics["minimum_sampled_periodic_centreline_distance_m"] <= 1.5 * FIBRE_RADIUS_M
            ):
                score = (
                    abs(contact_translation - 0.28e-3),
                    metrics["minimum_sampled_periodic_centreline_distance_m"],
                    first["source_face_index"],
                    second["source_face_index"],
                )
                crossing_options.append((score, first, second, metrics))
    if not crossing_options:
        raise RuntimeError("no deterministic crossing pair found within the frozen search domain")
    _, crossing_first, crossing_second, crossing_metrics = min(
        crossing_options, key=lambda item: item[0]
    )

    cases = [
        {
            "case_id": "separated_open_open",
            "role": "noninteracting_independence_control",
            "fibres": [primary_open, secondary_open],
            "analytical_pair_metrics": separated_open_metrics,
        },
        {
            "case_id": "separated_open_constricted",
            "role": "noninteracting_mixed_archetype_additivity",
            "fibres": [primary_open, primary_constricted],
            "analytical_pair_metrics": mixed_metrics,
        },
        {
            "case_id": "crossing_interaction",
            "role": "resolved_fibre_fibre_contact",
            "fibres": [crossing_first, crossing_second],
            "analytical_pair_metrics": crossing_metrics,
        },
    ]
    checks = {
        "exact_three_cases": len(cases) == 3,
        "all_two_fibres": all(len(case["fibres"]) == 2 for case in cases),
        "separated_open_open_clearance": separated_open_metrics[
            "minimum_sampled_periodic_centreline_distance_m"
        ]
        >= 4.0 * FIBRE_RADIUS_M,
        "separated_mixed_clearance": mixed_metrics[
            "minimum_sampled_periodic_centreline_distance_m"
        ]
        >= 4.0 * FIBRE_RADIUS_M,
        "crossing_initially_separate": crossing_metrics[
            "initial_periodic_centreline_distance_m"
        ]
        >= 2.5 * FIBRE_RADIUS_M,
        "crossing_contact_predicted": crossing_metrics[
            "first_predicted_contact_translation_m"
        ]
        is not None,
        "crossing_subdiameter_approach": crossing_metrics[
            "minimum_sampled_periodic_centreline_distance_m"
        ]
        <= 1.5 * FIBRE_RADIUS_M,
        "fixed_216_sand": design["acceptance"]["required_sand_particles"] == 216,
    }
    if not all(checks.values()):
        raise RuntimeError("candidate geometry checks failed")

    payload = {
        "schema": "lbs.stage28a-two-fibre-candidate-geometry.v1",
        "status": "candidate_geometry_built_independent_audit_required",
        "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cell_dimensions_m": lengths.tolist(),
        "fibre_radius_m": FIBRE_RADIUS_M,
        "maximum_synchronous_translation_m": MAX_TRANSLATION_M,
        "translation_sample_count": SAMPLES,
        "cases": cases,
        "checks": checks,
        "mechanics": {
            "fibre": stage26["fibre"],
            "contact": stage26["contact"],
            "loading": stage26["loading"],
            "numerics": stage26["numerics"],
            "outputs": stage26["outputs"],
        },
        "source_bindings": {
            "stage28_design": {"path": str(DESIGN), "sha256": digest(DESIGN)},
            "stage28_design_audit": {
                "path": str(DESIGN_AUDIT),
                "sha256": digest(DESIGN_AUDIT),
            },
            "stage26_config": {"path": str(STAGE26_CONFIG), "sha256": digest(STAGE26_CONFIG)},
            "stage26_result": {"path": str(STAGE26_RESULT), "sha256": digest(STAGE26_RESULT)},
            "path_search": {"path": str(PATH_SEARCH), "sha256": digest(PATH_SEARCH)},
            "network": {"path": str(NETWORK), "sha256": digest(NETWORK)},
            "geometry_helper": {"path": str(HELPER), "sha256": digest(HELPER)},
            "geometry_tests": {"path": str(TEST), "sha256": digest(TEST)},
            "builder": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).resolve())},
        },
        "authority": {
            "independent_candidate_audit": True,
            "mechanics_execution": False,
            "gpu_execution": False,
            "production_concentration_campaign": False,
            "mobile_sand": False,
            "two_way_coupling": False,
        },
        "claim_boundary": design["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    geometry_path = OUTPUT / "candidate_geometry.json"
    geometry_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    completion = {
        "schema": payload["schema"] + ".completion",
        "status": payload["status"],
        "passed": True,
        "checks": checks,
        "candidate_geometry": {"path": str(geometry_path), "sha256": digest(geometry_path)},
        "next_handoff": {
            "authorized": "independent candidate-geometry and implementation audit",
            "not_authorized": "YADE mechanics execution or GPU-LBM execution",
        },
    }
    completion_path = OUTPUT / "completion.json"
    completion_path.write_text(
        json.dumps(completion, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"geometry": str(geometry_path), "geometry_sha256": digest(geometry_path), "checks": checks, "pair_metrics": {case["case_id"]: case["analytical_pair_metrics"] for case in cases}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
