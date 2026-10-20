#!/usr/bin/env python3
"""Enumerate straight F37 candidate paths in one accepted Stage31 packing."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations, product
from pathlib import Path

import numpy as np
from scipy.optimize import root
from scipy.spatial import Delaunay

FIBRE_RADIUS = 50.0e-6
FIBRE_LENGTH = 0.9e-3
TIP_STANDOFF = 0.15e-3
MAX_FORWARD = 0.55e-3
SAMPLES = 111


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def solve_throat(indices: tuple[int, int, int], centres: np.ndarray, radii: np.ndarray):
    c, r = centres[list(indices)], radii[list(indices)]
    e1 = c[1] - c[0]
    distance = np.linalg.norm(e1)
    if distance <= 0.0:
        return None
    e1 /= distance
    offset = c[2] - c[0]
    projected = float(np.dot(offset, e1))
    e2_raw = offset - projected * e1
    height = np.linalg.norm(e2_raw)
    if height <= 1.0e-12:
        return None
    e2 = e2_raw / height
    plane = np.asarray([[0.0, 0.0], [distance, 0.0], [projected, height]])

    def residual(value):
        xy, throat = value[:2], value[2]
        return [np.linalg.norm(xy - plane[k]) - (r[k] + throat) for k in range(3)]

    centroid = plane.mean(axis=0)
    guess = min(np.linalg.norm(centroid - plane[k]) - r[k] for k in range(3))
    solution = root(residual, [centroid[0], centroid[1], max(guess, 1.0e-6)])
    if not solution.success or solution.x[2] <= 0.0:
        return None
    xy = solution.x[:2]
    bary = np.linalg.solve(np.vstack((plane.T, np.ones(3))), np.asarray([xy[0], xy[1], 1.0]))
    if np.min(bary) < -1.0e-8 or np.max(bary) > 1.0 + 1.0e-8:
        return None
    centre = c[0] + xy[0] * e1 + xy[1] * e2
    normal = np.cross(e1, e2)
    normal /= np.linalg.norm(normal)
    return centre, float(solution.x[2]), normal, bary


def segment_clearance(a: np.ndarray, b: np.ndarray, centres: np.ndarray, radii: np.ndarray) -> np.ndarray:
    vector = b - a
    length2 = float(np.dot(vector, vector))
    t = np.clip(((centres - a) @ vector) / length2, 0.0, 1.0)
    closest = a + t[:, None] * vector
    return np.linalg.norm(centres - closest, axis=1) - radii - FIBRE_RADIUS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--packing-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    network_path = args.network.resolve()
    completion_path = network_path.parent / "completion.json"
    evaluation_path = args.evaluation.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable path search: {output}")
    network, completion, evaluation = load(network_path), load(completion_path), load(evaluation_path)
    if network.get("passed") is not True or network.get("periodic") is not True:
        raise RuntimeError("network is not an accepted periodic export")
    if completion.get("passed") is not True or completion.get("network_sha256") != digest(network_path):
        raise RuntimeError("network completion binding mismatch")
    if evaluation.get("passed") is not True or args.packing_id not in {case["packing_id"] for case in evaluation["cases"]}:
        raise RuntimeError("Stage31 evaluation does not authorize this packing")

    lengths = np.asarray([network["cell_hsize_m"][k][k] for k in range(3)], dtype=float)
    particles = sorted(network["particles"], key=lambda item: int(item["sand_body_id"]))
    base_centres = np.asarray([item["position_m"] for item in particles], dtype=float) % lengths
    base_radii = np.asarray([item["radius_m"] for item in particles], dtype=float)
    body_ids = [int(item["sand_body_id"]) for item in particles]
    image_centres, image_radii, image_body_ids, image_shifts = [], [], [], []
    for shift in product((-1, 0, 1), repeat=3):
        vector = np.asarray(shift, dtype=float) * lengths
        for index in range(len(base_centres)):
            image_centres.append(base_centres[index] + vector)
            image_radii.append(base_radii[index])
            image_body_ids.append(body_ids[index])
            image_shifts.append(list(shift))
    image_centres = np.asarray(image_centres, dtype=float)
    image_radii = np.asarray(image_radii, dtype=float)
    delaunay = Delaunay(image_centres)
    counts = Counter(tuple(sorted(face)) for simplex in delaunay.simplices for face in combinations(simplex, 3))
    faces = [face for face, count in counts.items() if count == 2 and len({image_body_ids[i] for i in face}) == 3]
    rows = []
    for face_index, face in enumerate(sorted(faces)):
        solved = solve_throat(face, image_centres, image_radii)
        if solved is None:
            continue
        throat_centre, throat_radius, normal, bary = solved
        if not bool(np.all(throat_centre >= 0.0) and np.all(throat_centre < lengths)):
            continue
        occlusion = float(np.min(np.linalg.norm(image_centres - throat_centre, axis=1) - image_radii))
        if occlusion < throat_radius - 1.0e-8:
            continue
        for sign in (-1.0, 1.0):
            direction = sign * normal
            tip = throat_centre - direction * TIP_STANDOFF
            rear = tip - direction * FIBRE_LENGTH
            if not bool(np.all(np.minimum(rear, tip) >= FIBRE_RADIUS) and np.all(np.maximum(rear, tip) <= lengths - FIBRE_RADIUS)):
                continue
            initial = segment_clearance(rear, tip, image_centres, image_radii)
            minimum_initial = float(np.min(initial))
            if minimum_initial < 2.0e-6:
                continue
            swept, near, first_contact = [], set(), None
            for translation in np.linspace(0.0, MAX_FORWARD, SAMPLES):
                values = segment_clearance(rear + direction * translation, tip + direction * translation, image_centres, image_radii)
                swept.append(float(np.min(values)))
                near.update(image_body_ids[i] for i in np.where(values <= 5.0e-6)[0])
                if first_contact is None and np.min(values) <= 0.0:
                    first_contact = float(translation)
            rows.append({
                "face_index": face_index,
                "face_image_indices": [int(value) for value in face],
                "face_body_ids": [image_body_ids[index] for index in face],
                "face_image_shifts": [image_shifts[index] for index in face],
                "orientation_sign": sign,
                "throat_centre_m": throat_centre.tolist(),
                "pull_direction": direction.tolist(),
                "rear_m": rear.tolist(),
                "tip_m": tip.tolist(),
                "throat_radius_m": throat_radius,
                "throat_to_fibre_radius_ratio": throat_radius / FIBRE_RADIUS,
                "initial_minimum_surface_clearance_m": minimum_initial,
                "minimum_sampled_swept_clearance_m": min(swept),
                "first_sampled_contact_translation_m": first_contact,
                "distinct_near_grain_count": len(near),
                "barycentric": bary.tolist(),
            })
    rows.sort(key=lambda item: (item["throat_to_fibre_radius_ratio"], item["face_index"], item["orientation_sign"]))
    output.mkdir(parents=True)
    candidates_path = output / "path_candidates.json"
    payload = {
        "schema": "lbs.stage31b-periodic-path-search.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "packing_id": args.packing_id,
        "candidate_count": len(rows),
        "cell_dimensions_m": lengths.tolist(),
        "candidates": rows,
        "constants": {
            "fibre_radius_m": FIBRE_RADIUS,
            "fibre_length_m": FIBRE_LENGTH,
            "tip_standoff_m": TIP_STANDOFF,
            "maximum_forward_translation_m": MAX_FORWARD,
            "translation_sample_count": SAMPLES,
        },
        "source_bindings": {
            "network": {"path": str(network_path), "sha256": digest(network_path)},
            "network_completion": {"path": str(completion_path), "sha256": digest(completion_path)},
            "stage31_evaluation": {"path": str(evaluation_path), "sha256": digest(evaluation_path)},
            "searcher": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).resolve())},
        },
        "claim_boundary": "Analytical periodic pore-path search only; no fibre mechanics, flow, or permeability result.",
    }
    candidates_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = output / "path_candidates.csv"
    fields = ["face_index", "orientation_sign", "throat_to_fibre_radius_ratio", "initial_minimum_surface_clearance_m", "minimum_sampled_swept_clearance_m", "first_sampled_contact_translation_m", "distinct_near_grain_count"]
    with csv_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row[key] for key in fields} for row in rows)
    summary = {
        "schema": "lbs.stage31b-periodic-path-search.v1.completion",
        "packing_id": args.packing_id,
        "passed": len(rows) > 0,
        "candidate_count": len(rows),
        "contacting_sweep_candidates": sum(row["first_sampled_contact_translation_m"] is not None for row in rows),
        "open_control_candidates": sum(row["throat_to_fibre_radius_ratio"] >= 1.25 and row["minimum_sampled_swept_clearance_m"] >= 2.0e-6 for row in rows),
        "minimum_throat_to_fibre_radius_ratio": min((row["throat_to_fibre_radius_ratio"] for row in rows), default=None),
        "artifacts": {"candidates_sha256": digest(candidates_path), "csv_sha256": digest(csv_path)},
        "authority": {"fibre_mechanics": False, "flow": False},
    }
    (output / "completion.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(4)


if __name__ == "__main__":
    main()

