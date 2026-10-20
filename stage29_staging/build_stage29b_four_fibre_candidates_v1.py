#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(r"C:\MATDEM_MICROPLASTIC\stage28_staging")))
from stage28a_geometry_math_v1 import candidate_to_fibre, synchronous_distance_history


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29b_four_fibre_mechanics_qualification_20260825"
DESIGN = ROOT / "stage29_designs" / STUDY / "design_01" / "design_manifest.json"
DESIGN_AUDIT = ROOT / "stage29_evaluations" / STUDY / "design_audit_01" / "design_audit.json"
PATH_SEARCH = ROOT / "stage26_designs" / "stage26x_periodic_pore_geometry_20260823" / "path_search_01" / "path_candidates.json"
NETWORK = ROOT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_04" / "network.json"
HELPER = ROOT / "stage28_staging" / "stage28a_geometry_math_v1.py"
OUT = ROOT / "stage29_designs" / STUDY / "candidate_geometry_01"
RADIUS = 50.0e-6
MAX_TRANSLATION = 0.52e-3
SAMPLES = 209


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def metrics(first: dict, second: dict, lengths: np.ndarray, translations: np.ndarray) -> dict:
    values = synchronous_distance_history(first, second, lengths, translations)
    k = int(np.argmin(values))
    hits = np.where(values <= 2.0 * RADIUS)[0]
    return {
        "initial_periodic_centreline_distance_m": float(values[0]),
        "minimum_sampled_periodic_centreline_distance_m": float(values[k]),
        "minimum_sampled_surface_clearance_m": float(values[k] - 2.0 * RADIUS),
        "translation_at_minimum_distance_m": float(translations[k]),
        "first_predicted_contact_translation_m": float(translations[int(hits[0])]) if hits.size else None,
    }


def midpoint(f: dict) -> np.ndarray:
    return 0.5 * (np.asarray(f["rear_m"], dtype=float) + np.asarray(f["tip_m"], dtype=float))


def orientation_feature(f: dict) -> np.ndarray:
    v = np.asarray(f["tip_m"], dtype=float) - np.asarray(f["rear_m"], dtype=float)
    v /= np.linalg.norm(v)
    return np.sort(np.abs(v))


def case_features(indices: tuple[int, ...], fibres: list[dict], lengths: np.ndarray) -> dict:
    orient = np.mean([orientation_feature(fibres[i]) for i in indices], axis=0)
    mids = np.asarray([midpoint(fibres[i]) for i in indices])
    # Circular mean per periodic axis avoids a false centroid split at a boundary.
    centroid = []
    for axis, length in enumerate(lengths):
        theta = 2.0 * np.pi * mids[:, axis] / length
        angle = np.arctan2(np.sin(theta).mean(), np.cos(theta).mean()) % (2.0 * np.pi)
        centroid.append(float(length * angle / (2.0 * np.pi)))
    return {"mean_sorted_abs_orientation": orient.tolist(), "periodic_centroid_m": centroid}


def centroid_distance(a: list[float], b: list[float], lengths: np.ndarray) -> float:
    delta = np.abs(np.asarray(a) - np.asarray(b))
    delta = np.minimum(delta, lengths - delta)
    return float(np.linalg.norm(delta))


