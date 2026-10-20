#!/usr/bin/env python3
"""Enumerate Delaunay throat-normal straight fibre paths in the Stage26o geometry."""

import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.optimize import root
from scipy.spatial import Delaunay

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
GEOMETRY = ROOT / "stage26_runs" / "stage26v_216_flexible_fibre_integration_20260823" / "geometry_export_02" / "geometry.json"
GEOMETRY_COMPLETION = GEOMETRY.parent / "completion.json"
CONTRACT = ROOT / "stage26_staging" / "STAGE26V_216_GRAIN_FLEXIBLE_FIBRE_RESEARCH_CONTRACT.md"
SCRIPT = Path(__file__).resolve()
OUT = ROOT / "stage26_designs" / "stage26v_216_flexible_fibre_integration_20260823" / "path_search_02"
FIBRE_RADIUS = 50e-6
FIBRE_LENGTH = 0.9e-3
TIP_STANDOFF = 0.15e-3
MAX_FORWARD = 0.55e-3
SAMPLE_COUNT = 111


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def segment_surface_clearance(a, b, centres, radii):
    vector = b - a
    length2 = float(np.dot(vector, vector))
    t = np.clip(((centres - a) @ vector) / length2, 0.0, 1.0)
    closest = a + t[:, None] * vector
    return np.linalg.norm(centres - closest, axis=1) - radii - FIBRE_RADIUS


def wall_bounds(walls):
    xs = sorted(w["centre_m"][0] for w in walls if w["extents_m"][0] == 0.0)
    ys = sorted(w["centre_m"][1] for w in walls if w["extents_m"][1] == 0.0)
    zs = sorted(w["centre_m"][2] for w in walls if w["extents_m"][2] == 0.0)
    if not (len(xs) == len(ys) == len(zs) == 2):
        raise RuntimeError("could not resolve six wall planes")
    return np.asarray([xs[0], ys[0], zs[0]]), np.asarray([xs[1], ys[1], zs[1]])


def contained(a, b, lower, upper):
    return bool(np.all(np.minimum(a, b) >= lower + FIBRE_RADIUS) and np.all(np.maximum(a, b) <= upper - FIBRE_RADIUS))


def solve_throat(indices, centres, radii):
    ids = list(indices)
    c = centres[ids]
    r = radii[ids]
    e1 = c[1] - c[0]
    d = np.linalg.norm(e1)
    if d <= 0:
        return None
    e1 /= d
    offset = c[2] - c[0]
    projected = float(np.dot(offset, e1))
    e2raw = offset - projected * e1
    height = np.linalg.norm(e2raw)
    if height <= 1e-12:
        return None
    e2 = e2raw / height
    plane = np.asarray([[0.0, 0.0], [d, 0.0], [projected, height]])

    def residual(value):
        xy = value[:2]
        throat = value[2]
        return [np.linalg.norm(xy - plane[k]) - (r[k] + throat) for k in range(3)]

    centroid = plane.mean(axis=0)
    guess_radius = min(np.linalg.norm(centroid - plane[k]) - r[k] for k in range(3))
    solution = root(residual, [centroid[0], centroid[1], max(guess_radius, 1e-6)])
    if not solution.success or solution.x[2] <= 0:
        return None
    xy = solution.x[:2]
    matrix = np.vstack((plane.T, np.ones(3)))
    bary = np.linalg.solve(matrix, np.asarray([xy[0], xy[1], 1.0]))
    if np.min(bary) < -1e-8 or np.max(bary) > 1.0 + 1e-8:
        return None
    centre = c[0] + xy[0] * e1 + xy[1] * e2
    normal = np.cross(e1, e2)
    normal /= np.linalg.norm(normal)
    return centre, float(solution.x[2]), normal, bary


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite immutable path search {OUT}")
geometry = load(GEOMETRY)
completion = load(GEOMETRY_COMPLETION)
if geometry.get("passed") is not True or completion.get("passed") is not True:
    raise RuntimeError("geometry export is not accepted")
if completion["geometry"]["sha256"] != sha(GEOMETRY):
    raise RuntimeError("geometry completion binding mismatch")
