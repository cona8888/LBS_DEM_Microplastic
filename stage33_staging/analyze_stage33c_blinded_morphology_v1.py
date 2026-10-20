"""Stage33C blinded 2-D PET morphology measurement pipeline.

This release measures masks; it does not infer PET chemistry.  Publication-eligible
measurements require an adjudicated mask, valid scale, treatment blinding, and all
object-level topology/resolution gates.  Automatic thresholding is deliberately
limited to review-candidate masks.

Runtime: Python 3.12 with numpy, scipy and Pillow.  No scikit-image is required.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from scipy.interpolate import splprep, splev


VERSION = "1.0.0"
REQUIRED_COLUMNS = {
    "blind_release_id",
    "blind_key_manifest_sha256",
    "aliquot_id",
    "image_id",
    "mount_id",
    "field_id",
    "field_selection_method",
    "raw_file_path",
    "raw_sha256",
    "mask_sha256",
    "pixel_size_x_um",
    "pixel_size_y_um",
    "analysis_run_id",
    "analysis_role",
    "canonical_run",
    "segmentation_status",
    "treatment_blinded",
    "image_qc_status",
    "calibration_valid",
    "calibration_sha256",
    "pet_confirmed",
}
FORBIDDEN_ANALYST_COLUMNS = {
    "condition_id", "challenge_arm", "target_temperature_c", "temperature_c",
    "source_batch_id", "source_aliquot_id", "randomization_block",
}

OBJECT_COLUMNS = [
    "aliquot_id", "image_id", "analysis_run_id", "object_id",
    "morphology_class_final", "max_feret_um", "min_feret_um",
    "skeleton_contour_um", "end_to_end_chord_um", "width_median_um",
    "width_p10_um", "width_p90_um", "width_cv", "skeleton_endpoint_n",
    "skeleton_branchpoint_n", "border_touch", "counting_frame_status",
    "segmentation_status", "length_censor_type",
    "effective_lower_detection_limit_um", "primary_analysis_included",
    "pet_confirmed", "aspect_ratio_feret", "aspect_ratio_centerline",
    "straightness", "tortuosity", "orientation_deg_mod_180",
    "orientation_to_flow_abs_deg", "total_absolute_turn_rad",
    "median_abs_curvature_per_um", "projected_area_um2", "perimeter_um",
    "solidity", "circularity", "geometry_qc", "broken_end_1",
    "broken_end_2", "exclusion_reason", "mask_sha256", "raw_sha256",
    "bbox_x0_px", "bbox_y0_px", "bbox_x1_px", "bbox_y1_px",
]


DEFAULT_CONFIG: dict[str, Any] = {
    "minimum_object_area_px": 25,
    "minimum_resolved_width_px": 5.0,
    "minimum_psf_multiples": 3.0,
    "fibre_feret_aspect_ratio_min": 3.0,
    "straightness_min": 0.95,
    "candidate_polarity": "dark",
    "candidate_threshold_method": "otsu_global",
    "candidate_open_iterations": 0,
    "candidate_close_iterations": 1,
    "counting_frame_rule": "full_image; border-touch objects censored",
    "publication_segmentation_status": "adjudicated",
    "publication_requires_treatment_blinded": True,
    "allowed_probability_field_selection_methods": ["systematic_random", "simple_random", "stratified_random", "synthetic_verification"],
    "forbidden_blinding_tokens": ["120c", "140c", "160c", "180c", "untreated", "control", "as_received", "as-received", "pxar", "t20"],
    "centreline_method": "Zhang-Suen topology-preserving thinning; ordered simple path; width-scale spline",
    "width_method": "2x Euclidean distance transform sampled on centreline, endpoint half-width excluded",
    "feret_method": "convex hull of physical pixel corners; exact max diameter and minimum caliper",
    "claim_boundary": "2-D projected PET fragmentation phenotype; no chemical-degradation inference",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def bool_value(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def optional_float(value: Any, default: float | None = None) -> float | None:
    if value is None or str(value).strip() == "":
        return default
    return float(value)


def ensure_empty_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise RuntimeError(f"fail-closed: output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def resolve_path(value: str, manifest_path: Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = manifest_path.parent / p
    return p.resolve()


def load_config(path: Path | None) -> tuple[dict[str, Any], str]:
    cfg = dict(DEFAULT_CONFIG)
    if path is not None:
        supplied = json.loads(path.read_text(encoding="utf-8"))
        unknown = sorted(set(supplied) - set(DEFAULT_CONFIG))
        if unknown:
            raise RuntimeError(f"fail-closed: unknown configuration keys: {unknown}")
        cfg.update(supplied)
    payload = (json.dumps(cfg, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return cfg, sha256_bytes(payload)


def otsu_threshold(gray: np.ndarray) -> int:
    values = np.asarray(gray, dtype=np.uint8)
    hist = np.bincount(values.ravel(), minlength=256).astype(float)
    total = hist.sum()
    if total == 0:
        return 127
    p = hist / total
    omega = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    mu_t = mu[-1]
    denom = omega * (1.0 - omega)
    score = np.zeros(256)
    valid = denom > 0
    score[valid] = (mu_t * omega[valid] - mu[valid]) ** 2 / denom[valid]
    return int(np.argmax(score[:-1]))


def candidate_mask(image: Image.Image, cfg: dict[str, Any], polarity: str | None) -> tuple[np.ndarray, int]:
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    threshold = otsu_threshold(gray)
    chosen = (polarity or cfg["candidate_polarity"]).strip().lower()
    if chosen == "dark":
        mask = gray <= threshold
    elif chosen == "light":
        mask = gray >= threshold
    else:
        raise RuntimeError(f"fail-closed: candidate_polarity must be dark or light, got {chosen!r}")
    structure = np.ones((3, 3), dtype=bool)
    for _ in range(int(cfg["candidate_open_iterations"])):
        mask = ndimage.binary_opening(mask, structure=structure)
    for _ in range(int(cfg["candidate_close_iterations"])):
        mask = ndimage.binary_closing(mask, structure=structure)
    return mask.astype(bool), threshold


def zhang_suen(mask: np.ndarray) -> np.ndarray:
    """Return an 8-connected one-pixel skeleton using Zhang-Suen thinning."""
    img = np.pad(mask.astype(np.uint8), 1)
    changed = True
    while changed:
        changed = False
        for phase in (0, 1):
            to_delete: list[tuple[int, int]] = []
            ys, xs = np.nonzero(img)
            for y, x in zip(ys.tolist(), xs.tolist()):
                if y == 0 or x == 0 or y == img.shape[0] - 1 or x == img.shape[1] - 1:
                    continue
                p2, p3, p4 = img[y - 1, x], img[y - 1, x + 1], img[y, x + 1]
                p5, p6, p7 = img[y + 1, x + 1], img[y + 1, x], img[y + 1, x - 1]
                p8, p9 = img[y, x - 1], img[y - 1, x - 1]
                neighbours = [p2, p3, p4, p5, p6, p7, p8, p9]
                n = int(sum(neighbours))
                if n < 2 or n > 6:
                    continue
                transitions = sum(
                    1 for a, b in zip(neighbours, neighbours[1:] + neighbours[:1]) if a == 0 and b == 1
                )
                if transitions != 1:
                    continue
                if phase == 0:
                    gate1 = p2 * p4 * p6 == 0
                    gate2 = p4 * p6 * p8 == 0
                else:
                    gate1 = p2 * p4 * p8 == 0
                    gate2 = p2 * p6 * p8 == 0
                if gate1 and gate2:
                    to_delete.append((y, x))
            if to_delete:
                changed = True
                yy, xx = zip(*to_delete)
                img[np.asarray(yy), np.asarray(xx)] = 0
    return img[1:-1, 1:-1].astype(bool)


def skeleton_graph(skeleton: np.ndarray) -> tuple[list[tuple[int, int]], dict[int, list[tuple[int, float]]]]:
    coords = [tuple(v) for v in np.argwhere(skeleton).tolist()]
    index = {p: i for i, p in enumerate(coords)}
    graph: dict[int, list[tuple[int, float]]] = {i: [] for i in range(len(coords))}
    for i, (y, x) in enumerate(coords):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if not (dy or dx):
                    continue
                q = (y + dy, x + dx)
                j = index.get(q)
                if j is None or j <= i:
                    continue
                # Suppress diagonal corner shortcuts when an orthogonal skeleton
                # path is present; this stabilizes degrees and path ordering.
                if dy and dx and ((y, x + dx) in index or (y + dy, x) in index):
                    continue
                weight = math.sqrt(2.0) if dy and dx else 1.0
                graph[i].append((j, weight))
                graph[j].append((i, weight))
    return coords, graph


def count_node_clusters(coords: list[tuple[int, int]], selected: set[int]) -> int:
    if not selected:
        return 0
    by_coord = {coords[i]: i for i in selected}
    unseen = set(selected)
    clusters = 0
    while unseen:
        clusters += 1
        seed = unseen.pop()
        q = deque([seed])
        while q:
            i = q.popleft()
            y, x = coords[i]
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    j = by_coord.get((y + dy, x + dx))
                    if j is not None and j in unseen:
                        unseen.remove(j)
                        q.append(j)
    return clusters


def ordered_simple_path(
    coords: list[tuple[int, int]], graph: dict[int, list[tuple[int, float]]]
) -> tuple[np.ndarray | None, int, int]:
    degrees = {i: len(v) for i, v in graph.items()}
    endpoints = [i for i, d in degrees.items() if d == 1]
    branch_nodes = {i for i, d in degrees.items() if d > 2}
    branchpoint_n = count_node_clusters(coords, branch_nodes)
    if len(endpoints) != 2 or branchpoint_n != 0:
        return None, len(endpoints), branchpoint_n
    path = [endpoints[0]]
    previous = None
    current = endpoints[0]
    while current != endpoints[1]:
        candidates = [j for j, _ in graph[current] if j != previous]
        if len(candidates) != 1:
            return None, len(endpoints), branchpoint_n
        previous, current = current, candidates[0]
        path.append(current)
        if len(path) > len(coords) + 1:
            return None, len(endpoints), branchpoint_n
    if len(path) != len(coords):
        return None, len(endpoints), branchpoint_n
    return np.asarray([coords[i] for i in path], dtype=float), len(endpoints), branchpoint_n


def convex_hull(points: np.ndarray) -> np.ndarray:
    pts = sorted(set(map(tuple, np.asarray(points, dtype=float).tolist())))
    if len(pts) <= 1:
        return np.asarray(pts, dtype=float)

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.asarray(lower[:-1] + upper[:-1], dtype=float)


def polygon_area(poly: np.ndarray) -> float:
    if len(poly) < 3:
        return 0.0
    return float(abs(np.dot(poly[:, 0], np.roll(poly[:, 1], -1)) - np.dot(poly[:, 1], np.roll(poly[:, 0], -1))) / 2.0)


def mask_hull(mask: np.ndarray, sx: float, sy: float) -> np.ndarray:
    ys, xs = np.nonzero(mask)
    corners = np.concatenate(
        [
            np.column_stack(((xs + dx) * sx, (ys + dy) * sy))
            for dx, dy in ((0, 0), (1, 0), (1, 1), (0, 1))
        ],
        axis=0,
    )
    return convex_hull(corners)


def feret_metrics(hull: np.ndarray) -> tuple[float, float]:
    if len(hull) < 2:
        return 0.0, 0.0
    delta = hull[:, None, :] - hull[None, :, :]
    maximum = float(np.sqrt(np.sum(delta * delta, axis=2)).max())
    minimum = math.inf
    for a, b in zip(hull, np.roll(hull, -1, axis=0)):
        edge = b - a
        norm = float(np.linalg.norm(edge))
        if norm == 0:
            continue
        normal = np.asarray([-edge[1], edge[0]]) / norm
        projection = hull @ normal
        minimum = min(minimum, float(projection.max() - projection.min()))
    return maximum, (0.0 if not math.isfinite(minimum) else minimum)


def mask_perimeter(mask: np.ndarray, sx: float, sy: float) -> float:
    p = np.pad(mask.astype(np.int16), 1)
    horizontal_edges = int(np.abs(np.diff(p, axis=0)).sum())
    vertical_edges = int(np.abs(np.diff(p, axis=1)).sum())
    return float(horizontal_edges * sx + vertical_edges * sy)


@dataclass
class CentrelineMetrics:
    contour_um: float | None
    chord_um: float | None
    width_p10_um: float | None
    width_p50_um: float | None
    width_p90_um: float | None
    width_cv: float | None
    straightness: float | None
    orientation_deg: float | None
    orientation_to_flow_abs_deg: float | None
    total_turn_rad: float | None
    median_abs_curvature: float | None
    endpoint_n: int
    branchpoint_n: int


def centreline_metrics(
    component_mask: np.ndarray,
    sx: float,
    sy: float,
    flow_axis_deg: float,
) -> CentrelineMetrics:
    skeleton = zhang_suen(component_mask)
    coords, graph = skeleton_graph(skeleton)
    path_yx, endpoint_n, branchpoint_n = ordered_simple_path(coords, graph)
    if path_yx is None or len(path_yx) < 2:
        return CentrelineMetrics(*(None,) * 11, endpoint_n, branchpoint_n)

    # Physical coordinates in path order.  A width-scale smoothing spline reduces
    # orientation-dependent chain-code bias but preserves endpoints exactly.
    raw_xy = np.column_stack((path_yx[:, 1] * sx, path_yx[:, 0] * sy))
    distance_px = ndimage.distance_transform_edt(component_mask, sampling=(sy, sx))
    widths = 2.0 * distance_px[path_yx[:, 0].astype(int), path_yx[:, 1].astype(int)]
    positive_widths = widths[np.isfinite(widths) & (widths > 0)]
    median_width = float(np.median(positive_widths)) if len(positive_widths) else 0.0

    # Digital thinning retracts a rounded-cap skeleton slightly.  Extend each
    # endpoint along its local outward tangent to the mask tip, then return by one
    # median radius to estimate the physical cap centre.  This defines Lc as the
    # centreline between cap centres, not the full tip-to-tip Feret size.
    def corrected_endpoint(endpoint: np.ndarray, interior: np.ndarray) -> np.ndarray:
        outward = endpoint - interior
        norm = float(np.linalg.norm(outward))
        if norm == 0 or median_width <= 0:
            return endpoint
        outward /= norm
        step = min(sx, sy) / 10.0
        maximum = max(2.0 * median_width, 4.0 * max(sx, sy))
        last_inside = 0.0
        for distance in np.arange(step, maximum + step, step):
            point = endpoint + outward * distance
            iy = int(round(point[1] / sy))
            ix = int(round(point[0] / sx))
            if not (0 <= iy < component_mask.shape[0] and 0 <= ix < component_mask.shape[1] and component_mask[iy, ix]):
                break
            last_inside = float(distance)
        shift = max(0.0, last_inside - median_width / 2.0)
        return endpoint + outward * shift

    look = min(len(raw_xy) - 1, max(2, int(round(median_width / max(2.0 * min(sx, sy), 1e-12)))))
    raw_xy[0] = corrected_endpoint(raw_xy[0], raw_xy[look])
    raw_xy[-1] = corrected_endpoint(raw_xy[-1], raw_xy[-1 - look])
    raw_steps = np.linalg.norm(np.diff(raw_xy, axis=0), axis=1)
    u = np.concatenate(([0.0], np.cumsum(raw_steps)))
    raw_total = float(u[-1])
    if raw_total <= 0:
        return CentrelineMetrics(*(None,) * 11, endpoint_n, branchpoint_n)
    u /= raw_total

    if len(raw_xy) >= 4:
        smoothing = max(0.0, len(raw_xy) * (0.04 * median_width) ** 2)
        try:
            tck, _ = splprep([raw_xy[:, 0], raw_xy[:, 1]], u=u, s=smoothing, k=min(3, len(raw_xy) - 1))
            dense_u = np.linspace(0.0, 1.0, max(200, len(raw_xy) * 8))
            dense = np.column_stack(splev(dense_u, tck))
            dense[0] = raw_xy[0]
            dense[-1] = raw_xy[-1]
        except Exception:
            dense = raw_xy
    else:
        dense = raw_xy
    dense_steps = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    contour = float(dense_steps.sum())
    chord_vector = dense[-1] - dense[0]
    chord = float(np.linalg.norm(chord_vector))
    straightness = min(1.0, chord / contour) if contour > 0 else None

    # Exclude approximately one local half-width of path at both capped ends.
    path_cumulative = np.concatenate(([0.0], np.cumsum(raw_steps)))
    end_trim = max(median_width / 2.0, 0.0)
    keep = (path_cumulative >= end_trim) & (path_cumulative <= raw_total - end_trim)
    width_sample = widths[keep]
    if len(width_sample) < 3:
        width_sample = positive_widths
    if len(width_sample):
        w10, w50, w90 = [float(v) for v in np.quantile(width_sample, [0.1, 0.5, 0.9])]
        width_cv = float(np.std(width_sample, ddof=1) / np.mean(width_sample)) if len(width_sample) > 1 and np.mean(width_sample) else 0.0
    else:
        w10 = w50 = w90 = width_cv = None

    angle = math.degrees(math.atan2(chord_vector[1], chord_vector[0])) % 180.0
    relative = abs(((angle - flow_axis_deg + 90.0) % 180.0) - 90.0)
    if len(dense) >= 5:
        tangent = np.diff(dense, axis=0)
        theta = np.unwrap(np.arctan2(tangent[:, 1], tangent[:, 0]))
        turn = np.abs(np.diff(theta))
        segment_mid = (dense_steps[:-1] + dense_steps[1:]) / 2.0
        valid = segment_mid > 0
        curvature = np.abs(np.diff(theta)[valid] / segment_mid[valid])
        total_turn = float(turn.sum())
        median_curvature = float(np.median(curvature)) if len(curvature) else 0.0
    else:
        total_turn = 0.0
        median_curvature = 0.0
    return CentrelineMetrics(
        contour, chord, w10, w50, w90, width_cv, straightness,
        angle, relative, total_turn, median_curvature, endpoint_n, branchpoint_n,
    )


def component_rows(
    mask: np.ndarray,
    base: dict[str, str],
    mask_hash: str,
    raw_hash: str,
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    sx = float(base["pixel_size_x_um"])
    sy = float(base["pixel_size_y_um"])
    flow_axis = float(optional_float(base.get("flow_axis_deg"), 0.0) or 0.0)
    psf = optional_float(base.get("psf_fwhm_px"), None)
    rows: list[dict[str, Any]] = []
    object_no = 0
    for label_id in range(1, count + 1):
        component = labels == label_id
        area_px = int(component.sum())
        if area_px < int(cfg["minimum_object_area_px"]):
            continue
        object_no += 1
        ys, xs = np.nonzero(component)
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        border = bool(x0 == 0 or y0 == 0 or x1 == mask.shape[1] - 1 or y1 == mask.shape[0] - 1)
        hull = mask_hull(component, sx, sy)
        max_feret, min_feret = feret_metrics(hull)
        area = area_px * sx * sy
        hull_area = polygon_area(hull)
        perimeter = mask_perimeter(component, sx, sy)
        solidity = min(1.0, area / hull_area) if hull_area > 0 else None
        circularity = min(1.0, 4.0 * math.pi * area / (perimeter * perimeter)) if perimeter > 0 else None
        cl = centreline_metrics(component, sx, sy, flow_axis)
        feret_ar = max_feret / min_feret if min_feret > 0 else None
        centreline_ar = cl.contour_um / cl.width_p50_um if cl.contour_um and cl.width_p50_um else None

        characteristic_width_um = cl.width_p50_um if cl.width_p50_um else min_feret
        resolution_px = characteristic_width_um / math.sqrt(sx * sy) if characteristic_width_um else None
        minimum_width_px = float(cfg["minimum_resolved_width_px"])
        if psf is not None:
            minimum_width_px = max(minimum_width_px, float(cfg["minimum_psf_multiples"]) * psf)
        resolution_ok = resolution_px is not None and resolution_px >= minimum_width_px

        shape_ar = centreline_ar if centreline_ar is not None else feret_ar
        if border:
            morphology = "border_truncated"
        elif cl.branchpoint_n > 0 or cl.endpoint_n not in {0, 2}:
            morphology = "branched_or_touching"
        elif shape_ar is not None and shape_ar < float(cfg["fibre_feret_aspect_ratio_min"]):
            morphology = "compact_fragment"
        elif cl.contour_um is not None:
            morphology = "straight_fibre" if cl.straightness is not None and cl.straightness >= float(cfg["straightness_min"]) else "curved_fibre"
        else:
            morphology = "ambiguous_topology"

        adjudicated = base["segmentation_status"].strip().lower() == str(cfg["publication_segmentation_status"]).lower()
        blinded = bool_value(base["treatment_blinded"])
        image_qc_ok = base["image_qc_status"].strip().lower() == "pass"
        calibration_ok = bool_value(base["calibration_valid"])
        sampling_ok = base["field_selection_method"].strip().lower() in {
            str(v).lower() for v in cfg["allowed_probability_field_selection_methods"]
        }
        topology_ok = morphology in {"straight_fibre", "curved_fibre"} and cl.endpoint_n == 2 and cl.branchpoint_n == 0
        pet_confirmed = bool_value(base.get("pet_confirmed", "false"))
        class_ok = morphology in {"straight_fibre", "curved_fibre", "compact_fragment"}
        publication_ok = adjudicated and blinded and image_qc_ok and calibration_ok and sampling_ok and pet_confirmed and not border and resolution_ok and class_ok
        # Feret metrics are valid for compact objects; centreline metrics require simple fibre topology.
        primary_included = publication_ok
        exclusion: list[str] = []
        if not adjudicated:
            exclusion.append("mask_not_adjudicated")
        if not blinded:
            exclusion.append("treatment_not_blinded")
        if not image_qc_ok:
            exclusion.append("image_qc_not_passed")
        if not calibration_ok:
            exclusion.append("calibration_not_valid")
        if not sampling_ok:
            exclusion.append("field_selection_not_probability_based")
        if not pet_confirmed:
            exclusion.append("pet_identity_not_confirmed")
        if border:
            exclusion.append("border_truncated")
        if not resolution_ok:
            exclusion.append("width_below_resolution_gate")
        if morphology in {"branched_or_touching", "ambiguous_topology"}:
            exclusion.append("ambiguous_object_topology")

        length_censor = "none" if topology_ok and publication_ok else (
            "right_censored_border" if border else "not_applicable_non_simple_fibre"
        )
        row = {
            "aliquot_id": base["aliquot_id"],
            "image_id": base["image_id"],
            "analysis_run_id": base["analysis_run_id"],
            "object_id": f"{base['image_id']}_O{object_no:05d}",
            "morphology_class_final": morphology,
            "max_feret_um": max_feret,
            "min_feret_um": min_feret,
            "skeleton_contour_um": cl.contour_um if topology_ok else None,
            "end_to_end_chord_um": cl.chord_um if topology_ok else None,
            "width_median_um": cl.width_p50_um if topology_ok and resolution_ok else None,
            "width_p10_um": cl.width_p10_um if topology_ok and resolution_ok else None,
            "width_p90_um": cl.width_p90_um if topology_ok and resolution_ok else None,
            "width_cv": cl.width_cv if topology_ok and resolution_ok else None,
            "skeleton_endpoint_n": cl.endpoint_n,
            "skeleton_branchpoint_n": cl.branchpoint_n,
            "border_touch": border,
            "counting_frame_status": "censored_border" if border else "inside",
            "segmentation_status": base["segmentation_status"],
            "length_censor_type": length_censor,
            "effective_lower_detection_limit_um": minimum_width_px * math.sqrt(sx * sy),
            "primary_analysis_included": primary_included,
            "pet_confirmed": pet_confirmed,
            "aspect_ratio_feret": feret_ar,
            "aspect_ratio_centerline": centreline_ar if topology_ok and resolution_ok else None,
            "straightness": cl.straightness if topology_ok else None,
            "tortuosity": (1.0 / cl.straightness) if topology_ok and cl.straightness and cl.straightness > 0 else None,
            "orientation_deg_mod_180": cl.orientation_deg if topology_ok else None,
            "orientation_to_flow_abs_deg": cl.orientation_to_flow_abs_deg if topology_ok else None,
            "total_absolute_turn_rad": cl.total_turn_rad if topology_ok else None,
            "median_abs_curvature_per_um": cl.median_abs_curvature if topology_ok else None,
            "projected_area_um2": area,
            "perimeter_um": perimeter,
            "solidity": solidity,
            "circularity": circularity,
            "geometry_qc": "pass" if publication_ok else "excluded_or_censored",
            "broken_end_1": "not_scored",
            "broken_end_2": "not_scored",
            "exclusion_reason": ";".join(exclusion),
            "mask_sha256": mask_hash,
            "raw_sha256": raw_hash,
            "bbox_x0_px": x0,
            "bbox_y0_px": y0,
            "bbox_x1_px": x1,
            "bbox_y1_px": y1,
        }
        rows.append(row)
    return rows


def overlay_image(image: Image.Image, labels: np.ndarray, rows: list[dict[str, Any]], path: Path) -> None:
    rgb = image.convert("RGB")
    rgba = np.asarray(rgb.convert("RGBA")).copy()
    foreground = labels > 0
    rgba[foreground, 0] = (0.45 * rgba[foreground, 0] + 0.55 * 0).astype(np.uint8)
    rgba[foreground, 1] = (0.45 * rgba[foreground, 1] + 0.55 * 210).astype(np.uint8)
    rgba[foreground, 2] = (0.45 * rgba[foreground, 2] + 0.55 * 255).astype(np.uint8)
    out = Image.fromarray(rgba, mode="RGBA").convert("RGB")
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default()
    for row in rows:
        box = [row["bbox_x0_px"], row["bbox_y0_px"], row["bbox_x1_px"], row["bbox_y1_px"]]
        color = "#00A6D6" if row["primary_analysis_included"] else "#D95F02"
        draw.rectangle(box, outline=color, width=2)
        draw.text((box[0] + 2, box[1] + 2), f"{row['object_id']} {row['morphology_class_final']}", fill=color, font=font)
    out.save(path)


def validate_manifest_rows(rows: list[dict[str, str]], manifest_path: Path, cfg: dict[str, Any]) -> None:
    if not rows:
        raise RuntimeError("fail-closed: input manifest has no rows")
    missing = REQUIRED_COLUMNS - set(rows[0])
    if missing:
        raise RuntimeError(f"fail-closed: manifest missing columns: {sorted(missing)}")
    forbidden_columns = FORBIDDEN_ANALYST_COLUMNS & {name.strip().lower() for name in rows[0]}
    if forbidden_columns:
        raise RuntimeError(f"fail-closed: blinded analyst manifest contains treatment-key columns: {sorted(forbidden_columns)}")
    ids: set[str] = set()
    run_ids: set[str] = set()
    analysis_roles: set[str] = set()
    blind_releases: set[tuple[str, str]] = set()
    hash_pattern = re.compile(r"^[0-9a-fA-F]{64}$")
    allowed_fields = {str(v).lower() for v in cfg["allowed_probability_field_selection_methods"]}
    forbidden_tokens = [str(v).lower() for v in cfg["forbidden_blinding_tokens"]]
    for i, row in enumerate(rows, start=2):
        image_id = row["image_id"].strip()
        if not image_id or image_id in ids:
            raise RuntimeError(f"fail-closed: blank or duplicate image_id at row {i}: {image_id!r}")
        ids.add(image_id)
        run_ids.add(row["analysis_run_id"].strip())
        analysis_roles.add(row["analysis_role"].strip().lower())
        if row["analysis_role"].strip().lower() not in {"locked_primary", "synthetic_verification"}:
            raise RuntimeError(f"fail-closed: analysis_role must be locked_primary or synthetic_verification at row {i}")
        if not bool_value(row["canonical_run"]):
            raise RuntimeError(f"fail-closed: every row must bind the one canonical run at row {i}")
        blind_releases.add((row["blind_release_id"].strip(), row["blind_key_manifest_sha256"].strip().lower()))
        for field in ("blind_release_id", "aliquot_id", "image_id", "mount_id", "field_id", "raw_file_path", "mask_file_path", "original_filename"):
            value = row.get(field, "").lower()
            hit = next((token for token in forbidden_tokens if token and token in value), None)
            if hit:
                raise RuntimeError(f"fail-closed: possible treatment-key leakage token {hit!r} in {field} at row {i}")
        for field in ("blind_key_manifest_sha256", "calibration_sha256", "raw_sha256"):
            if not hash_pattern.fullmatch(row[field].strip()):
                raise RuntimeError(f"fail-closed: invalid SHA-256 in {field} at row {i}")
        sx, sy = float(row["pixel_size_x_um"]), float(row["pixel_size_y_um"])
        if not (sx > 0 and sy > 0):
            raise RuntimeError(f"fail-closed: invalid pixel scale at row {i}")
        raw = resolve_path(row["raw_file_path"], manifest_path)
        if not raw.is_file():
            raise RuntimeError(f"fail-closed: raw image missing at row {i}: {raw}")
        if sha256(raw).lower() != row["raw_sha256"].strip().lower():
            raise RuntimeError(f"fail-closed: raw image hash mismatch at row {i}: {raw}")
        if row["field_selection_method"].strip().lower() not in allowed_fields:
            raise RuntimeError(f"fail-closed: invalid field_selection_method at row {i}")
        status = row["segmentation_status"].strip().lower()
        if status == "adjudicated":
            mask_value = row.get("mask_file_path", "").strip()
            if not mask_value:
                raise RuntimeError(f"fail-closed: adjudicated row lacks mask_file_path at row {i}")
            mask_path = resolve_path(mask_value, manifest_path)
            if not mask_path.is_file():
                raise RuntimeError(f"fail-closed: mask missing at row {i}: {mask_path}")
            if not hash_pattern.fullmatch(row["mask_sha256"].strip()):
                raise RuntimeError(f"fail-closed: invalid mask SHA-256 at row {i}")
            if sha256(mask_path).lower() != row["mask_sha256"].strip().lower():
                raise RuntimeError(f"fail-closed: mask hash mismatch at row {i}: {mask_path}")
        elif status not in {"candidate_unadjudicated", "candidate"}:
            raise RuntimeError(f"fail-closed: unsupported segmentation_status at row {i}: {status!r}")
    if len(run_ids) != 1:
        raise RuntimeError(f"fail-closed: one immutable release must use one analysis_run_id, found {sorted(run_ids)}")
    if len(analysis_roles) != 1:
        raise RuntimeError(f"fail-closed: one immutable release must use one analysis_role, found {sorted(analysis_roles)}")
    if len(blind_releases) != 1 or not next(iter(blind_releases))[0]:
        raise RuntimeError("fail-closed: exactly one nonblank blind release/key-manifest binding is required")


def run_analysis(manifest_path: Path, output_dir: Path, config_path: Path | None) -> dict[str, Any]:
    ensure_empty_output(output_dir)
    cfg, config_hash = load_config(config_path)
    with manifest_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    validate_manifest_rows(rows, manifest_path, cfg)
    overlays = output_dir / "overlays"
    candidate_dir = output_dir / "candidate_masks"
    overlays.mkdir()
    candidate_dir.mkdir()

    object_rows: list[dict[str, Any]] = []
    image_rows: list[dict[str, Any]] = []
    for base in rows:
        raw_path = resolve_path(base["raw_file_path"], manifest_path)
        raw_hash = sha256(raw_path)
        image = Image.open(raw_path)
        metadata_text = json.dumps({"info": image.info, "exif": dict(image.getexif())}, default=str).lower()
        metadata_hit = next((str(token).lower() for token in cfg["forbidden_blinding_tokens"] if str(token).lower() in metadata_text), None)
        if metadata_hit:
            raise RuntimeError(f"fail-closed: possible treatment-key leakage token {metadata_hit!r} in image metadata for {base['image_id']}")
        status = base["segmentation_status"].strip().lower()
        threshold: int | None = None
        if status == "adjudicated":
            mask_path = resolve_path(base["mask_file_path"], manifest_path)
            mask_img = Image.open(mask_path).convert("L")
            if mask_img.size != image.size:
                raise RuntimeError(f"fail-closed: image/mask size mismatch for {base['image_id']}")
            mask = np.asarray(mask_img) > 0
            mask_hash = sha256(mask_path)
        else:
            mask, threshold = candidate_mask(image, cfg, base.get("candidate_polarity"))
            mask_path = candidate_dir / f"{base['image_id']}_candidate_mask.png"
            Image.fromarray((mask * 255).astype(np.uint8)).save(mask_path)
            mask_hash = sha256(mask_path)
            base = dict(base)
            base["segmentation_status"] = "candidate_unadjudicated"

        rows_for_image = component_rows(mask, base, mask_hash, raw_hash, cfg)
        object_rows.extend(rows_for_image)
        labels, _ = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
        overlay_path = overlays / f"{base['image_id']}_overlay.png"
        overlay_image(image, labels, rows_for_image, overlay_path)
        image_rows.append(
            {
                "aliquot_id": base["aliquot_id"],
                "image_id": base["image_id"],
                "mount_id": base["mount_id"],
                "field_id": base["field_id"],
                "field_selection_method": base["field_selection_method"],
                "raw_file_path": str(raw_path),
                "raw_sha256": raw_hash,
                "mask_file_path": str(mask_path),
                "mask_sha256": mask_hash,
                "pixel_size_x_um": float(base["pixel_size_x_um"]),
                "pixel_size_y_um": float(base["pixel_size_y_um"]),
                "analysis_run_id": base["analysis_run_id"],
                "analysis_role": base["analysis_role"],
                "canonical_run": bool_value(base["canonical_run"]),
                "segmentation_status": base["segmentation_status"],
                "treatment_blinded": bool_value(base["treatment_blinded"]),
                "blind_release_id": base["blind_release_id"],
                "blind_key_manifest_sha256": base["blind_key_manifest_sha256"],
                "image_qc_status": base["image_qc_status"],
                "calibration_valid": bool_value(base["calibration_valid"]),
                "calibration_sha256": base["calibration_sha256"],
                "psf_fwhm_px": optional_float(base.get("psf_fwhm_px")),
                "flow_axis_deg": optional_float(base.get("flow_axis_deg"), 0.0),
                "candidate_threshold": threshold,
                "object_n": len(rows_for_image),
                "publication_included_object_n": sum(bool(v["primary_analysis_included"]) for v in rows_for_image),
                "overlay_path": str(overlay_path),
                "overlay_sha256": sha256(overlay_path),
            }
        )

    image_columns = list(image_rows[0]) if image_rows else []
    write_csv(output_dir / "images.csv", image_rows, image_columns)
    write_csv(output_dir / "objects.csv", object_rows, OBJECT_COLUMNS)
    script_path = Path(__file__).resolve()
    manifest = {
        "stage": "Stage33C-M",
        "release": "blinded_2d_pet_morphology_pipeline_v1",
        "status": "software_output_not_empirical_calibration",
        "created_utc": utc_now(),
        "script_path": str(script_path),
        "script_sha256": sha256(script_path),
        "input_manifest_path": str(manifest_path.resolve()),
        "input_manifest_sha256": sha256(manifest_path),
        "configuration": cfg,
        "configuration_sha256": config_hash,
        "image_n": len(image_rows),
        "object_n": len(object_rows),
        "publication_included_object_n": sum(bool(v["primary_analysis_included"]) for v in object_rows),
        "claim_boundary": cfg["claim_boundary"],
        "publication_gate": "closed unless adjudicated-mask, blinding, scale, border and resolution gates pass",
    }
    json_dump(output_dir / "analysis_manifest.json", manifest)
    return manifest


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="measure a blinded image/mask manifest")
    analyze.add_argument("--manifest", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--config", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "analyze":
        result = run_analysis(args.manifest.resolve(), args.output.resolve(), args.config.resolve() if args.config else None)
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
