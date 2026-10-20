#!/usr/bin/env python3
"""Freeze the Stage34C eight-case fragmentation CPD4 GPU configuration."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage34c_cpd4_first_fragmentation_geometry_20260902"
DESIGN = ROOT / "stage34_designs" / STUDY / "design_01/design_manifest.json"
DESIGN_COMPLETION = DESIGN.parent / "completion.json"
RASTER = ROOT / "stage34_designs" / STUDY / "raster_geometry_01/raster_manifest.json"
RASTER_COMPLETION = RASTER.parent / "completion.json"
RASTER_AUDIT = ROOT / "stage34_evaluations" / STUDY / "raster_audit_01/raster_audit.json"
RASTER_AUDIT_COMPLETION = RASTER_AUDIT.parent / "completion.json"
STAGE31_CONFIG = ROOT / "stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/resolved_config.json"
STAGE31_COMPLETION = ROOT / "stage31_runs/stage31f_selected_replicated_cpd4_20260827/gpu_confirmation_01/completion.json"
STAGE31_EVALUATION = ROOT / "stage31_evaluations/stage31f_selected_replicated_cpd4_20260827/gpu_evaluation_02/evaluation.json"
STAGE31_VISUAL_AUDIT = ROOT / "stage31_evaluations/stage31f_selected_replicated_cpd4_20260827/visual_audit_01/visual_audit.json"
CONTRACT = ROOT / "stage34_staging/STAGE34C_FRAGMENT_CPD4_GPU_CONTRACT.md"
RUNNER = ROOT / "stage34_staging/run_stage34c_fragment_cpd4_gpu_v1.py"
SUPERVISOR = ROOT / "stage34_staging/supervise_stage34c_fragment_cpd4_gpu_v1.ps1"
OUTPUT = ROOT / "stage34_designs" / STUDY / "gpu_config_01"

CONTEXTS = (
    ("n216_s1", "A", "s31b_n216_s1_A_f004_open"),
    ("n216_s1", "B", "s31b_n216_s1_B_f004_open"),
    ("n216_s2", "A", "s31b_n216_s2_A_f004_open"),
    ("n216_s2", "B", "s31b_n216_s2_B_f004_open"),
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def binding(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"required immutable evidence missing: {path}")
    return {"path": str(path), "sha256": sha(path)}


def verified_artifacts(directory: Path) -> dict:
    names = ("record.json", "audit.npz", "final_fields.npz", "final_shifted_state.npz", "final_flow.vtk")
    return {name: binding(directory / name) for name in names}


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable configuration: {OUTPUT}")
    required = (
        DESIGN, DESIGN_COMPLETION, RASTER, RASTER_COMPLETION, RASTER_AUDIT,
        RASTER_AUDIT_COMPLETION, STAGE31_CONFIG, STAGE31_COMPLETION,
        STAGE31_EVALUATION, STAGE31_VISUAL_AUDIT, CONTRACT, RUNNER, SUPERVISOR,
    )
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"required immutable evidence missing: {path}")

    design, design_done, raster, raster_done, raster_audit, raster_audit_done = map(
        load, (DESIGN, DESIGN_COMPLETION, RASTER, RASTER_COMPLETION, RASTER_AUDIT, RASTER_AUDIT_COMPLETION)
    )
    stage31, stage31_done, stage31_eval, stage31_visual = map(
        load, (STAGE31_CONFIG, STAGE31_COMPLETION, STAGE31_EVALUATION, STAGE31_VISUAL_AUDIT)
    )
    if not (design_done.get("passed") and raster_done.get("passed") and raster_audit.get("passed") and raster_audit_done.get("passed")):
        raise RuntimeError("Stage34C geometry evidence is not fully accepted")
    if raster_audit.get("status") != "passed_raster_audit_gpu_configuration_authorized":
        raise RuntimeError("Stage34C raster audit does not authorize GPU configuration")
    if not (stage31_done.get("passed") and stage31_eval.get("passed") and stage31_visual.get("passed")):
        raise RuntimeError("accepted Stage31f reference chain is incomplete")
    if stage31_eval.get("status") != "passed_selected_replicated_cpd4_solution_verification":
        raise RuntimeError("Stage31f solution verification status differs")
    if raster["source_bindings"]["stage31f_config"]["sha256"] != sha(STAGE31_CONFIG):
        raise RuntimeError("raster manifest does not bind current Stage31f config")
    if design["source_bindings"]["stage31f_evaluation"]["sha256"] != sha(STAGE31_EVALUATION):
        raise RuntimeError("design manifest does not bind current Stage31f evaluation")

    design_rows = {row["case_id"]: row for row in design["cases"]}
    raster_rows = {row["case_id"]: row for row in raster["cases"]}
    new_rows = [row for row in design["cases"] if int(row["fragments_per_parent"]) > 1]
    new_rows.sort(key=lambda row: int(row["new_randomized_run_order"]))
    if [int(row["new_randomized_run_order"]) for row in new_rows] != list(range(1, 9)):
        raise RuntimeError("Stage34C new-case order is not exactly 1..8")

    geometry_artifacts = {}
    cases = []
    for row in new_rows:
        case_id = row["case_id"]
        artifact = raster["artifacts"][case_id]
        geometry = Path(artifact["cpd4_geometry"])
        if artifact.get("cpd4_reused_accepted_intact") or sha(geometry) != artifact["cpd4_geometry_sha256"]:
            raise RuntimeError(f"new CPD4 geometry binding failed: {case_id}")
        metrics = raster_rows[case_id]["cpd4_metrics"]
        geometry_artifacts[case_id] = {
            "path": str(geometry), "sha256": sha(geometry),
            "fibre_only_voxel_count": int(metrics["fibre_only_voxel_count"]),
            "sand_voxel_count": int(metrics["sand_voxel_count"]),
            "spacing_m": float(metrics["spacing_m"]),
        }
        cases.append({
            "case_id": case_id,
            "run_order": int(row["new_randomized_run_order"]),
            "packing_id": row["packing_id"],
            "placement_block": row["placement_block"],
            "fragments_per_parent": int(row["fragments_per_parent"]),
            "total_fragment_count": int(row["total_fragment_count"]),
            "source_intact_case_id": row["source_intact_case_id"],
            "uniform_length_multiplier": float(raster_rows[case_id]["uniform_length_multiplier"]),
            "cpd4_fibre_volume_ratio_to_intact": float(raster_rows[case_id]["cpd4_fibre_volume_ratio_to_intact"]),
            "analytical_capsule_volume_deviation_from_intact": float(
                raster_audit["cases"][[item["case_id"] for item in raster_audit["cases"]].index(case_id)]["analytical_capsule_volume_deviation_from_intact"]
            ),
        })

    stage31_results = {row["case_id"]: row for row in stage31_done["paired_results"]}
    stage31_run = STAGE31_COMPLETION.parent
    intact_contexts = {}
    warm_starts = {}
    matched_controls = {}
    for packing_id, block, intact_id in CONTEXTS:
        context_id = f"{packing_id}_{block}"
        case_dir = stage31_run / f"stage31f_{intact_id}_cpd4"
        artifacts = verified_artifacts(case_dir)
        if artifacts["record.json"]["sha256"] != stage31_results[intact_id]["record_sha256"]:
            raise RuntimeError(f"Stage31f intact record binding failed: {intact_id}")
        intact_contexts[context_id] = {
            "packing_id": packing_id,
            "placement_block": block,
            "source_case_id": intact_id,
            "conductance_proxy_lu": float(stage31_results[intact_id]["conductance_proxy_lu"]),
            "paired_permeability_ratio": float(stage31_results[intact_id]["paired_permeability_ratio"]),
            "geometry": binding(Path(stage31["geometry"]["artifacts"][intact_id]["geometry"])),
            "artifacts": artifacts,
        }
        for case in cases:
            if case["packing_id"] == packing_id and case["placement_block"] == block:
                warm_starts[case["case_id"]] = {
                    "path": artifacts["final_fields.npz"]["path"],
                    "sha256": artifacts["final_fields.npz"]["sha256"],
                    "velocity_scale": float(stage31["solver"]["warm_start_velocity_scale"]),
                    "density_deviation_scale": float(stage31["solver"]["warm_start_density_deviation_scale"]),
                    "source_intact_case_id": intact_id,
                }

        if packing_id == "n216_s1":
            reused = stage31["reused_s1_clean_cpd4"]
            clean_record = Path(reused["record"]["path"])
            matched_controls[context_id] = {
                "packing_id": packing_id, "placement_block": block,
                "conductance_proxy_lu": float(reused["conductance_proxy_lu"]),
                "intrinsic_permeability_m2_descriptive_only": float(reused["intrinsic_permeability_m2"]),
                "record": binding(clean_record), "geometry": binding(Path(reused["geometry"]["path"])),
                "completion": binding(Path(reused["completion"]["path"])),
                "evaluation": binding(Path(reused["evaluation"]["path"])),
            }
        else:
            clean_id = "s31b_n216_s2_clean"
            clean_dir = stage31_run / f"stage31f_{clean_id}_cpd4"
            clean_result = stage31_results[clean_id]
            matched_controls[context_id] = {
                "packing_id": packing_id, "placement_block": block,
                "conductance_proxy_lu": float(clean_result["conductance_proxy_lu"]),
                "intrinsic_permeability_m2_descriptive_only": float(clean_result["intrinsic_permeability_m2_descriptive_only"]),
                "record": binding(clean_dir / "record.json"),
                "geometry": binding(Path(stage31["geometry"]["artifacts"][clean_id]["geometry"])),
                "completion": binding(STAGE31_COMPLETION), "evaluation": binding(STAGE31_EVALUATION),
            }

    if len(cases) != 8 or len(intact_contexts) != 4 or len(matched_controls) != 4 or len(warm_starts) != 8:
        raise RuntimeError("frozen Stage34C case/control cardinality differs")

    lineage = {
        "builder": binding(Path(__file__).resolve()), "contract": binding(CONTRACT),
        "runner": binding(RUNNER), "supervisor": binding(SUPERVISOR),
        "design_manifest": binding(DESIGN), "design_completion": binding(DESIGN_COMPLETION),
        "raster_manifest": binding(RASTER), "raster_completion": binding(RASTER_COMPLETION),
        "raster_audit": binding(RASTER_AUDIT), "raster_audit_completion": binding(RASTER_AUDIT_COMPLETION),
        "stage31f_config": binding(STAGE31_CONFIG), "stage31f_completion": binding(STAGE31_COMPLETION),
        "stage31f_evaluation": binding(STAGE31_EVALUATION), "stage31f_visual_audit": binding(STAGE31_VISUAL_AUDIT),
        "cuda_source": copy.deepcopy(stage31["lineage"]["cuda_source"]),
        "stage13_execution_manifest": copy.deepcopy(stage31["lineage"]["stage13_execution_manifest"]),
        "stage13_qualification": copy.deepcopy(stage31["lineage"]["stage13_qualification"]),
        "stage13_runner": copy.deepcopy(stage31["lineage"]["stage13_runner"]),
        "qualified_ptx_sha256": stage31["lineage"]["qualified_ptx_sha256"],
    }
    config = {
        "schema": "lbs.stage34c-fragment-cpd4-gpu.v1",
        "status": "fragment_cpd4_configuration_frozen_independent_gpu_release_required",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": design["research_question"],
        "claim_boundary": design["claim_boundary"],
        "solver": copy.deepcopy(stage31["solver"]),
        "fluid": copy.deepcopy(stage31["fluid"]),
        "execution": copy.deepcopy(stage31["execution"]),
        "acceptance": copy.deepcopy(stage31["acceptance"]),
        "analysis": copy.deepcopy(design["analysis"]),
        "lineage": lineage,
        "geometry": {"resolution": [186, 186, 186], "cases": cases, "artifacts": geometry_artifacts},
        "intact_contexts": intact_contexts,
        "matched_clean_controls": matched_controls,
        "warm_starts": warm_starts,
        "checks": {
            "stage34c_raster_chain_passed": True,
            "stage31f_reference_chain_passed": True,
            "exact_eight_new_cases": len(cases) == 8,
            "exact_four_hash_reused_intact_contexts": len(intact_contexts) == 4,
            "exact_four_context_to_clean_mappings": len(matched_controls) == 4,
            "all_warm_starts_context_matched": len(warm_starts) == 8,
            "solver_exact_stage31f": copy.deepcopy(stage31["solver"]) == stage31["solver"],
            "cpd6_flow_not_configured": True,
            "monotonicity_not_imposed": design["analysis"]["monotonicity_imposed"] is False,
        },
        "authority": {
            "gpu_flow_configuration": True, "independent_gpu_release": False,
            "gpu_cpd4_execution": False, "cpd6_flow_execution": False,
            "independent_evaluation": False, "render": False,
            "absolute_permeability_validation_claim": False, "chemical_degradation_claim": False,
            "mechanics_rerun": False, "mobile_sand": False, "migration": False,
            "clogging": False, "deformation": False, "transient_coupling": False,
            "two_way_coupling": False,
        },
    }
    OUTPUT.mkdir(parents=True)
    config_path = OUTPUT / "resolved_config.json"
    write(config_path, config)
    completion = {
        "schema": config["schema"] + ".config-completion",
        "status": "passed_fragment_cpd4_configuration_freeze",
        "passed": True, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": sha(config_path), "case_count": len(cases),
        "run_order": [row["case_id"] for row in cases],
        "lineage_hashes": {key: value["sha256"] for key, value in lineage.items() if isinstance(value, dict)},
        "authority": config["authority"], "claim_boundary": config["claim_boundary"],
    }
    write(OUTPUT / "completion.json", completion)
    print(json.dumps({"passed": True, "config": str(config_path), "config_sha256": sha(config_path),
                      "completion": str(OUTPUT / 'completion.json'), "run_order": completion["run_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