centres = np.asarray([item["centre_m"] for item in geometry["spheres"]], dtype=float)
radii = np.asarray([item["radius_m"] for item in geometry["spheres"]], dtype=float)
body_ids = [int(item["body_id"]) for item in geometry["spheres"]]
lower, upper = wall_bounds(geometry["walls"])
delaunay = Delaunay(centres)
face_counts = Counter(tuple(sorted(face)) for simplex in delaunay.simplices for face in combinations(simplex, 3))
internal_faces = sorted(face for face, count in face_counts.items() if count == 2)
rows = []
for face_index, face in enumerate(internal_faces):
    solved = solve_throat(face, centres, radii)
    if solved is None:
        continue
    throat_centre, throat_radius, normal, bary = solved
    occlusion = float(np.min(np.linalg.norm(centres - throat_centre, axis=1) - radii))
    if occlusion < throat_radius - 1e-8:
        continue
    for sign in (-1.0, 1.0):
        direction = sign * normal
        tip = throat_centre - direction * TIP_STANDOFF
        rear = tip - direction * FIBRE_LENGTH
        if not contained(rear, tip, lower, upper):
            continue
        initial_clearances = segment_surface_clearance(rear, tip, centres, radii)
        initial_clearance = float(np.min(initial_clearances))
        if initial_clearance < 2e-6:
            continue
        translations = np.linspace(0.0, MAX_FORWARD, SAMPLE_COUNT)
        sweep_clearances = []
        distinct_near = set()
        first_contact = None
        for translation in translations:
            values = segment_surface_clearance(rear + direction * translation, tip + direction * translation, centres, radii)
            sweep_clearances.append(float(np.min(values)))
            distinct_near.update(int(index) for index in np.where(values <= 5e-6)[0])
            if first_contact is None and np.min(values) <= 0.0:
                first_contact = float(translation)
        row = {
            "face_index": face_index,
            "face_local_indices": [int(value) for value in face],
            "face_body_ids": [body_ids[index] for index in face],
            "orientation_sign": sign,
            "throat_centre_m": throat_centre.tolist(),
            "pull_direction": direction.tolist(),
            "rear_m": rear.tolist(),
            "tip_m": tip.tolist(),
            "throat_radius_m": throat_radius,
            "throat_to_fibre_radius_ratio": throat_radius / FIBRE_RADIUS,
            "initial_minimum_surface_clearance_m": initial_clearance,
            "minimum_sampled_swept_clearance_m": min(sweep_clearances),
            "first_sampled_contact_translation_m": first_contact,
            "distinct_near_grain_count": len(distinct_near),
            "barycentric": bary.tolist(),
        }
        rows.append(row)

rows.sort(key=lambda item: (item["throat_to_fibre_radius_ratio"], item["face_index"], item["orientation_sign"]))
OUT.mkdir(parents=True)
json_path = OUT / "path_candidates.json"
json_path.write_text(json.dumps({
    "schema": "lbs.stage26v-path-search.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "candidate_count": len(rows),
    "candidates": rows,
    "constants": {"fibre_radius_m": FIBRE_RADIUS, "fibre_length_m": FIBRE_LENGTH,
                  "tip_standoff_m": TIP_STANDOFF, "maximum_forward_translation_m": MAX_FORWARD,
                  "translation_sample_count": SAMPLE_COUNT},
    "source_bindings": {"geometry": {"path": str(GEOMETRY), "sha256": sha(GEOMETRY)},
                        "geometry_completion": {"path": str(GEOMETRY_COMPLETION), "sha256": sha(GEOMETRY_COMPLETION)},
                        "contract": {"path": str(CONTRACT), "sha256": sha(CONTRACT)},
                        "searcher": {"path": str(SCRIPT), "sha256": sha(SCRIPT)}},
    "claim_boundary": "Deterministic analytical path search only; no DEM execution or physical result.",
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
csv_path = OUT / "path_candidates.csv"
fields = ["face_index", "orientation_sign", "throat_to_fibre_radius_ratio", "initial_minimum_surface_clearance_m",
          "minimum_sampled_swept_clearance_m", "first_sampled_contact_translation_m", "distinct_near_grain_count"]
with csv_path.open("x", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for item in rows:
        writer.writerow({key: item[key] for key in fields})
summary = {
    "candidate_count": len(rows),
    "blocked_geometry_candidates": sum(1 for item in rows if item["throat_to_fibre_radius_ratio"] < 1.0 and item["first_sampled_contact_translation_m"] is not None),
    "open_geometry_candidates": sum(1 for item in rows if item["throat_to_fibre_radius_ratio"] >= 1.25 and item["minimum_sampled_swept_clearance_m"] >= 2e-6),
    "candidate_json": {"path": str(json_path), "sha256": sha(json_path)},
    "candidate_csv": {"path": str(csv_path), "sha256": sha(csv_path)},
}
(OUT / "completion.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
