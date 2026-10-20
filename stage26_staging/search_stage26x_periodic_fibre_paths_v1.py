#!/usr/bin/env python3
"""Periodic Delaunay throat/path search on the accepted Stage25 216-grain state."""

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


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
NETWORK = ROOT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_04" / "network.json"
COMPLETION = NETWORK.parent / "completion.json"
STAGE26W = ROOT / "stage26_evaluations" / "stage26w_dense_wall_shrink_regrow_20260823" / "evaluation_01" / "checkpoint_manifest.json"
CONTRACT = ROOT / "stage26_staging" / "STAGE26X_PERIODIC_PORE_GEOMETRY_CONTRACT.md"
SCRIPT = Path(__file__).resolve()
OUT = ROOT / "stage26_designs" / "stage26x_periodic_pore_geometry_20260823" / "path_search_01"
FIBRE_RADIUS = 50.0e-6
FIBRE_LENGTH = 0.9e-3
TIP_STANDOFF = 0.15e-3
MAX_FORWARD = 0.55e-3
SAMPLES = 111


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def solve_throat(indices, centres, radii):
    c = centres[list(indices)]
    r = radii[list(indices)]
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
        xy = value[:2]
        throat = value[2]
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


def segment_clearance(a, b, centres, radii):
    vector = b - a
    length2 = float(np.dot(vector, vector))
    t = np.clip(((centres - a) @ vector) / length2, 0.0, 1.0)
    closest = a + t[:, None] * vector
    return np.linalg.norm(centres - closest, axis=1) - radii - FIBRE_RADIUS


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite immutable Stage26x search: {OUT}")
network = load(NETWORK)
completion = load(COMPLETION)
if network.get("passed") is not True or network.get("periodic") is not True:
    raise RuntimeError("Stage25 network export is not accepted periodic geometry")
if completion.get("passed") is not True or completion.get("network_sha256") != sha(NETWORK):
    raise RuntimeError("network completion binding mismatch")
if not STAGE26W.is_file():
    raise RuntimeError("Stage26w nonacceptance checkpoint is missing")
lengths = np.asarray([network["cell_hsize_m"][k][k] for k in range(3)], dtype=float)
particles = sorted(network["particles"], key=lambda item: int(item["sand_body_id"]))
base_centres = np.asarray([item["position_m"] for item in particles], dtype=float) % lengths
base_radii = np.asarray([item["radius_m"] for item in particles], dtype=float)
body_ids = [int(item["sand_body_id"]) for item in particles]

image_centres = []
image_radii = []
image_body_ids = []
image_shifts = []
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
faces = [face for face, count in counts.items() if count == 2 and len({image_body_ids[index] for index in face}) == 3]
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
        swept = []
        near = set()
        first_contact = None
        for translation in np.linspace(0.0, MAX_FORWARD, SAMPLES):
            values = segment_clearance(rear + direction * translation, tip + direction * translation, image_centres, image_radii)
            swept.append(float(np.min(values)))
            near.update(image_body_ids[index] for index in np.where(values <= 5.0e-6)[0])
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
OUT.mkdir(parents=True, exist_ok=False)
json_path = OUT / "path_candidates.json"
payload = {
    "schema": "lbs.stage26x-periodic-path-search.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "candidate_count": len(rows),
    "cell_dimensions_m": lengths.tolist(),
    "candidates": rows,
    "constants": {"fibre_radius_m": FIBRE_RADIUS, "fibre_length_m": FIBRE_LENGTH, "tip_standoff_m": TIP_STANDOFF, "maximum_forward_translation_m": MAX_FORWARD, "translation_sample_count": SAMPLES},
    "source_bindings": {
        "network": {"path": str(NETWORK), "sha256": sha(NETWORK)},
        "network_completion": {"path": str(COMPLETION), "sha256": sha(COMPLETION)},
        "stage26w_checkpoint": {"path": str(STAGE26W), "sha256": sha(STAGE26W)},
        "contract": {"path": str(CONTRACT), "sha256": sha(CONTRACT)},
        "searcher": {"path": str(SCRIPT), "sha256": sha(SCRIPT)},
    },
    "claim_boundary": "Periodic analytical pore-geometry search only; no DEM execution, fibre mechanics, flow, or permeability result.",
}
json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
csv_path = OUT / "path_candidates.csv"
fields = ["face_index", "orientation_sign", "throat_to_fibre_radius_ratio", "initial_minimum_surface_clearance_m", "minimum_sampled_swept_clearance_m", "first_sampled_contact_translation_m", "distinct_near_grain_count"]
with csv_path.open("x", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for item in rows:
        writer.writerow({key: item[key] for key in fields})
summary = {
    "candidate_count": len(rows),
    "subdiameter_throat_candidates": sum(1 for item in rows if item["throat_to_fibre_radius_ratio"] < 1.0),
    "contacting_sweep_candidates": sum(1 for item in rows if item["first_sampled_contact_translation_m"] is not None),
    "open_control_candidates": sum(1 for item in rows if item["throat_to_fibre_radius_ratio"] >= 1.25 and item["minimum_sampled_swept_clearance_m"] >= 2.0e-6),
    "minimum_throat_to_fibre_radius_ratio": min((item["throat_to_fibre_radius_ratio"] for item in rows), default=None),
    "candidate_json": {"path": str(json_path), "sha256": sha(json_path)},
    "candidate_csv": {"path": str(csv_path), "sha256": sha(csv_path)},
}
(OUT / "completion.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
