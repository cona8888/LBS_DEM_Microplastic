from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
sys.path.insert(0, str(ROOT / "stage27_staging"))
import build_stage27a_mechanics_hydraulic_masks_v1 as api  # noqa: E402

STUDY = "stage29e_low_concentration_hydraulic_design_20260826"
SOURCE = ROOT / "stage29_designs" / STUDY / "geometry_01"
CONFIG = SOURCE / "resolved_config.json"
COMPLETION = SOURCE / "completion.json"
OUT = ROOT / "stage29_evaluations" / STUDY / "geometry_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def adjacency(a: np.ndarray, b: np.ndarray) -> int:
    return sum(int(np.count_nonzero(np.roll(a, s, axis=axis) & b)) for axis in range(3) for s in (-1, 1))


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    config, completion = json.loads(CONFIG.read_text()), json.loads(COMPLETION.read_text())
    with np.load(Path(config["clean_control"]["geometry"])) as data:
        clean_phase = np.asarray(data["phase"], dtype=np.uint8); sand = np.asarray(data["material"] == 1)
        length = float(data["cell_length_m"][0])
    source_checks = {k: Path(v["path"]).is_file() and sha(Path(v["path"])) == v["sha256"] for k, v in config["lineage"].items() if isinstance(v, dict) and "path" in v and "sha256" in v}
    case_checks, topology = {}, {}
    for row in config["geometry"]["cases"]:
        cid = row["case_id"]; artifact = config["geometry"]["artifacts"][cid]; path = Path(artifact["geometry"])
        with np.load(path) as data:
            phase = np.asarray(data["phase"], dtype=np.uint8); material = np.asarray(data["material"], dtype=np.uint8); centrelines = np.asarray(data["fibre_centrelines_m"], dtype=float); radius = float(data["fibre_radius_m"][0])
        masks = []
        for points in centrelines:
            mask = np.zeros_like(sand); api.mark_capsule(mask, points, radius, length); masks.append(mask)
        overlap, face = [], []
        for i in range(len(masks)):
            for j in range(i + 1, len(masks)):
                overlap.append(int(np.count_nonzero(masks[i] & masks[j]))); face.append(adjacency(masks[i], masks[j]))
        resolved = any(v > 0 for v in overlap + face); expected = row["topology"] in ("crossing", "one_contact")
        union = np.logical_or.reduce(masks) & ~sand
        checks = {"geometry_hash": sha(path) == artifact["geometry_sha256"], "vtk_hash": sha(Path(artifact["material_vtk"])) == artifact["material_vtk_sha256"], "mechanics_case_hash": sha(Path(artifact["mechanics_case_result"])) == artifact["mechanics_case_result_sha256"], "shape_matches_clean": phase.shape == clean_phase.shape, "sand_exact": np.array_equal(material == 1, sand), "phase_material_consistent": np.array_equal(phase != 0, material != 0), "centrelines_exact": centrelines.shape == (row["fibre_count"], 37, 3), "rasterisation_reproduces_material": np.array_equal(union, material == 2), "contact_topology_matches_label": resolved == expected}
        case_checks[cid] = checks; topology[cid] = {"expected_contact": expected, "resolved_contact": resolved, "raw_overlap_voxels": overlap, "periodic_face_adjacency_counts": face}
    checks = {"config_fail_closed": config["status"] == "geometry_built_independent_gpu_release_required" and config["authority"]["gpu_execution"] is False, "completion_passed_and_bound": completion.get("passed") is True and completion["config_sha256"] == sha(CONFIG), "clean_control_hash": sha(Path(config["clean_control"]["geometry"])) == config["clean_control"]["geometry_sha256"], "all_lineage_bound": all(source_checks.values()), "exact_eleven_cases": len(case_checks) == 11, "all_builder_checks": all(config["checks"].values()), "all_case_checks": all(all(v.values()) for v in case_checks.values()), "run_order_exact": [x["run_order"] for x in config["geometry"]["cases"]] == list(range(1, 12))}
    passed = all(checks.values())
    audit = {"schema": config["schema"] + ".geometry-audit", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": passed, "status": "passed_cpd2_geometry_audit_gpu_not_authorized" if passed else "failed_cpd2_geometry_audit", "checks": checks, "case_checks": case_checks, "topology": topology, "source_checks": source_checks, "bindings": {"config_sha256": sha(CONFIG), "completion_sha256": sha(COMPLETION)}, "authority": {"runner_and_gpu_release_design": passed, "gpu_execution": False, "cpd4": False, "permeability_claim": False}, "next_handoff": {"authorized": "design and independently audit the bounded eleven-case CPD2 runner/GPU release" if passed else "diagnosis only", "not_authorized": "GPU execution, CPD4, or permeability claims"}}
    OUT.mkdir(parents=True); ap = OUT / "geometry_audit.json"; ap.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    (OUT / "checkpoint_manifest.json").write_text(json.dumps({"schema": audit["schema"] + ".checkpoint", "passed": passed, "geometry_audit_sha256": sha(ap), "config_sha256": sha(CONFIG), "authority": audit["next_handoff"]}, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUT), "passed": passed, "status": audit["status"], "checks": checks, "topology": topology}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
