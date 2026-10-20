#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(r"C:\MATDEM_MICROPLASTIC\stage29_staging")))
from build_stage29b_four_fibre_candidates_v1 import (  # noqa: E402
    MAX_TRANSLATION, NETWORK, PATH_SEARCH, RADIUS, SAMPLES,
    case_features, digest, load, metrics, pair_match_score,
)
sys.path.insert(0, str(Path(r"C:\MATDEM_MICROPLASTIC\stage28_staging")))
from stage28a_geometry_math_v1 import candidate_to_fibre  # noqa: E402


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29c_four_fibre_single_contact_qualification_20260825"
DESIGN = ROOT / "stage29_designs" / STUDY / "design_01" / "design_manifest.json"
AUDIT = ROOT / "stage29_evaluations" / STUDY / "design_audit_01" / "design_audit.json"
STAGE29B_FAILURE = ROOT / "stage29_designs" / "stage29b_four_fibre_mechanics_qualification_20260825" / "candidate_geometry_01" / "failure.json"
HELPER = ROOT / "stage28_staging" / "stage28a_geometry_math_v1.py"
OUT = ROOT / "stage29_designs" / STUDY / "candidate_geometry_01"


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    design = load(DESIGN)
    audit = load(AUDIT)
    if not (audit.get("passed") and "candidate geometries" in audit["next_handoff"]["authorized"]):
        raise RuntimeError("Stage29c audit does not authorize candidate construction")
    path_data = load(PATH_SEARCH)
    network = load(NETWORK)
    lengths = np.asarray([network["cell_hsize_m"][i][i] for i in range(3)], dtype=float)
    translations = np.linspace(0.0, MAX_TRANSLATION, SAMPLES)
    rows = [r for r in path_data["candidates"] if r["first_sampled_contact_translation_m"] is None and float(r["throat_to_fibre_radius_ratio"]) >= 1.25 and float(r["minimum_sampled_swept_clearance_m"]) >= 2.0e-6]
    fibres = []
    for i, row in enumerate(rows):
        f = candidate_to_fibre(row, f"candidate_{i + 1}")
        f.update({"archetype": "open", "source": "stage26x_path_search"})
        fibres.append(f)
    pair = {(i, j): metrics(fibres[i], fibres[j], lengths, translations) for i, j in itertools.combinations(range(len(fibres)), 2)}

    def pm(i: int, j: int) -> dict:
        return pair[tuple(sorted((i, j)))]

    def sep(i: int, j: int) -> bool:
        return pm(i, j)["minimum_sampled_periodic_centreline_distance_m"] >= 4.0 * RADIUS

    def cross(i: int, j: int) -> bool:
        m = pm(i, j)
        t = m["first_predicted_contact_translation_m"]
        return m["initial_periodic_centreline_distance_m"] >= 2.5 * RADIUS and t is not None and 0.10e-3 <= t <= 0.45e-3 and m["minimum_sampled_periodic_centreline_distance_m"] <= 1.5 * RADIUS

    low = []
    for inds in itertools.combinations(range(len(fibres)), 4):
        if all(sep(i, j) for i, j in itertools.combinations(inds, 2)):
            low.append({"indices": inds, "features": case_features(inds, fibres, lengths)})
    one = []
    for edge in [e for e in itertools.combinations(range(len(fibres)), 2) if cross(*e)]:
        remaining = [i for i in range(len(fibres)) if i not in edge]
        for extras in itertools.combinations(remaining, 2):
            inds = tuple(sorted(edge + extras))
            other_edges = [e for e in itertools.combinations(inds, 2) if tuple(sorted(e)) != tuple(sorted(edge))]
            if all(sep(i, j) for i, j in other_edges):
                one.append({"indices": inds, "contact_edge_original": edge, "features": case_features(inds, fibres, lengths)})
    if len(low) < 3 or len(one) < 3:
        raise RuntimeError(f"insufficient revised topology candidates: zero={len(low)} one={len(one)}")

    scored = []
    for li, a in enumerate(low):
        for oi, b in enumerate(one):
            score, orientation, centroid = pair_match_score(a, b, lengths)
            scored.append((score, orientation, centroid, li, oi))
    scored.sort()
    selected = []
    used_low, used_one = set(), set()
    for score, orientation, centroid, li, oi in scored:
        a, b = low[li], one[oi]
        af = {int(fibres[i]["source_face_index"]) for i in a["indices"]}
        bf = {int(fibres[i]["source_face_index"]) for i in b["indices"]}
        if af & used_low or bf & used_one:
            continue
        selected.append((a, b, score, orientation, centroid))
        used_low |= af
        used_one |= bf
        if len(selected) == 3:
            break
    if len(selected) != 3:
        raise RuntimeError("could not select three source-distinct revised blocks")

    cases, matching = [], {}
    for block, (a, b, score, orientation, centroid) in zip("ABC", selected):
        for topology, option in (("zero_contact", a), ("one_contact", b)):
            inds = option["indices"]
            mapping, local = {}, []
            for number, original in enumerate(inds, 1):
                f = dict(fibres[original])
                f["fibre_id"] = f"fibre_{number}"
                mapping[original] = number
                local.append(f)
            expected = []
            if topology == "one_contact":
                i, j = option["contact_edge_original"]
                expected = [sorted([mapping[i], mapping[j]])]
            cases.append({
                "case_id": f"s29c_f004_{topology}_{block}",
                "placement_block": block,
                "topology_regime": topology,
                "fibres": local,
                "intended_predicted_contact_edges": expected,
                "pair_metrics": {f"{mapping[i]}-{mapping[j]}": pm(i, j) for i, j in itertools.combinations(inds, 2)},
                "features": option["features"],
            })
        matching[block] = {"combined_match_score": score, "orientation_feature_l2_mismatch": orientation, "periodic_centroid_mismatch_m": centroid}
    checks = {
        "source_candidate_count": len(fibres),
        "zero_contact_option_count": len(low),
        "one_contact_option_count": len(one),
        "exact_six_cases": len(cases) == 6,
        "three_source_distinct_blocks": len(selected) == 3,
        "predicted_graphs_exact": all(len(c["intended_predicted_contact_edges"]) == (0 if c["topology_regime"] == "zero_contact" else 1) for c in cases),
        "matched_orientation_mismatch_max": max(v["orientation_feature_l2_mismatch"] for v in matching.values()),
        "matched_centroid_mismatch_m_max": max(v["periodic_centroid_mismatch_m"] for v in matching.values()),
    }
    payload = {
        "schema": "lbs.stage29c-four-fibre-single-contact-candidate-geometry.v1",
        "status": "candidate_geometry_built_independent_audit_required",
        "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cell_dimensions_m": lengths.tolist(),
        "fibre_radius_m": RADIUS,
        "maximum_synchronous_translation_m": MAX_TRANSLATION,
        "translation_sample_count": SAMPLES,
        "cases": cases,
        "paired_matching": matching,
        "checks": checks,
        "source_bindings": {
            "design": {"path": str(DESIGN), "sha256": digest(DESIGN)},
            "design_audit": {"path": str(AUDIT), "sha256": digest(AUDIT)},
            "stage29b_failure": {"path": str(STAGE29B_FAILURE), "sha256": digest(STAGE29B_FAILURE)},
            "path_search": {"path": str(PATH_SEARCH), "sha256": digest(PATH_SEARCH)},
            "network": {"path": str(NETWORK), "sha256": digest(NETWORK)},
            "geometry_helper": {"path": str(HELPER), "sha256": digest(HELPER)},
            "builder": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).resolve())},
        },
        "authority": {"independent_geometry_audit": True, "geometry_acceptance": False, "runner_construction": False, "yade_execution": False, "gpu_flow": False},
        "claim_boundary": design["interpretation"],
    }
    OUT.mkdir(parents=True)
    p = OUT / "candidate_geometry.json"
    p.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    completion = {
        "schema": payload["schema"] + ".completion",
        "passed": True,
        "status": payload["status"],
        "candidate_geometry_sha256": digest(p),
        "checks": checks,
        "next_handoff": {"authorized": "independent revised candidate geometry audit", "not_authorized": "geometry acceptance, runner construction, YADE execution, or GPU flow"},
    }
    (OUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **completion}, indent=2))


if __name__ == "__main__":
    main()
