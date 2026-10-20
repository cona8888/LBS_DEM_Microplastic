"""Deterministic synthetic verification for Stage33C-M morphology code.

The suite verifies geometry, topology, censoring, scaling and candidate-only
segmentation logic.  It cannot validate microscopy, PET identification, recovery,
field sampling, or inter-analyst agreement.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_stage33c_blinded_morphology_v1 import (  # noqa: E402
    run_analysis,
    sha256,
    utc_now,
)


N = 192
Q = 8


def ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise RuntimeError(f"fail-closed: verification directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def highres_grid() -> tuple[np.ndarray, np.ndarray]:
    c = (np.arange(N * Q, dtype=np.float32) + 0.5) / Q
    x, y = np.meshgrid(c, c)
    return x, y


def capsule_indicator(
    x: np.ndarray,
    y: np.ndarray,
    p0: tuple[float, float],
    p1: tuple[float, float],
    width: float,
) -> np.ndarray:
    ax, ay = p0
    bx, by = p1
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    t = np.clip(((x - ax) * vx + (y - ay) * vy) / denom, 0.0, 1.0)
    d2 = (x - (ax + t * vx)) ** 2 + (y - (ay + t * vy)) ** 2
    return d2 <= (width / 2.0) ** 2


def straight_indicator(
    x: np.ndarray,
    y: np.ndarray,
    center: tuple[float, float],
    length: float,
    width: float,
    angle_deg: float,
) -> np.ndarray:
    a = math.radians(angle_deg)
    dx, dy = math.cos(a) * length / 2.0, math.sin(a) * length / 2.0
    return capsule_indicator(x, y, (center[0] - dx, center[1] - dy), (center[0] + dx, center[1] + dy), width)


def arc_indicator(
    x: np.ndarray,
    y: np.ndarray,
    center: tuple[float, float],
    radius: float,
    a0: float,
    a1: float,
    width: float,
) -> np.ndarray:
    cx, cy = center
    angle = np.arctan2(y - cy, x - cx)
    radial = np.hypot(x - cx, y - cy)
    inside_angle = (angle >= a0) & (angle <= a1)
    p0 = (cx + radius * math.cos(a0), cy + radius * math.sin(a0))
    p1 = (cx + radius * math.cos(a1), cy + radius * math.sin(a1))
    end_distance = np.minimum(np.hypot(x - p0[0], y - p0[1]), np.hypot(x - p1[0], y - p1[1]))
    distance = np.where(inside_angle, np.abs(radial - radius), end_distance)
    return distance <= width / 2.0


def ellipse_indicator(
    x: np.ndarray,
    y: np.ndarray,
    center: tuple[float, float],
    a: float,
    b: float,
    angle_deg: float,
) -> np.ndarray:
    theta = math.radians(angle_deg)
    xx, yy = x - center[0], y - center[1]
    xr = xx * math.cos(theta) + yy * math.sin(theta)
    yr = -xx * math.sin(theta) + yy * math.cos(theta)
    return (xr / a) ** 2 + (yr / b) ** 2 <= 1.0


def rasterize(indicator: np.ndarray) -> np.ndarray:
    coverage = indicator.reshape(N, Q, N, Q).mean(axis=(1, 3))
    return coverage >= 0.5


def raw_from_mask(mask: np.ndarray, polarity: str, seed: int) -> np.ndarray:
    coverage = ndimage.gaussian_filter(mask.astype(float), sigma=0.8)
    gradient = np.linspace(-4.0, 4.0, mask.shape[1])[None, :]
    rng = np.random.default_rng(seed)
    if polarity == "dark":
        raw = 214.0 - 172.0 * coverage + gradient
    else:
        raw = 40.0 + 172.0 * coverage + gradient
    raw += rng.normal(0.0, 3.0, mask.shape)
    return np.clip(np.rint(raw), 0, 255).astype(np.uint8)


def save_fixture(inputs: Path, image_id: str, mask: np.ndarray, seed: int = 331) -> tuple[Path, Path]:
    mask_path = inputs / f"{image_id}_mask.png"
    raw_path = inputs / f"{image_id}_raw.png"
    Image.fromarray((mask * 255).astype(np.uint8)).save(mask_path)
    Image.fromarray(raw_from_mask(mask, "dark", seed)).save(raw_path)
    return raw_path, mask_path


def generate_fixtures(inputs: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]], dict[str, np.ndarray]]:
    x, y = highres_grid()
    truth: dict[str, dict[str, Any]] = {}
    masks: dict[str, np.ndarray] = {}
    length, width = 100.0, 20.0
    for angle in (0.0, 17.0, 43.0, 89.0):
        case_id = f"straight_{int(angle):03d}"
        masks[case_id] = rasterize(straight_indicator(x, y, (96.0, 96.0), length, width, angle))
        truth[case_id] = {
            "expected_class": "straight_fibre", "lc": length, "w": width,
            "straightness": 1.0, "orientation": angle % 180.0,
            "feret_max": length + width, "feret_min": width,
        }
    masks["straight_043_shift"] = rasterize(straight_indicator(x, y, (109.0, 85.0), length, width, 43.0))
    truth["straight_043_shift"] = dict(truth["straight_043"])

    radius, theta, arc_width = 55.0, math.pi / 2.0, 18.0
    masks["arc_090"] = rasterize(arc_indicator(x, y, (96.0, 108.0), radius, -3 * math.pi / 4, -math.pi / 4, arc_width))
    truth["arc_090"] = {
        "expected_class": "curved_fibre", "lc": radius * theta, "w": arc_width,
        "straightness": 2.0 * math.sin(theta / 2.0) / theta, "orientation": 0.0,
        "curvature": 1.0 / radius,
    }

    ea, eb = 36.0, 24.0
    masks["compact_ellipse"] = rasterize(ellipse_indicator(x, y, (96.0, 96.0), ea, eb, 27.0))
    truth["compact_ellipse"] = {
        "expected_class": "compact_fragment", "feret_max": 2 * ea,
        "feret_min": 2 * eb, "area": math.pi * ea * eb,
    }

    branch = capsule_indicator(x, y, (96.0, 96.0), (96.0, 34.0), 14.0)
    branch |= capsule_indicator(x, y, (96.0, 96.0), (43.0, 137.0), 14.0)
    branch |= capsule_indicator(x, y, (96.0, 96.0), (149.0, 137.0), 14.0)
    masks["branch_y"] = rasterize(branch)
    truth["branch_y"] = {"expected_class": "branched_or_touching", "endpoint_min": 3, "branchpoint_min": 1}

    cross = capsule_indicator(x, y, (44.0, 44.0), (148.0, 148.0), 13.0)
    cross |= capsule_indicator(x, y, (148.0, 44.0), (44.0, 148.0), 13.0)
    masks["cross_x"] = rasterize(cross)
    truth["cross_x"] = {"expected_class": "branched_or_touching", "endpoint_min": 4, "branchpoint_min": 1}

    masks["border_clip"] = rasterize(capsule_indicator(x, y, (-20.0, 96.0), (94.0, 96.0), 14.0))
    truth["border_clip"] = {"expected_class": "border_truncated", "border": True}

    masks["underresolved"] = rasterize(straight_indicator(x, y, (96.0, 96.0), 80.0, 3.0, 12.0))
    truth["underresolved"] = {"expected_class": "straight_fibre", "resolution_fail": True}

    two = straight_indicator(x, y, (62.0, 58.0), 56.0, 12.0, 10.0)
    two |= straight_indicator(x, y, (128.0, 132.0), 64.0, 12.0, 72.0)
    masks["two_objects"] = rasterize(two)
    truth["two_objects"] = {"object_n": 2}

    rows: list[dict[str, str]] = []
    for index, (case_id, mask) in enumerate(masks.items(), start=1):
        raw_path, mask_path = save_fixture(inputs, case_id, mask, 331 + index)
        rows.append(
            {
                "blind_release_id": "STAGE33CM_SYNTH_BLIND_V1", "blind_key_manifest_sha256": "a" * 64,
                "aliquot_id": "BLIND_A01", "image_id": case_id, "mount_id": "M01",
                "field_id": f"F{index:03d}", "field_selection_method": "synthetic_verification",
                "raw_file_path": str(raw_path), "raw_sha256": sha256(raw_path),
                "mask_file_path": str(mask_path), "mask_sha256": sha256(mask_path), "pixel_size_x_um": "1.0",
                "pixel_size_y_um": "1.0", "analysis_run_id": "STAGE33CM_SYNTH_V1",
                "analysis_role": "synthetic_verification", "canonical_run": "true",
                "segmentation_status": "adjudicated", "treatment_blinded": "true",
                "image_qc_status": "pass", "calibration_valid": "true", "calibration_sha256": "b" * 64,
                "pet_confirmed": "true", "psf_fwhm_px": "1.5" if case_id == "underresolved" else "1.0",
                "flow_axis_deg": "0", "candidate_polarity": "dark",
            }
        )

    # Exact unit-scaling challenge using the same raster mask and raw image.
    base = next(r for r in rows if r["image_id"] == "straight_043")
    scaled = dict(base)
    scaled.update({"image_id": "straight_043_scale2", "field_id": "FSCALE", "pixel_size_x_um": "2.0", "pixel_size_y_um": "2.0"})
    rows.append(scaled)
    truth["straight_043_scale2"] = {"scaled_from": "straight_043", "scale": 2.0, "expected_class": "straight_fibre"}
    arc_base = next(r for r in rows if r["image_id"] == "arc_090")
    arc_scaled = dict(arc_base)
    arc_scaled.update({"image_id": "arc_090_scale2", "field_id": "FARCSCALE", "pixel_size_x_um": "2.0", "pixel_size_y_um": "2.0"})
    rows.append(arc_scaled)
    truth["arc_090_scale2"] = {"scaled_from": "arc_090", "scale": 2.0, "expected_class": "curved_fibre"}

    # Candidate-only smoke fixtures; these can never enter publication output.
    candidate_truth = masks["straight_043"]
    for polarity, seed in (("dark", 901), ("light", 902)):
        image_id = f"candidate_{polarity}"
        raw_path = inputs / f"{image_id}_raw.png"
        Image.fromarray(raw_from_mask(candidate_truth, polarity, seed)).save(raw_path)
        rows.append(
            {
                "blind_release_id": "STAGE33CM_SYNTH_BLIND_V1", "blind_key_manifest_sha256": "a" * 64,
                "aliquot_id": "BLIND_A01", "image_id": image_id, "mount_id": "M01",
                "field_id": image_id, "field_selection_method": "synthetic_verification",
                "raw_file_path": str(raw_path), "raw_sha256": sha256(raw_path), "mask_file_path": "", "mask_sha256": "",
                "pixel_size_x_um": "1.0", "pixel_size_y_um": "1.0",
                "analysis_run_id": "STAGE33CM_SYNTH_V1", "analysis_role": "synthetic_verification",
                "canonical_run": "true", "segmentation_status": "candidate_unadjudicated",
                "treatment_blinded": "true", "image_qc_status": "pass", "calibration_valid": "true",
                "calibration_sha256": "b" * 64, "pet_confirmed": "true", "psf_fwhm_px": "1.0",
                "flow_axis_deg": "0", "candidate_polarity": polarity,
            }
        )
        truth[image_id] = {"candidate_truth": "straight_043", "publication_forbidden": True}
    return rows, truth, masks


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    columns = list(rows[0])
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_objects(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value == "":
        raise ValueError(f"missing numeric value {key} for {row.get('image_id')}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite numeric value {key} for {row.get('image_id')}")
    return result


def relative_error(value: float, truth: float) -> float:
    return abs(value - truth) / abs(truth)


def angle_error(value: float, truth: float) -> float:
    return abs(((value - truth + 90.0) % 180.0) - 90.0)


def build_montage(analysis: Path, output: Path) -> None:
    files = sorted((analysis / "overlays").glob("*.png"))
    thumb_w, thumb_h = 260, 235
    cols = 4
    rows = math.ceil(len(files) / cols)
    canvas = Image.new("RGB", (cols * thumb_w, rows * thumb_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for i, path in enumerate(files):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w - 10, thumb_h - 30))
        x = (i % cols) * thumb_w + 5
        y = (i // cols) * thumb_h + 20
        canvas.paste(image, (x, y))
        draw.text((x, 3 + (i // cols) * thumb_h), path.stem.replace("_overlay", ""), fill="black", font=font)
    canvas.save(output)


def verify(output: Path, config: Path | None) -> dict[str, Any]:
    ensure_empty(output)
    inputs = output / "synthetic_inputs"
    inputs.mkdir()
    rows, truth, source_masks = generate_fixtures(inputs)
    manifest_path = output / "synthetic_manifest.csv"
    truth_path = output / "synthetic_truth.json"
    write_manifest(manifest_path, rows)
    json_dump(truth_path, truth)

    analysis = output / "analysis_01"
    repeat = output / "analysis_repeat"
    run_analysis(manifest_path, analysis, config)
    run_analysis(manifest_path, repeat, config)
    objects = read_objects(analysis / "objects.csv")
    by_image: dict[str, list[dict[str, str]]] = {}
    for row in objects:
        by_image.setdefault(row["image_id"], []).append(row)

    checks: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, observed: Any, requirement: str) -> None:
        checks.append({"check_id": check_id, "pass": bool(passed), "observed": observed, "requirement": requirement})

    check("deterministic_objects", sha256(analysis / "objects.csv") == sha256(repeat / "objects.csv"), sha256(analysis / "objects.csv"), "byte-identical objects.csv")
    overlay_names = sorted(p.name for p in (analysis / "overlays").glob("*.png"))
    deterministic_overlays = all(sha256(analysis / "overlays" / n) == sha256(repeat / "overlays" / n) for n in overlay_names)
    check("deterministic_overlays", deterministic_overlays, len(overlay_names), "all corresponding overlay hashes identical")

    length_errors: list[float] = []
    width_errors: list[float] = []
    ar_errors: list[float] = []
    straightness_errors: list[float] = []
    orientation_errors: list[float] = []
    feret_errors: list[float] = []
    for case_id, expected in truth.items():
        if case_id.startswith("candidate_") or case_id.endswith("scale2") or case_id == "two_objects":
            continue
        case_rows = by_image.get(case_id, [])
        check(f"{case_id}_object_count", len(case_rows) == 1, len(case_rows), "exactly one retained component")
        if len(case_rows) != 1:
            continue
        row = case_rows[0]
        check(f"{case_id}_class", row["morphology_class_final"] == expected["expected_class"], row["morphology_class_final"], expected["expected_class"])
        if "endpoint_min" in expected:
            check(f"{case_id}_endpoints", int(row["skeleton_endpoint_n"]) >= expected["endpoint_min"], int(row["skeleton_endpoint_n"]), f">={expected['endpoint_min']}")
            check(f"{case_id}_branchpoints", int(row["skeleton_branchpoint_n"]) >= expected["branchpoint_min"], int(row["skeleton_branchpoint_n"]), f">={expected['branchpoint_min']}")
        if expected.get("border"):
            check(f"{case_id}_border", row["border_touch"] == "True" and row["primary_analysis_included"] == "False", {"border": row["border_touch"], "included": row["primary_analysis_included"]}, "border=True and excluded")
        if expected.get("resolution_fail"):
            check(f"{case_id}_resolution", "width_below_resolution_gate" in row["exclusion_reason"] and row["primary_analysis_included"] == "False", row["exclusion_reason"], "resolution exclusion and not included")
        measured: dict[str, Any] = {"case_id": case_id, "class": row["morphology_class_final"]}
        if "lc" in expected:
            measured["lc"] = as_float(row, "skeleton_contour_um")
            measured["lc_truth"] = expected["lc"]
            measured["lc_rel_error"] = relative_error(measured["lc"], expected["lc"])
            length_errors.append(measured["lc_rel_error"])
        if "w" in expected:
            measured["w"] = as_float(row, "width_median_um")
            measured["w_truth"] = expected["w"]
            measured["w_rel_error"] = relative_error(measured["w"], expected["w"])
            width_errors.append(measured["w_rel_error"])
        if "lc" in expected and "w" in expected:
            ar = as_float(row, "aspect_ratio_centerline")
            ar_truth = expected["lc"] / expected["w"]
            measured["ar"] = ar
            measured["ar_truth"] = ar_truth
            measured["ar_rel_error"] = relative_error(ar, ar_truth)
            ar_errors.append(measured["ar_rel_error"])
        if "straightness" in expected:
            measured["straightness"] = as_float(row, "straightness")
            measured["straightness_truth"] = expected["straightness"]
            measured["straightness_abs_error"] = abs(measured["straightness"] - expected["straightness"])
            straightness_errors.append(measured["straightness_abs_error"])
        if "orientation" in expected:
            measured["orientation"] = as_float(row, "orientation_deg_mod_180")
            measured["orientation_truth"] = expected["orientation"]
            measured["orientation_abs_error"] = angle_error(measured["orientation"], expected["orientation"])
            orientation_errors.append(measured["orientation_abs_error"])
        for key, column in (("feret_max", "max_feret_um"), ("feret_min", "min_feret_um")):
            if key in expected:
                value = as_float(row, column)
                error = relative_error(value, expected[key])
                measured[key] = value
                measured[f"{key}_truth"] = expected[key]
                measured[f"{key}_rel_error"] = error
                feret_errors.append(error)
        if "area" in expected:
            value = as_float(row, "projected_area_um2")
            measured["area"] = value
            measured["area_truth"] = expected["area"]
            measured["area_rel_error"] = relative_error(value, expected["area"])
            check("compact_area", measured["area_rel_error"] <= 0.03, measured["area_rel_error"], "<=0.03")
            check("compact_solidity", as_float(row, "solidity") >= 0.97, as_float(row, "solidity"), ">=0.97")
        if "curvature" in expected:
            value = as_float(row, "median_abs_curvature_per_um")
            measured["curvature"] = value
            measured["curvature_truth"] = expected["curvature"]
            measured["curvature_abs_error"] = abs(value - expected["curvature"])
            check("arc_curvature", measured["curvature_abs_error"] <= max(0.003, 0.2 * expected["curvature"]), measured["curvature_abs_error"], "<=max(0.003,20%)")
        comparisons.append(measured)

    check("two_objects_count", len(by_image.get("two_objects", [])) == 2, len(by_image.get("two_objects", [])), "exactly 2")
    for polarity in ("dark", "light"):
        case_id = f"candidate_{polarity}"
        candidate_path = analysis / "candidate_masks" / f"{case_id}_candidate_mask.png"
        candidate = np.asarray(Image.open(candidate_path).convert("L")) > 0
        target = source_masks["straight_043"]
        dice = 2.0 * np.logical_and(candidate, target).sum() / (candidate.sum() + target.sum())
        included = any(r["primary_analysis_included"] == "True" for r in by_image.get(case_id, []))
        check(f"candidate_{polarity}_dice", dice >= 0.90, dice, ">=0.90 synthetic smoke only")
        check(f"candidate_{polarity}_publication_forbidden", not included, included, "False")

    def quantile(values: list[float], q: float) -> float:
        return float(np.quantile(values, q)) if values else math.inf

    check("length_median_error", quantile(length_errors, 0.5) <= 0.05, quantile(length_errors, 0.5), "<=0.05")
    check("length_p95_error", quantile(length_errors, 0.95) <= 0.10, quantile(length_errors, 0.95), "<=0.10")
    check("width_median_error", quantile(width_errors, 0.5) <= max(1.0 / 14.0, 0.05), quantile(width_errors, 0.5), "absolute <=1 px or relative <=5%")
    check("aspect_ratio_max_error", max(ar_errors, default=math.inf) <= 0.07, max(ar_errors, default=math.inf), "<=0.07")
    check("straightness_max_abs_error", max(straightness_errors, default=math.inf) <= 0.02, max(straightness_errors, default=math.inf), "<=0.02")
    check("orientation_max_abs_error_deg", max(orientation_errors, default=math.inf) <= 3.0, max(orientation_errors, default=math.inf), "<=3 deg")
    feret_gate = all(
        abs(float(row[key]) - float(row[f"{key}_truth"])) <= max(2.0, 0.03 * float(row[f"{key}_truth"]))
        for row in comparisons for key in ("feret_max", "feret_min") if key in row
    )
    check("feret_error", feret_gate, max(feret_errors, default=math.inf), "absolute <=max(2 px,3%) for every Feret value")

    rotation_rows = [by_image[k][0] for k in ("straight_000", "straight_017", "straight_043", "straight_089", "straight_043_shift")]
    for metric in ("skeleton_contour_um", "width_median_um", "aspect_ratio_centerline"):
        values = [as_float(r, metric) for r in rotation_rows]
        spread = (max(values) - min(values)) / float(np.mean(values))
        check(f"rotation_translation_{metric}", spread <= 0.02, spread, "<=0.02")

    original = by_image["straight_043"][0]
    scaled = by_image["straight_043_scale2"][0]
    arc_original = by_image["arc_090"][0]
    arc_scaled = by_image["arc_090_scale2"][0]
    scale_checks = {
        "length": as_float(scaled, "skeleton_contour_um") / as_float(original, "skeleton_contour_um"),
        "width": as_float(scaled, "width_median_um") / as_float(original, "width_median_um"),
        "area": as_float(scaled, "projected_area_um2") / as_float(original, "projected_area_um2"),
        "curvature": as_float(arc_scaled, "median_abs_curvature_per_um") / as_float(arc_original, "median_abs_curvature_per_um"),
        "feret_ar": as_float(scaled, "aspect_ratio_feret") / as_float(original, "aspect_ratio_feret"),
    }
    check("unit_scale_length", abs(scale_checks["length"] - 2.0) <= 1e-10, scale_checks["length"], "2")
    check("unit_scale_width", abs(scale_checks["width"] - 2.0) <= 1e-10, scale_checks["width"], "2")
    check("unit_scale_area", abs(scale_checks["area"] - 4.0) <= 1e-10, scale_checks["area"], "4")
    check("unit_scale_curvature", abs(scale_checks["curvature"] - 0.5) <= 1e-8, scale_checks["curvature"], "0.5")
    check("unit_scale_dimensionless", abs(scale_checks["feret_ar"] - 1.0) <= 1e-10, scale_checks["feret_ar"], "1")

    # Explicit duplicate-ID fail-closed challenge.
    duplicate_manifest = output / "invalid_duplicate_manifest.csv"
    write_manifest(duplicate_manifest, [rows[0], dict(rows[0])])
    duplicate_failed_closed = False
    try:
        run_analysis(duplicate_manifest, output / "invalid_duplicate_output", config)
    except RuntimeError as exc:
        duplicate_failed_closed = "duplicate image_id" in str(exc)
    check("duplicate_id_fail_closed", duplicate_failed_closed, duplicate_failed_closed, "True")

    comparison_columns = sorted({k for row in comparisons for k in row})
    with (output / "metrics_comparison.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=comparison_columns)
        writer.writeheader()
        writer.writerows(comparisons)
    build_montage(analysis, output / "synthetic_overlay_montage.png")
    passed = all(item["pass"] for item in checks)
    result = {
        "stage": "Stage33C-M",
        "verification": "deterministic_synthetic_geometry_v1",
        "created_utc": utc_now(),
        "pass": passed,
        "check_n": len(checks),
        "passed_n": sum(item["pass"] for item in checks),
        "failed_n": sum(not item["pass"] for item in checks),
        "checks": checks,
        "claim_boundary": "software geometry verification only; empirical microscopy and degradation calibration remain closed",
        "publication_validation_missing": [
            "blinded independent PET-batch masks",
            "detection precision/recall and split/merge rates",
            "manual-mask Dice/boundary agreement",
            "inter-analyst repeatability",
            "field sampling, recovery and PET-identity validation",
        ],
        "artifacts": {
            "input_manifest_sha256": sha256(manifest_path),
            "truth_sha256": sha256(truth_path),
            "objects_sha256": sha256(analysis / "objects.csv"),
            "comparison_sha256": sha256(output / "metrics_comparison.csv"),
            "montage_sha256": sha256(output / "synthetic_overlay_montage.png"),
        },
    }
    json_dump(output / "verification.json", result)
    completion = {
        "stage": "Stage33C-M",
        "status": "complete" if passed else "failed",
        "completed_utc": utc_now(),
        "verification_sha256": sha256(output / "verification.json"),
        "no_empirical_data_analyzed": True,
        "no_dem_lbm_job_launched": True,
    }
    json_dump(output / ("completion.json" if passed else "failure.json"), completion)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    result = verify(args.output.resolve(), args.config.resolve() if args.config else None)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