def pair_match_score(low: dict, rich: dict, lengths: np.ndarray) -> tuple[float, float, float]:
    orientation = float(np.linalg.norm(np.asarray(low["features"]["mean_sorted_abs_orientation"]) - np.asarray(rich["features"]["mean_sorted_abs_orientation"])))
    centroid = centroid_distance(low["features"]["periodic_centroid_m"], rich["features"]["periodic_centroid_m"], lengths)
    return orientation + centroid / float(np.mean(lengths)), orientation, centroid


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    design = load(DESIGN)
    audit = load(DESIGN_AUDIT)
    if not (audit.get("passed") and "candidate geometries" in audit["next_handoff"]["authorized"]):
        raise RuntimeError("Stage29b design audit does not authorize candidate geometry construction")
    path_data = load(PATH_SEARCH)
    network = load(NETWORK)
    lengths = np.asarray([network["cell_hsize_m"][i][i] for i in range(3)], dtype=float)
    translations = np.linspace(0.0, MAX_TRANSLATION, SAMPLES)

    rows = [
        row for row in path_data["candidates"]
        if row["first_sampled_contact_translation_m"] is None
        and float(row["throat_to_fibre_radius_ratio"]) >= 1.25
        and float(row["minimum_sampled_swept_clearance_m"]) >= 2.0e-6
    ]
    fibres = []
    for i, row in enumerate(rows):
        f = candidate_to_fibre(row, f"candidate_{i + 1}")
        f["archetype"] = "open"
        f["source"] = "stage26x_path_search"
        fibres.append(f)
    pair = {}
    for i, j in itertools.combinations(range(len(fibres)), 2):
        pair[(i, j)] = metrics(fibres[i], fibres[j], lengths, translations)

    def pm(i: int, j: int) -> dict:
        return pair[tuple(sorted((i, j)))]

    def separated(i: int, j: int) -> bool:
        return pm(i, j)["minimum_sampled_periodic_centreline_distance_m"] >= 4.0 * RADIUS

    def crossing(i: int, j: int) -> bool:
        m = pm(i, j)
        t = m["first_predicted_contact_translation_m"]
        return (
            m["initial_periodic_centreline_distance_m"] >= 2.5 * RADIUS
            and t is not None and 0.10e-3 <= t <= 0.45e-3
            and m["minimum_sampled_periodic_centreline_distance_m"] <= 1.5 * RADIUS
        )

    low_options = []
    for inds in itertools.combinations(range(len(fibres)), 4):
        edges = list(itertools.combinations(inds, 2))
        if all(separated(i, j) for i, j in edges):
            clearance = min(pm(i, j)["minimum_sampled_periodic_centreline_distance_m"] for i, j in edges)
            low_options.append({"indices": inds, "clearance": clearance, "features": case_features(inds, fibres, lengths)})
    crossing_edges = [(i, j) for i, j in itertools.combinations(range(len(fibres)), 2) if crossing(i, j)]
    rich_options = []
    for e1, e2 in itertools.combinations(crossing_edges, 2):
        inds = tuple(sorted(set(e1 + e2)))
        if len(inds) != 4:
            continue
        cross_edges = [(i, j) for i in e1 for j in e2]
        if all(separated(i, j) for i, j in cross_edges):
            rich_options.append({
                "indices": inds,
                "contact_edges_original": [list(e1), list(e2)],
                "cross_clearance": min(pm(i, j)["minimum_sampled_periodic_centreline_distance_m"] for i, j in cross_edges),
                "features": case_features(inds, fibres, lengths),
            })
    if len(low_options) < 3 or len(rich_options) < 3:
        raise RuntimeError(f"insufficient topology candidates: low={len(low_options)} rich={len(rich_options)}")

    candidates = []
    for li, low in enumerate(low_options):
        for ri, rich in enumerate(rich_options):
            score, orientation, centroid = pair_match_score(low, rich, lengths)
            candidates.append((score, orientation, centroid, li, ri))
    candidates.sort()
    selected = []
    used_low_faces: set[int] = set()
    used_rich_faces: set[int] = set()
    for score, orientation, centroid, li, ri in candidates:
        low = low_options[li]
        rich = rich_options[ri]
        low_faces = {int(fibres[i]["source_face_index"]) for i in low["indices"]}
        rich_faces = {int(fibres[i]["source_face_index"]) for i in rich["indices"]}
        if low_faces & used_low_faces or rich_faces & used_rich_faces:
            continue
        selected.append((low, rich, score, orientation, centroid))
        used_low_faces |= low_faces
        used_rich_faces |= rich_faces
        if len(selected) == 3:
            break
    if len(selected) != 3:
        raise RuntimeError("could not form three source-distinct matched blocks")

    out_cases = []
    matching = {}
    for block, (low, rich, score, orientation, centroid) in zip("ABC", selected):
        for topology, option in (("low_contact", low), ("contact_rich", rich)):
            inds = option["indices"]
            local = []
            original_to_local = {}
            for local_id, original in enumerate(inds, start=1):
                f = dict(fibres[original])
                f["fibre_id"] = f"fibre_{local_id}"
                local.append(f)
                original_to_local[original] = local_id
            pair_metrics = {}
            for i, j in itertools.combinations(inds, 2):
                key = f"{original_to_local[i]}-{original_to_local[j]}"
                pair_metrics[key] = pm(i, j)
            intended = []
            if topology == "contact_rich":
                intended = [sorted([original_to_local[i], original_to_local[j]]) for i, j in option["contact_edges_original"]]
                intended.sort()
            out_cases.append({
                "case_id": f"s29b_f004_{topology}_{block}",
                "placement_block": block,
                "topology_regime": topology,
                "fibres": local,
                "intended_predicted_contact_edges": intended,
                "pair_metrics": pair_metrics,
                "features": option["features"],
            })
        matching[block] = {
            "combined_match_score": score,
            "orientation_feature_l2_mismatch": orientation,
            "periodic_centroid_mismatch_m": centroid,
        }

    checks = {
        "source_candidate_count": len(fibres),
        "low_contact_option_count": len(low_options),
        "crossing_edge_count": len(crossing_edges),
        "contact_rich_option_count": len(rich_options),
        "exact_six_cases": len(out_cases) == 6,
        "three_matched_blocks": set(matching) == {"A", "B", "C"},
        "all_four_fibres": all(len(c["fibres"]) == 4 for c in out_cases),
        "low_contact_all_pairs_separated": all(
            all(m["minimum_sampled_periodic_centreline_distance_m"] >= 4.0 * RADIUS for m in c["pair_metrics"].values())
            for c in out_cases if c["topology_regime"] == "low_contact"
        ),
        "contact_rich_exact_two_predicted_edges": all(
            len(c["intended_predicted_contact_edges"]) == 2
            for c in out_cases if c["topology_regime"] == "contact_rich"
        ),
        "matched_orientation_mismatch_max": max(x["orientation_feature_l2_mismatch"] for x in matching.values()),
        "matched_centroid_mismatch_m_max": max(x["periodic_centroid_mismatch_m"] for x in matching.values()),
    }
    passed = (
        checks["exact_six_cases"] and checks["three_matched_blocks"] and checks["all_four_fibres"]
        and checks["low_contact_all_pairs_separated"] and checks["contact_rich_exact_two_predicted_edges"]
    )
    payload = {
        "schema": "lbs.stage29b-four-fibre-candidate-geometry.v1",
        "status": "candidate_geometry_built_independent_audit_required" if passed else "candidate_geometry_failed",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cell_dimensions_m": lengths.tolist(),
        "fibre_radius_m": RADIUS,
        "maximum_synchronous_translation_m": MAX_TRANSLATION,
        "translation_sample_count": SAMPLES,
        "cases": out_cases,
        "paired_matching": matching,
        "checks": checks,
        "source_bindings": {
            "design": {"path": str(DESIGN), "sha256": digest(DESIGN)},
            "design_audit": {"path": str(DESIGN_AUDIT), "sha256": digest(DESIGN_AUDIT)},
            "path_search": {"path": str(PATH_SEARCH), "sha256": digest(PATH_SEARCH)},
            "network": {"path": str(NETWORK), "sha256": digest(NETWORK)},
            "geometry_helper": {"path": str(HELPER), "sha256": digest(HELPER)},
            "builder": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).resolve())},
        },
        "authority": {
            "independent_geometry_audit": True,
            "geometry_acceptance": False,
            "runner_construction": False,
            "yade_execution": False,
            "gpu_flow": False,
        },
        "claim_boundary": design["failure_policy"],
    }
    OUT.mkdir(parents=True)
    p = OUT / "candidate_geometry.json"
    p.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    completion = {
        "schema": payload["schema"] + ".completion",
        "passed": passed,
        "status": payload["status"],
        "candidate_geometry_sha256": digest(p),
        "checks": checks,
        "next_handoff": {
            "authorized": "independent candidate geometry audit" if passed else "diagnosis only",
            "not_authorized": "geometry acceptance, runner construction, YADE execution, or GPU flow",
        },
    }
    (OUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **completion}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
