"""Freeze and compare two independent Stage33C-Q labelled-mask submissions.

This is a pre-consensus repeatability assessment.  It does not create consensus
masks and does not qualify treatment effects or chemical degradation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_stage33c_blinded_morphology_v1 import (  # noqa: E402
    centreline_metrics,
    feret_metrics,
    mask_hull,
)


SUBMISSION_COLUMNS = {
    "blind_release_id", "reviewer_id", "review_pass", "image_id",
    "instance_mask_path", "instance_mask_sha256", "annotation_path",
    "annotation_sha256", "submission_utc",
}
ANNOTATION_COLUMNS = {
    "image_id", "reviewer_object_id", "mask_label", "morphology_class",
    "border_touch", "counting_frame_status", "censor_type", "topology_status",
    "segmentation_disposition", "ambiguity_flag", "confidence_code", "exclusion_reason",
}
ALLOWED_CLASSES = {
    "straight_fibre", "curved_fibre", "branched_or_peeled_fibre", "ribbon",
    "compact_irregular_fragment", "aggregate_or_bundle",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bool_value(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise RuntimeError(f"fail-closed: qualification output is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def resolve_path(value: str, table: Path) -> Path:
    path = Path(value)
    return (table.parent / path).resolve() if not path.is_absolute() else path.resolve()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def validate_reviewer_roles(path: Path, reviewer_ids: list[str]) -> str:
    roles = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "key_custodian_ids", "acquisition_operator_ids", "release_officer_ids",
        "morphology_analyst_ids", "freeze_auditor_ids", "reveal_authority_ids",
    }
    if set(roles) != required:
        raise RuntimeError("fail-closed: reviewer roles file has an invalid schema")
    role_sets = {name: {str(v).strip() for v in roles[name]} for name in required}
    if any(not values or "" in values for values in role_sets.values()):
        raise RuntimeError("fail-closed: reviewer roles contain a blank or empty assignment")
    privileged = (
        role_sets["key_custodian_ids"]
        | role_sets["acquisition_operator_ids"]
        | role_sets["release_officer_ids"]
    )
    blinded = role_sets["morphology_analyst_ids"] | role_sets["freeze_auditor_ids"]
    if privileged & blinded:
        raise RuntimeError("fail-closed: custody/acquisition/release role overlaps blinded analysis")
    if not set(reviewer_ids).issubset(role_sets["morphology_analyst_ids"]):
        raise RuntimeError("fail-closed: both mask reviewers must be authorized morphology analysts")
    return sha256(path)


def load_label_mask(path: Path, expected_size: tuple[int, int]) -> np.ndarray:
    image = Image.open(path)
    array = np.asarray(image)
    if array.ndim != 2 or array.dtype.kind not in {"u", "i"}:
        raise RuntimeError(f"fail-closed: instance mask must be a 2-D integer image: {path}")
    if array.shape != (expected_size[1], expected_size[0]) or np.any(array < 0):
        raise RuntimeError(f"fail-closed: instance mask dimensions/value domain invalid: {path}")
    return array.astype(np.int64, copy=False)


def load_annotations(path: Path, image_id: str, labels: set[int]) -> dict[int, dict[str, str]]:
    rows = read_csv(path)
    if not rows or ANNOTATION_COLUMNS - set(rows[0]):
        raise RuntimeError(f"fail-closed: annotation file missing columns: {path}")
    result: dict[int, dict[str, str]] = {}
    for row_no, row in enumerate(rows, start=2):
        if row["image_id"] != image_id:
            raise RuntimeError(f"fail-closed: annotation image mismatch at {path}:{row_no}")
        label = int(row["mask_label"])
        if label <= 0 or label in result:
            raise RuntimeError(f"fail-closed: duplicate/invalid mask label at {path}:{row_no}")
        if row["morphology_class"] not in ALLOWED_CLASSES:
            raise RuntimeError(f"fail-closed: invalid morphology class at {path}:{row_no}")
        result[label] = row
    if set(result) != labels:
        raise RuntimeError(f"fail-closed: mask labels and annotations differ for {image_id}: mask={sorted(labels)}, annotation={sorted(result)}")
    return result


def boundary(mask: np.ndarray) -> np.ndarray:
    return mask & ~ndimage.binary_erosion(mask, structure=np.ones((3, 3), dtype=bool), border_value=0)


def boundary_metrics(a: np.ndarray, b: np.ndarray, tolerance_px: float = 2.0) -> tuple[float, float]:
    ba, bb = boundary(a), boundary(b)
    if not ba.any() or not bb.any():
        return (1.0 if np.array_equal(ba, bb) else 0.0), math.inf
    db = ndimage.distance_transform_edt(~bb)
    da = ndimage.distance_transform_edt(~ba)
    precision = float(np.mean(db[ba] <= tolerance_px))
    recall = float(np.mean(da[bb] <= tolerance_px))
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    distances = np.concatenate((db[ba], da[bb]))
    return f1, float(np.quantile(distances, 0.95))


def cohen_kappa(values_a: list[str], values_b: list[str]) -> float | None:
    if not values_a or len(values_a) != len(values_b):
        return None
    categories = sorted(set(values_a) | set(values_b))
    n = len(values_a)
    observed = sum(a == b for a, b in zip(values_a, values_b)) / n
    expected = sum(values_a.count(c) * values_b.count(c) for c in categories) / (n * n)
    return (observed - expected) / (1.0 - expected) if expected < 1.0 else (1.0 if observed == 1.0 else None)


def gwet_ac1(values_a: list[str], values_b: list[str]) -> float | None:
    if not values_a or len(values_a) != len(values_b):
        return None
    categories = sorted(set(values_a) | set(values_b))
    q = len(categories)
    observed = sum(a == b for a, b in zip(values_a, values_b)) / len(values_a)
    if q <= 1:
        return 1.0
    pooled = {c: (values_a.count(c) + values_b.count(c)) / (2.0 * len(values_a)) for c in categories}
    expected = sum(p * (1.0 - p) for p in pooled.values()) / (q - 1)
    return (observed - expected) / (1.0 - expected) if expected < 1.0 else None


def icc_absolute_single(a: list[float], b: list[float]) -> float | None:
    if len(a) != len(b) or len(a) < 2:
        return None
    values = np.column_stack((np.asarray(a, float), np.asarray(b, float)))
    n, k = values.shape
    grand = float(values.mean())
    row_mean = values.mean(axis=1)
    column_mean = values.mean(axis=0)
    msr = k * float(np.sum((row_mean - grand) ** 2)) / (n - 1)
    msc = n * float(np.sum((column_mean - grand) ** 2)) / (k - 1)
    residual = values - row_mean[:, None] - column_mean[None, :] + grand
    mse = float(np.sum(residual ** 2)) / ((n - 1) * (k - 1))
    denominator = msr + (k - 1) * mse + k * (msc - mse) / n
    return (msr - mse) / denominator if denominator != 0 else None


def object_geometry(mask: np.ndarray, sx: float, sy: float) -> dict[str, float | None]:
    hull = mask_hull(mask, sx, sy)
    feret_max, feret_min = feret_metrics(hull)
    cl = centreline_metrics(mask, sx, sy, 0.0)
    centreline_ar = cl.contour_um / cl.width_p50_um if cl.contour_um and cl.width_p50_um else None
    return {
        "feret_max": feret_max,
        "feret_min": feret_min,
        "contour": cl.contour_um,
        "width": cl.width_p50_um,
        "centreline_ar": centreline_ar,
        "straightness": cl.straightness,
        "orientation": cl.orientation_deg,
    }


def relation_components(iou: np.ndarray, containment: np.ndarray) -> list[tuple[list[int], list[int]]]:
    na, nb = iou.shape
    adjacency_a = {i: set(np.where((iou[i] >= 0.10) | (containment[i] >= 0.25))[0].tolist()) for i in range(na)}
    adjacency_b = {j: {i for i in range(na) if j in adjacency_a[i]} for j in range(nb)}
    unseen_a, unseen_b = set(range(na)), set(range(nb))
    components: list[tuple[list[int], list[int]]] = []
    while unseen_a or unseen_b:
        side = "a" if unseen_a else "b"
        seed = unseen_a.pop() if unseen_a else unseen_b.pop()
        qa, qb = ([seed], []) if side == "a" else ([], [seed])
        comp_a, comp_b = set(qa), set(qb)
        while qa or qb:
            while qa:
                i = qa.pop()
                for j in adjacency_a[i]:
                    if j not in comp_b:
                        comp_b.add(j)
                        unseen_b.discard(j)
                        qb.append(j)
            while qb:
                j = qb.pop()
                for i in adjacency_b[j]:
                    if i not in comp_a:
                        comp_a.add(i)
                        unseen_a.discard(i)
                        qa.append(i)
        components.append((sorted(comp_a), sorted(comp_b)))
    return components


def qualify(
    blinded_manifest_path: Path,
    submission_a_path: Path,
    submission_b_path: Path,
    roles_path: Path,
    output: Path,
) -> dict[str, Any]:
    ensure_empty(output)
    image_rows = read_csv(blinded_manifest_path)
    if not image_rows:
        raise RuntimeError("fail-closed: blinded image manifest is empty")
    required_manifest_columns = {
        "blind_release_id", "image_id", "raw_file_path", "raw_sha256",
        "pixel_size_x_um", "pixel_size_y_um",
    }
    missing_manifest_columns = required_manifest_columns - set(image_rows[0])
    if missing_manifest_columns:
        raise RuntimeError(
            f"fail-closed: blinded manifest missing columns: {sorted(missing_manifest_columns)}"
        )
    by_image = {row["image_id"]: row for row in image_rows}
    if len(by_image) != len(image_rows):
        raise RuntimeError("fail-closed: duplicate image IDs in blinded manifest")
    release_ids = {row.get("blind_release_id", "").strip() for row in image_rows}
    if len(release_ids) != 1 or not next(iter(release_ids)):
        raise RuntimeError("fail-closed: blinded manifest must bind exactly one nonempty release ID")
    blind_release_id = next(iter(release_ids))
    submissions = [read_csv(submission_a_path), read_csv(submission_b_path)]
    submission_paths = [submission_a_path, submission_b_path]
    reviewer_ids: list[str] = []
    submission_maps: list[dict[str, dict[str, str]]] = []
    for table, path in zip(submissions, submission_paths):
        if not table or SUBMISSION_COLUMNS - set(table[0]):
            raise RuntimeError(f"fail-closed: submission table missing columns: {path}")
        reviewers = {row["reviewer_id"] for row in table}
        if len(reviewers) != 1 or not next(iter(reviewers)):
            raise RuntimeError(f"fail-closed: each submission table must contain one reviewer: {path}")
        reviewer_ids.append(next(iter(reviewers)))
        table_map = {row["image_id"]: row for row in table}
        if len(table_map) != len(table) or set(table_map) != set(by_image):
            raise RuntimeError(f"fail-closed: reviewer submission must cover every image exactly: {path}")
        if not all(bool_value(row["review_pass"]) and row["submission_utc"].strip() for row in table):
            raise RuntimeError(f"fail-closed: reviewer submission is not frozen/complete: {path}")
        if any(row["blind_release_id"] != blind_release_id for row in table):
            raise RuntimeError(f"fail-closed: reviewer submission release binding mismatch: {path}")
        submission_maps.append(table_map)
    if reviewer_ids[0] == reviewer_ids[1]:
        raise RuntimeError("fail-closed: two distinct reviewers are required")
    roles_sha256 = validate_reviewer_roles(roles_path, reviewer_ids)

    match_rows: list[dict[str, Any]] = []
    instance_rows: list[dict[str, Any]] = []
    discrepancy_rows: list[dict[str, Any]] = []
    dice_values: list[float] = []
    boundary_values: list[float] = []
    hausdorff_values: list[float] = []
    class_a: list[str] = []
    class_b: list[str] = []
    feret_a: list[float] = []
    feret_b: list[float] = []
    contour_a: list[float] = []
    contour_b: list[float] = []
    total_a = total_b = matched_total = split_n = merge_n = 0
    reviewer_evidence: list[dict[str, str]] = []

    for image_id in sorted(by_image):
        base = by_image[image_id]
        raw_path = resolve_path(base["raw_file_path"], blinded_manifest_path)
        if not raw_path.is_file() or sha256(raw_path) != base["raw_sha256"].strip().lower():
            raise RuntimeError(f"fail-closed: blinded raw-image binding mismatch: {raw_path}")
        with Image.open(raw_path) as raw:
            expected_size = raw.size
        reviewer_data: list[tuple[np.ndarray, dict[int, dict[str, str]], list[int]]] = []
        for reviewer_index in (0, 1):
            submission = submission_maps[reviewer_index][image_id]
            mask_path = resolve_path(submission["instance_mask_path"], submission_paths[reviewer_index])
            annotation_path = resolve_path(submission["annotation_path"], submission_paths[reviewer_index])
            if not mask_path.is_file() or sha256(mask_path) != submission["instance_mask_sha256"].lower():
                raise RuntimeError(f"fail-closed: reviewer mask hash mismatch: {mask_path}")
            if not annotation_path.is_file() or sha256(annotation_path) != submission["annotation_sha256"].lower():
                raise RuntimeError(f"fail-closed: reviewer annotation hash mismatch: {annotation_path}")
            reviewer_evidence.append(
                {
                    "reviewer_id": reviewer_ids[reviewer_index],
                    "image_id": image_id,
                    "instance_mask_path": str(mask_path),
                    "instance_mask_sha256": submission["instance_mask_sha256"].lower(),
                    "annotation_path": str(annotation_path),
                    "annotation_sha256": submission["annotation_sha256"].lower(),
                }
            )
            mask = load_label_mask(mask_path, expected_size)
            labels = sorted(int(v) for v in np.unique(mask) if v > 0)
            annotations = load_annotations(annotation_path, image_id, set(labels))
            reviewer_data.append((mask, annotations, labels))
            for label in labels:
                ann = annotations[label]
                area_px = int(np.sum(mask == label))
                instance_rows.append(
                    {
                        "reviewer_id": reviewer_ids[reviewer_index], "image_id": image_id,
                        "reviewer_object_id": ann["reviewer_object_id"], "mask_label": label,
                        "area_px": area_px, "subarea_below_25px": area_px < 25,
                        "morphology_class": ann["morphology_class"], "border_touch": ann["border_touch"],
                        "counting_frame_status": ann["counting_frame_status"], "censor_type": ann["censor_type"],
                        "topology_status": ann["topology_status"],
                        "segmentation_disposition": ann["segmentation_disposition"],
                        "ambiguity_flag": ann["ambiguity_flag"], "confidence_code": ann["confidence_code"],
                        "exclusion_reason": ann["exclusion_reason"],
                    }
                )

        mask_a, annotations_a, labels_a = reviewer_data[0]
        mask_b, annotations_b, labels_b = reviewer_data[1]
        total_a += len(labels_a)
        total_b += len(labels_b)
        area_a = np.asarray([np.sum(mask_a == label) for label in labels_a], dtype=float)
        area_b = np.asarray([np.sum(mask_b == label) for label in labels_b], dtype=float)
        intersections = np.zeros((len(labels_a), len(labels_b)), dtype=float)
        for ia, label_a in enumerate(labels_a):
            values, counts = np.unique(mask_b[mask_a == label_a], return_counts=True)
            count_map = dict(zip(values.tolist(), counts.tolist()))
            for ib, label_b in enumerate(labels_b):
                intersections[ia, ib] = count_map.get(label_b, 0)
        union = area_a[:, None] + area_b[None, :] - intersections
        iou = np.divide(intersections, union, out=np.zeros_like(intersections), where=union > 0)
        minimum_area = np.minimum(area_a[:, None], area_b[None, :])
        containment = np.divide(intersections, minimum_area, out=np.zeros_like(intersections), where=minimum_area > 0)
        components = relation_components(iou, containment)
        for component_no, (indices_a, indices_b) in enumerate(components, start=1):
            if len(indices_a) == len(indices_b) == 1:
                relation = "1:1"
            elif len(indices_a) == 1 and len(indices_b) > 1:
                relation = "1:many_split_disagreement"
                split_n += 1
            elif len(indices_a) > 1 and len(indices_b) == 1:
                relation = "many:1_merge_disagreement"
                merge_n += 1
            elif indices_a and indices_b:
                relation = "many:many_complex_disagreement"
                split_n += 1
                merge_n += 1
            elif indices_a:
                relation = "reviewer_A_only"
            else:
                relation = "reviewer_B_only"
            if relation != "1:1":
                discrepancy_rows.append(
                    {
                        "image_id": image_id, "discrepancy_type": relation,
                        "reviewer_A_object_ids": ";".join(annotations_a[labels_a[i]]["reviewer_object_id"] for i in indices_a),
                        "reviewer_B_object_ids": ";".join(annotations_b[labels_b[j]]["reviewer_object_id"] for j in indices_b),
                        "required_action": "joint_adjudication_without_overwriting_originals",
                    }
                )

        if len(labels_a) and len(labels_b):
            cost = 1.0 - iou
            assigned_a, assigned_b = linear_sum_assignment(cost)
            assignments = [(ia, ib) for ia, ib in zip(assigned_a.tolist(), assigned_b.tolist()) if iou[ia, ib] >= 0.50]
        else:
            assignments = []
        matched_total += len(assignments)
        sx, sy = float(base["pixel_size_x_um"]), float(base["pixel_size_y_um"])
        for pair_no, (ia, ib) in enumerate(assignments, start=1):
            label_a, label_b = labels_a[ia], labels_b[ib]
            binary_a, binary_b = mask_a == label_a, mask_b == label_b
            intersection = intersections[ia, ib]
            dice = 2.0 * intersection / (area_a[ia] + area_b[ib])
            bf1, h95 = boundary_metrics(binary_a, binary_b)
            geom_a, geom_b = object_geometry(binary_a, sx, sy), object_geometry(binary_b, sx, sy)
            ann_a, ann_b = annotations_a[label_a], annotations_b[label_b]
            class_match = ann_a["morphology_class"] == ann_b["morphology_class"]
            row = {
                "image_id": image_id, "pair_id": f"{image_id}_P{pair_no:05d}",
                "reviewer_A_object_id": ann_a["reviewer_object_id"],
                "reviewer_B_object_id": ann_b["reviewer_object_id"],
                "relationship_type": "hungarian_1:1_iou_ge_0.50",
                "intersection_px": int(intersection), "iou": float(iou[ia, ib]), "dice": float(dice),
                "boundary_f1_2px": bf1, "hausdorff95_px": h95,
                "class_A": ann_a["morphology_class"], "class_B": ann_b["morphology_class"],
                "class_agreement": class_match,
                "feret_max_A_um": geom_a["feret_max"], "feret_max_B_um": geom_b["feret_max"],
                "contour_A_um": geom_a["contour"], "contour_B_um": geom_b["contour"],
                "width_A_um": geom_a["width"], "width_B_um": geom_b["width"],
                "centreline_AR_A": geom_a["centreline_ar"], "centreline_AR_B": geom_b["centreline_ar"],
                "straightness_A": geom_a["straightness"], "straightness_B": geom_b["straightness"],
                "orientation_A_deg": geom_a["orientation"], "orientation_B_deg": geom_b["orientation"],
            }
            match_rows.append(row)
            dice_values.append(float(dice))
            boundary_values.append(bf1)
            hausdorff_values.append(h95)
            class_a.append(ann_a["morphology_class"])
            class_b.append(ann_b["morphology_class"])
            feret_a.append(float(geom_a["feret_max"]))
            feret_b.append(float(geom_b["feret_max"]))
            if geom_a["contour"] is not None and geom_b["contour"] is not None:
                contour_a.append(float(geom_a["contour"]))
                contour_b.append(float(geom_b["contour"]))
            if not class_match or dice < 0.90 or bf1 < 0.90 or h95 > 2.0:
                discrepancy_rows.append(
                    {
                        "image_id": image_id,
                        "discrepancy_type": "matched_object_boundary_or_class",
                        "reviewer_A_object_ids": ann_a["reviewer_object_id"],
                        "reviewer_B_object_ids": ann_b["reviewer_object_id"],
                        "required_action": "joint_adjudication_without_overwriting_originals",
                    }
                )

    precision = matched_total / total_a if total_a else 1.0
    recall = matched_total / total_b if total_b else 1.0
    split_rate = split_n / total_a if total_a else 0.0
    merge_rate = merge_n / total_b if total_b else 0.0
    summary = {
        "stage": "Stage33C-Q",
        "blind_release_id": blind_release_id,
        "state": "PRECONSENSUS_FROZEN_PENDING_ADJUDICATION",
        "created_utc": utc_now(),
        "reviewer_A_id": reviewer_ids[0], "reviewer_B_id": reviewer_ids[1],
        "image_n": len(by_image), "reviewer_A_object_n": total_a,
        "reviewer_B_object_n": total_b, "matched_object_n": matched_total,
        "detection_precision_A_denominator": precision,
        "detection_recall_B_denominator": recall,
        "split_disagreement_rate": split_rate, "merge_disagreement_rate": merge_rate,
        "median_dice": float(np.median(dice_values)) if dice_values else None,
        "p10_dice": float(np.quantile(dice_values, 0.10)) if dice_values else None,
        "median_boundary_f1_2px": float(np.median(boundary_values)) if boundary_values else None,
        "median_hausdorff95_px": float(np.median(hausdorff_values)) if hausdorff_values else None,
        "morphology_class_cohen_kappa": cohen_kappa(class_a, class_b),
        "morphology_class_gwet_ac1": gwet_ac1(class_a, class_b),
        "feret_max_icc_A1": icc_absolute_single(feret_a, feret_b),
        "contour_length_icc_A1": icc_absolute_single(contour_a, contour_b),
        "subarea_below_25px_instance_n": sum(bool_value(row["subarea_below_25px"]) for row in instance_rows),
        "discrepancy_n": len(discrepancy_rows),
        "claim_boundary": "inter-reviewer preconsensus repeatability only; not accuracy, treatment effect, or degradation validation",
    }
    gates = {
        "precision_ge_0.95": precision >= 0.95,
        "recall_ge_0.95": recall >= 0.95,
        "split_rate_le_0.02": split_rate <= 0.02,
        "merge_rate_le_0.02": merge_rate <= 0.02,
        "median_dice_ge_0.90": bool(dice_values) and float(np.median(dice_values)) >= 0.90,
        "p10_dice_ge_0.80": bool(dice_values) and float(np.quantile(dice_values, 0.10)) >= 0.80,
        "median_boundary_f1_ge_0.90": bool(boundary_values) and float(np.median(boundary_values)) >= 0.90,
        "median_hausdorff95_le_2px": bool(hausdorff_values) and float(np.median(hausdorff_values)) <= 2.0,
        "class_kappa_ge_0.80": summary["morphology_class_cohen_kappa"] is not None and summary["morphology_class_cohen_kappa"] >= 0.80,
        "class_ac1_ge_0.90": summary["morphology_class_gwet_ac1"] is not None and summary["morphology_class_gwet_ac1"] >= 0.90,
        "feret_icc_ge_0.95": summary["feret_max_icc_A1"] is not None and summary["feret_max_icc_A1"] >= 0.95,
    }
    summary["preconsensus_gates"] = gates
    summary["preconsensus_gate_pass"] = all(gates.values())
    summary["final_empirical_qualification"] = "pending_consensus_and_heldout_reference_comparison"

    match_columns = list(match_rows[0]) if match_rows else [
        "image_id", "pair_id", "reviewer_A_object_id", "reviewer_B_object_id",
        "relationship_type", "intersection_px", "iou", "dice", "boundary_f1_2px",
        "hausdorff95_px", "class_A", "class_B", "class_agreement",
    ]
    write_csv(output / "preconsensus_matches.csv", match_rows, match_columns)
    write_csv(output / "reviewer_instances.csv", instance_rows, list(instance_rows[0]) if instance_rows else ["reviewer_id", "image_id", "reviewer_object_id"])
    discrepancy_columns = ["image_id", "discrepancy_type", "reviewer_A_object_ids", "reviewer_B_object_ids", "required_action"]
    write_csv(output / "discrepancy_queue.csv", discrepancy_rows, discrepancy_columns)
    adjudication_rows = [
        {
            **row, "consensus_status": "pending", "adjudication_reason_code": "",
            "final_mask_path": "", "final_mask_sha256": "", "adjudicator_1_id": "",
            "adjudicator_2_id": "", "adjudication_utc": "",
        }
        for row in discrepancy_rows
    ]
    adjudication_columns = discrepancy_columns + [
        "consensus_status", "adjudication_reason_code", "final_mask_path",
        "final_mask_sha256", "adjudicator_1_id", "adjudicator_2_id", "adjudication_utc",
    ]
    write_csv(output / "consensus_adjudication_template.csv", adjudication_rows, adjudication_columns)
    json_dump(output / "preconsensus_agreement_summary.json", summary)
    freeze = {
        "stage": "Stage33C-Q", "blind_release_id": blind_release_id,
        "state": "PRECONSENSUS_FROZEN_PENDING_ADJUDICATION",
        "created_utc": utc_now(), "blinded_manifest_sha256": sha256(blinded_manifest_path),
        "submission_A_sha256": sha256(submission_a_path), "submission_B_sha256": sha256(submission_b_path),
        "roles_and_key_custody_sha256": roles_sha256,
        "mask_qualifier_sha256": sha256(Path(__file__).resolve()),
        "stage33cm_geometry_helper_sha256": sha256(
            Path(__file__).resolve().parent / "analyze_stage33c_blinded_morphology_v1.py"
        ),
        "reviewer_evidence": sorted(
            reviewer_evidence, key=lambda row: (row["reviewer_id"], row["image_id"])
        ),
        "preconsensus_matches_sha256": sha256(output / "preconsensus_matches.csv"),
        "reviewer_instances_sha256": sha256(output / "reviewer_instances.csv"),
        "discrepancy_queue_sha256": sha256(output / "discrepancy_queue.csv"),
        "summary_sha256": sha256(output / "preconsensus_agreement_summary.json"),
        "no_consensus_mask_generated": True, "no_treatment_key_present": True,
    }
    json_dump(output / "preconsensus_freeze_manifest.json", freeze)
    completion = {
        "stage": "Stage33C-Q", "blind_release_id": blind_release_id, "status": "complete",
        "state": "PRECONSENSUS_FROZEN_PENDING_ADJUDICATION",
        "completed_utc": utc_now(), "freeze_manifest_sha256": sha256(output / "preconsensus_freeze_manifest.json"),
        "preconsensus_gate_pass": summary["preconsensus_gate_pass"],
        "final_empirical_qualification": "pending", "no_empirical_treatment_analysis": True,
        "no_treatment_reveal": True, "no_simulation": True,
    }
    json_dump(output / "completion.json", completion)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blinded-manifest", type=Path, required=True)
    parser.add_argument("--reviewer-a-submissions", type=Path, required=True)
    parser.add_argument("--reviewer-b-submissions", type=Path, required=True)
    parser.add_argument("--roles-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = qualify(
        args.blinded_manifest.resolve(), args.reviewer_a_submissions.resolve(),
        args.reviewer_b_submissions.resolve(), args.roles_file.resolve(), args.output.resolve(),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
