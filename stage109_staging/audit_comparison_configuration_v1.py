"""Read-only Stage B configuration/lineage audit; does not run transport."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage109_staging"))
import comparison_case_core_v1 as adapter

OUT = ROOT / "stage109_evaluations/comparison_configuration_audit_20260914"
POP = ROOT / "stage95_designs/common_admissible_population_01"
OBS = ROOT / "stage108_runs/first_iid_fibre_2pv_01"
REG = ROOT / "stage109_evaluations/flow_adapter_regression_20260914"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def check_hash_map(hashes):
    for path, digest in hashes.items():
        if sha(path) != digest:
            raise RuntimeError(f"lineage drift: {path}")


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    protocol = read(adapter.PROTOCOL)
    protocol_completion = read(adapter.PROTOCOL.with_name("completion.json"))
    if (protocol_completion["protocol_sha256"] != sha(adapter.PROTOCOL)
            or protocol["status"] != "design_frozen_pending_stage_b_admissibility_and_cost"):
        raise RuntimeError("Stage A protocol drift")
    check_hash_map(protocol["source_hashes"])
    check_hash_map(protocol["input_hashes"])
    population = read(POP / "results.json")
    observation = read(OBS / "manifest.json")
    check_hash_map(population["source_hashes"])
    check_hash_map(population["input_hashes"])
    check_hash_map(observation["source_hashes"])
    check_hash_map(observation["input_hashes"])
    if (sha(adapter.h.DESIGN) != observation["input_hashes"][str(adapter.h.DESIGN)]
            or sha(adapter.h.matrix_case_v1.__file__) != observation["source_hashes"][str(Path(adapter.h.matrix_case_v1.__file__).resolve())]
            or sha(adapter.h.geometry_exact_v1.__file__) != observation["source_hashes"][str(Path(adapter.h.geometry_exact_v1.__file__).resolve())]):
        raise RuntimeError("comparison configuration core differs from Stage108")
    regression = read(REG / "results.json")
    regression_completion = read(REG / "completion.json")
    if (regression_completion["results_sha256"] != sha(REG / "results.json")
            or not all(regression["checks"].values())):
        raise RuntimeError("flow adapter regression drift")
    check_hash_map(regression["source_hashes"])
    check_hash_map(regression["input_hashes"])

    base = read(adapter.h.DESIGN)
    expected_inputs = population["input_hashes"]
    rows = []
    for seed in (1, 2, 3):
        sample_id = protocol["population"]["stage_b_sentinel_ids"][str(seed)]
        start = read(POP / f"starts_s{seed}.json")[sample_id]
        for factor in protocol["flow"]["candidate_factors"]:
            target = protocol["flow"]["reference_u0_m_s"] * factor
            field, _, length, _, files = adapter.h.matrix_case_v1.load(
                seed, target_velocity=target)
            for path in files:
                if str(path) not in expected_inputs or sha(path) != expected_inputs[str(path)]:
                    raise RuntimeError(f"packing {seed} geometry/field/record drift: {path}")
            if not np.isclose(field.u[0, field.fluid].mean(), target, rtol=0, atol=1e-15):
                raise RuntimeError("mean flow mismatch")
            for shape in protocol["shapes"]:
                cfg, state = adapter.resolve(seed, sample_id, shape, factor)
                unchanged = {k: v for k, v in cfg.items()
                             if k not in ("prolate_semiaxes_m", "target_mean_interstitial_velocity_m_s")}
                base_unchanged = {k: v for k, v in base.items()
                                  if k not in ("prolate_semiaxes_m", "target_mean_interstitial_velocity_m_s")}
                expected_axes = ([protocol["equal_volume_sphere_radius_m"]] * 3
                                 if shape == "equal_volume_sphere"
                                 else protocol["prolate_semiaxes_m"])
                if (unchanged != base_unchanged or cfg["prolate_semiaxes_m"] != expected_axes
                        or cfg["target_mean_interstitial_velocity_m_s"] != target
                        or state["position_m"] != start["position_m"]
                        or state["orientation"] != start["orientation"]
                        or state["velocity_generalized"] != [0.0] * 6):
                    raise RuntimeError(f"configuration or paired start drift: {seed}/{shape}/{factor}")
                rows.append({"packing_seed": seed, "sample_id": sample_id,
                             "shape": shape, "flow_factor": factor,
                             "mean_interstitial_velocity_m_s": target,
                             "horizon_2pv_s": 2 * length / target})
    if len(rows) != 18:
        raise RuntimeError("missing shape-flow configuration")
    result = {
        "status": "configuration_lineage_passed_transport_unrun",
        "checks": {
            "all_18_sentinel_configurations": True,
            "all_frozen_Stage108_source_and_input_hashes": True,
            "all_Stage95_packing_artifact_hashes": True,
            "base_config_unchanged_except_shape_and_flow": True,
            "exact_matched_initial_centres_and_orientation": True,
            "actual_mean_flow_matches_requested_target": True,
            "flow_adapter_regression_bound": True,
        },
        "rows": rows,
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                          str(Path(adapter.__file__).resolve()): sha(adapter.__file__)},
        "input_hashes": {str(path): sha(path) for path in
                         (adapter.PROTOCOL, adapter.PROTOCOL.with_name("completion.json"),
                          POP / "results.json", OBS / "manifest.json",
                          REG / "results.json", REG / "completion.json")},
        "claim_boundary": "Configuration and lineage only. Physical validity of flow scaling, dynamic Re, contact response, outlet events, three-level convergence and cost remain open.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"status": result["status"],
                                    "results_sha256": sha(OUT / "results.json")})
    print(json.dumps({"status": result["status"], "configurations": len(rows)}))


if __name__ == "__main__":
    main()
