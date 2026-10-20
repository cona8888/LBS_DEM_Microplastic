#!/usr/bin/env python3
"""Fail-closed evaluator for the frozen Stage32C matched validation design."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


TRUE = {"1", "true", "yes", "y"}
FALSE = {"0", "false", "no", "n"}
CAPTURE_FIELDS = [
    "run_order", "specimen_id", "phase", "preparation_block", "batch_id",
    "dry_sand_mass_g", "fibre_mass_g", "initial_void_ratio", "final_void_ratio",
    "water_temperature_c", "specimen_diameter_mm", "specimen_length_mm",
    "head_difference_m", "collection_time_s", "collected_water_mass_g",
    "K_raw_m_s", "K20_m_s", "valid", "rejection_reason", "operator_notes",
]
LINEARITY_FIELDS = [
    "specimen_id", "determination_id", "water_temperature_c",
    "specimen_diameter_mm", "specimen_length_mm", "head_difference_m",
    "collection_time_s", "collected_water_mass_g", "K_raw_m_s", "K20_m_s",
    "valid", "rejection_reason", "operator_notes",
]
T95 = {
    1: 12.7062, 2: 4.3027, 3: 3.1824, 4: 2.7764, 5: 2.5706,
    6: 2.4469, 7: 2.3646, 8: 2.3060, 9: 2.2622, 10: 2.2281,
    11: 2.2010, 12: 2.1788, 13: 2.1604, 14: 2.1448, 15: 2.1314,
    16: 2.1199, 17: 2.1098, 18: 2.1009, 19: 2.0930, 20: 2.0860,
    21: 2.0796, 22: 2.0739, 23: 2.0687, 24: 2.0639, 25: 2.0595,
    26: 2.0555, 27: 2.0518, 28: 2.0484, 29: 2.0452, 30: 2.0423,
    37: 2.0262,
}


class EvaluationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def binding(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256(path)}


def verify_binding(name: str, item: dict) -> None:
    path = Path(item["path"])
    if not path.is_file():
        raise EvaluationError(f"bound file missing: {name}: {path}")
    actual = sha256(path)
    if actual.lower() != str(item["sha256"]).lower():
        raise EvaluationError(f"SHA-256 mismatch: {name}: expected {item['sha256']}, got {actual}")


def read_csv(path: Path, expected_fields: list[str] | None = None) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)
    if expected_fields is not None and fields != expected_fields:
        raise EvaluationError(f"unexpected columns in {path}: {fields}")
    return fields, rows


def parse_float(row: dict[str, str], field: str, context: str, positive: bool = False) -> float:
    raw = row.get(field, "").strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise EvaluationError(f"invalid {field} for {context}: {raw!r}") from exc
    if not math.isfinite(value) or (positive and value <= 0.0):
        raise EvaluationError(f"out-of-range {field} for {context}: {raw!r}")
    return value


def parse_valid(raw: str, context: str) -> bool:
    token = raw.strip().lower()
    if token in TRUE:
        return True
    if token in FALSE:
        return False
    raise EvaluationError(f"unsupported or blank valid token for {context}: {raw!r}")


def water_density_kg_m3(temp_c: float) -> float:
    return 1000.0 * (1.0 - ((temp_c + 288.9414) / (508929.2 * (temp_c + 68.12963))) * (temp_c - 3.9863) ** 2)


def water_viscosity_pa_s(temp_c: float) -> float:
    return 2.414e-5 * 10.0 ** (247.8 / (temp_c + 133.15))


def hydraulic_values(temp_c: float, diameter_mm: float, length_mm: float, head_m: float,
                     time_s: float, water_mass_g: float) -> tuple[float, float, float, float]:
    rho = water_density_kg_m3(temp_c)
    volume_m3 = (water_mass_g / 1000.0) / rho
    area_m2 = math.pi * (diameter_mm / 2000.0) ** 2
    length_m = length_mm / 1000.0
    discharge_m3_s = volume_m3 / time_s
    gradient = head_m / length_m
    k_raw = discharge_m3_s * length_m / (area_m2 * head_m)
    rho20 = water_density_kg_m3(20.0)
    k20 = k_raw * (water_viscosity_pa_s(temp_c) / water_viscosity_pa_s(20.0)) * (rho20 / rho)
    return k_raw, k20, discharge_m3_s, gradient


def crosscheck(row: dict[str, str], field: str, calculated: float, context: str) -> None:
    raw = row.get(field, "").strip()
    if not raw:
        return
    supplied = parse_float(row, field, context, positive=True)
    if abs(supplied - calculated) / calculated > 0.005:
        raise EvaluationError(f"{field} cross-check exceeds 0.5% for {context}")


def mean_ci(values: list[float]) -> dict[str, float | int | None]:
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "sample_sd": None, "ci95_low": None, "ci95_high": None}
    mean = statistics.fmean(values)
    if n == 1:
        return {"n": 1, "mean": mean, "sample_sd": None, "ci95_low": None, "ci95_high": None}
    sd = statistics.stdev(values)
    df = n - 1
    critical = T95.get(df, 2.0262 if df <= 37 else 1.96)
    half = critical * sd / math.sqrt(n)
    return {"n": n, "mean": mean, "sample_sd": sd, "ci95_low": mean - half, "ci95_high": mean + half}


def intervals_overlap(low_a: float | None, high_a: float | None, low_b: float, high_b: float) -> bool:
    return low_a is not None and high_a is not None and max(low_a, low_b) <= min(high_a, high_b)


def r_squared(x: list[float], y: list[float]) -> float:
    if len(x) < 2 or len(set(x)) < 2:
        return float("nan")
    xm, ym = statistics.fmean(x), statistics.fmean(y)
    sxx = sum((v - xm) ** 2 for v in x)
    slope = sum((a - xm) * (b - ym) for a, b in zip(x, y)) / sxx
    intercept = ym - slope * xm
    residual = sum((b - (intercept + slope * a)) ** 2 for a, b in zip(x, y))
    total = sum((b - ym) ** 2 for b in y)
    return 1.0 if total == 0.0 and residual == 0.0 else (1.0 - residual / total if total > 0 else float("nan"))


def evaluate(args: argparse.Namespace) -> dict:
    release = args.release_dir.resolve()
    manifest_path = release / "release_manifest.json"
    if not manifest_path.is_file():
        raise EvaluationError("release_manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "lbs.stage32c-blinded-validation-release.v1" or manifest.get("passed") is not True:
        raise EvaluationError("release manifest is not an accepted Stage32C v1 release")
    for name, item in manifest["source_bindings"].items():
        verify_binding(f"source:{name}", item)
    for name, item in manifest["artifacts"].items():
        verify_binding(f"artifact:{name}", item)

    _, design_rows = read_csv(release / "preparation_schedule.csv")
    design_by_id = {row["specimen_id"]: row for row in design_rows}
    if len(design_rows) != 38 or len(design_by_id) != 38:
        raise EvaluationError("release design is not exactly 38 unique specimens")
    _, capture_rows = read_csv(args.capture.resolve(), CAPTURE_FIELDS)
    capture_by_id = {row["specimen_id"]: row for row in capture_rows}
    if len(capture_rows) != 38 or len(capture_by_id) != 38 or set(capture_by_id) != set(design_by_id):
        raise EvaluationError("completed capture identities do not exactly match the frozen 38 specimens")
    for sid, design in design_by_id.items():
        row = capture_by_id[sid]
        for field in ["run_order", "phase", "preparation_block"]:
            if row[field].strip() != design[field].strip():
                raise EvaluationError(f"altered frozen identity field {field} for {sid}")

    applicable_phase = 1 if args.phase == "phase1" else 2
    results: list[dict] = []
    for design in design_rows:
        sid = design["specimen_id"]
        row = capture_by_id[sid]
        phase = int(design["phase"])
        result = {
            "specimen_id": sid, "run_order": int(design["run_order"]), "phase": phase,
            "preparation_block": int(design["preparation_block"]), "group_id": design["group_id"],
            "orientation": design["orientation"], "target_dry_mass_percent": float(design["target_dry_mass_percent"]),
            "applicable": phase <= applicable_phase, "eligible": False, "reasons": [],
            "batch_id": row["batch_id"].strip(), "K_raw_m_s": None, "K20_m_s": None, "ratio_to_batch_clean": None,
        }
        if not result["applicable"]:
            results.append(result)
            continue
        operator_valid = parse_valid(row["valid"], sid)
        if not operator_valid:
            reason = row["rejection_reason"].strip()
            if not reason:
                raise EvaluationError(f"operator-rejected row lacks rejection_reason: {sid}")
            result["reasons"].append(f"operator_rejected:{reason}")
            results.append(result)
            continue

        batch = row["batch_id"].strip()
        if not batch:
            result["reasons"].append("missing_batch_id")
        dry_mass = parse_float(row, "dry_sand_mass_g", sid, positive=True)
        fibre_mass = parse_float(row, "fibre_mass_g", sid, positive=False)
        if fibre_mass < 0:
            raise EvaluationError(f"negative fibre_mass_g for {sid}")
        final_e = parse_float(row, "final_void_ratio", sid)
        temp = parse_float(row, "water_temperature_c", sid)
        diameter = parse_float(row, "specimen_diameter_mm", sid, positive=True)
        length = parse_float(row, "specimen_length_mm", sid, positive=True)
        head = parse_float(row, "head_difference_m", sid, positive=True)
        time_s = parse_float(row, "collection_time_s", sid, positive=True)
        water_mass = parse_float(row, "collected_water_mass_g", sid, positive=True)
        if not 0.734 <= final_e <= 0.754:
            result["reasons"].append("final_void_ratio_outside_frozen_tolerance")
        if not 19.5 <= temp <= 20.5:
            result["reasons"].append("water_temperature_outside_frozen_tolerance")
        target = result["target_dry_mass_percent"]
        achieved = 100.0 * fibre_mass / dry_mass
        result["achieved_dry_mass_percent"] = achieved
        if target == 0.0:
            if fibre_mass > 0.001:
                result["reasons"].append("clean_fibre_mass_exceeds_0p001_g")
        elif abs(achieved - target) > max(0.0005, 0.05 * target):
            result["reasons"].append("achieved_concentration_outside_frozen_tolerance")
        k_raw, k20, _, _ = hydraulic_values(temp, diameter, length, head, time_s, water_mass)
        crosscheck(row, "K_raw_m_s", k_raw, sid)
        crosscheck(row, "K20_m_s", k20, sid)
        result["K_raw_m_s"], result["K20_m_s"] = k_raw, k20
        result["eligible"] = not result["reasons"]
        results.append(result)

    clean_batch: dict[str, list[float]] = {}
    for result in results:
        if result["eligible"] and result["group_id"] == "clean":
            clean_batch.setdefault(result["batch_id"], []).append(result["K20_m_s"])
    clean_batch_means = {key: statistics.fmean(values) for key, values in clean_batch.items()}
    for result in results:
        if not result["applicable"] or not result["eligible"] or result["group_id"] == "clean":
            continue
        clean_mean = clean_batch_means.get(result["batch_id"])
        if clean_mean is None:
            result["eligible"] = False
            result["reasons"].append("no_eligible_clean_control_in_same_batch")
        else:
            result["ratio_to_batch_clean"] = result["K20_m_s"] / clean_mean

    predictions = {row["group_id"]: {
        "minimum": float(row["numerical_minimum_ratio"]),
        "mean": float(row["numerical_mean_ratio"]),
        "maximum": float(row["numerical_maximum_ratio"]),
    } for row in design_rows}
    protocol_path = Path(manifest["source_bindings"]["stage32a_protocol"]["path"])
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))

    groups: dict[str, dict] = {}
    for group_id in sorted({r["group_id"] for r in results if r["phase"] == 1}):
        eligible = [r for r in results if r["eligible"] and r["group_id"] == group_id and r["phase"] == 1]
        values = [r["K20_m_s"] for r in eligible] if group_id == "clean" else [r["ratio_to_batch_clean"] for r in eligible]
        groups[group_id] = {**mean_ci(values), "metric": "K20_m_s" if group_id == "clean" else "ratio_to_batch_clean"}
        if group_id != "clean":
            pred = predictions[group_id]
            groups[group_id]["numerical_range"] = [pred["minimum"], pred["maximum"]]
            groups[group_id]["interval_overlaps_numerical_range"] = intervals_overlap(
                groups[group_id]["ci95_low"], groups[group_id]["ci95_high"], pred["minimum"], pred["maximum"])

    clean = groups["clean"]
    clean_cv = (clean["sample_sd"] / clean["mean"]) if clean["n"] > 1 and clean["mean"] else None
    clean_envelope = protocol["frozen_predictions"]["clean_cpd2_K20_m_s_envelope"]
    clean_magnitude = intervals_overlap(clean["ci95_low"], clean["ci95_high"], clean_envelope[0], clean_envelope[1])
    phase1_counts = all(summary["n"] >= 5 for summary in groups.values())
    high_ids = ["iso_0p051576", "iso_0p098418", "iso_0p401820"]
    relative_overlap_count = sum(bool(groups[g]["interval_overlaps_numerical_range"]) for g in high_ids)
    high_upper_below_one = groups["iso_0p401820"]["ci95_high"] is not None and groups["iso_0p401820"]["ci95_high"] < 1.0

    _, linearity_rows = read_csv(args.linearity.resolve(), LINEARITY_FIELDS)
    determinations: dict[str, list[dict]] = {}
    determination_ids: set[tuple[str, str]] = set()
    for row in linearity_rows:
        sid = row["specimen_id"].strip()
        did = row["determination_id"].strip()
        if not sid or sid not in design_by_id or not did:
            raise EvaluationError("linearity row has missing/unknown specimen_id or determination_id")
        key = (sid, did)
        if key in determination_ids:
            raise EvaluationError(f"duplicate linearity determination: {sid}/{did}")
        determination_ids.add(key)
        valid = parse_valid(row["valid"], f"linearity {sid}/{did}")
        if not valid:
            if not row["rejection_reason"].strip():
                raise EvaluationError(f"rejected linearity row lacks reason: {sid}/{did}")
            continue
        temp = parse_float(row, "water_temperature_c", key, positive=False)
        diameter = parse_float(row, "specimen_diameter_mm", key, positive=True)
        length = parse_float(row, "specimen_length_mm", key, positive=True)
        head = parse_float(row, "head_difference_m", key, positive=True)
        time_s = parse_float(row, "collection_time_s", key, positive=True)
        mass = parse_float(row, "collected_water_mass_g", key, positive=True)
        if not 19.5 <= temp <= 20.5:
            raise EvaluationError(f"linearity temperature outside tolerance: {sid}/{did}")
        k_raw, k20, discharge, gradient = hydraulic_values(temp, diameter, length, head, time_s, mass)
        crosscheck(row, "K_raw_m_s", k_raw, f"linearity {sid}/{did}")
        crosscheck(row, "K20_m_s", k20, f"linearity {sid}/{did}")
        determinations.setdefault(sid, []).append({"head": head, "gradient": gradient, "discharge": discharge, "K20": k20})

    linearity_summary = []
    eligible_by_id = {r["specimen_id"]: r for r in results}
    for sid, values in sorted(determinations.items()):
        primary = eligible_by_id[sid]
        ks = [v["K20"] for v in values]
        cv = statistics.stdev(ks) / statistics.fmean(ks) if len(ks) > 1 else None
        r2 = r_squared([v["gradient"] for v in values], [v["discharge"] for v in values])
        passed = bool(primary["eligible"] and len(values) >= 3 and len({v["head"] for v in values}) >= 3 and r2 >= 0.99 and cv is not None and cv <= 0.05)
        linearity_summary.append({"specimen_id": sid, "group_id": primary["group_id"], "n": len(values), "r_squared": r2, "K20_cv": cv, "passed": passed})
    clean_linearity = any(x["passed"] and x["group_id"] == "clean" for x in linearity_summary)
    high_linearity = any(x["passed"] and x["group_id"] == "iso_0p401820" for x in linearity_summary)
    linearity_gate = clean_linearity and high_linearity

    phase2_release = bool(phase1_counts and clean_cv is not None and clean_cv <= 0.05 and clean_magnitude and linearity_gate)
    phase1_model_support = bool(phase1_counts and clean_cv is not None and clean_cv <= 0.05 and clean_magnitude and
                                relative_overlap_count >= 2 and high_upper_below_one and linearity_gate)
    orientation = {"evaluated": False, "supported": None, "groups": {}}
    if args.phase == "all" and phase2_release:
        for group_id in ["parallel_0p401820", "transverse_0p401820"]:
            vals = [r["ratio_to_batch_clean"] for r in results if r["eligible"] and r["group_id"] == group_id]
            orientation["groups"][group_id] = mean_ci(vals)
        p = orientation["groups"]["parallel_0p401820"]
        t = orientation["groups"]["transverse_0p401820"]
        iso = groups["iso_0p401820"]
        counts_ok = p["n"] >= 3 and t["n"] >= 3
        orientation["evaluated"] = counts_ok
        orientation["supported"] = bool(counts_ok and p["mean"] < iso["mean"] < t["mean"])

    overall_support = phase1_model_support if args.phase == "phase1" else bool(phase1_model_support and orientation["supported"] is True)
    return {
        "schema": "lbs.stage32c-matched-validation-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "phase": args.phase,
        "status": "evaluated_without_posthoc_model_change",
        "raw_bindings": {"release_manifest": binding(manifest_path), "capture": binding(args.capture.resolve()), "linearity": binding(args.linearity.resolve())},
        "clean_batch_means_K20_m_s": clean_batch_means,
        "group_results": groups,
        "linearity_controls": linearity_summary,
        "gates": {
            "phase1_minimum_counts": phase1_counts,
            "clean_cv": clean_cv,
            "clean_cv_at_most_0p05": clean_cv is not None and clean_cv <= 0.05,
            "clean_ci_overlaps_numerical_envelope": clean_magnitude,
            "relative_interval_overlap_count_high_groups": relative_overlap_count,
            "relative_overlap_at_least_two": relative_overlap_count >= 2,
            "high_concentration_upper_ci_below_one": high_upper_below_one,
            "clean_linearity": clean_linearity,
            "high_concentration_linearity": high_linearity,
            "phase2_release_authorized": phase2_release,
            "phase1_model_support": phase1_model_support,
            "orientation": orientation,
            "overall_preregistered_support": overall_support,
        },
        "specimen_results": results,
        "claim_boundary": "This evaluation can support or challenge the frozen model only for the matched fixed-solid saturated constant-head scope; it does not validate migration, clogging, deformation, or coupling.",
        "passed": True,
    }


def write_results(output: Path, evaluation: dict) -> None:
    output.mkdir(parents=True)
    (output / "evaluation.json").write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    fields = ["run_order", "specimen_id", "phase", "group_id", "orientation", "batch_id", "eligible", "reasons", "K_raw_m_s", "K20_m_s", "ratio_to_batch_clean"]
    with (output / "specimen_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in evaluation["specimen_results"]:
            writer.writerow({field: json.dumps(row[field]) if field == "reasons" else row.get(field) for field in fields})
    completion = {"schema": "lbs.stage32c-evaluation-completion.v1", "status": "complete", "evaluation_sha256": sha256(output / "evaluation.json"), "passed": True}
    (output / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--linearity", type=Path, required=True)
    parser.add_argument("--phase", choices=["phase1", "all"], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        print(f"Refusing to overwrite output: {output}", file=sys.stderr)
        return 2
    try:
        evaluation = evaluate(args)
        write_results(output, evaluation)
    except Exception as exc:
        output.mkdir(parents=True, exist_ok=False)
        failure = {"schema": "lbs.stage32c-evaluation-failure.v1", "status": "failed_closed", "error_type": type(exc).__name__, "error": str(exc), "passed": False}
        (output / "failure.json").write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(failure, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({"output_dir": str(output), "overall_preregistered_support": evaluation["gates"]["overall_preregistered_support"], "passed": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
