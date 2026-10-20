"""Read-only field/geometry preflight for the frozen Stage A shape-flow design."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage40_staging"))
import matrix_case_v1

PROTOCOL = ROOT / "stage109_designs/shape_flow_protocol_20260914/protocol.json"
COMPLETION = PROTOCOL.with_name("completion.json")
OUT = ROOT / "stage109_evaluations/field_scaling_preflight_20260914"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    protocol = load(PROTOCOL)
    completion = load(COMPLETION)
    if completion["protocol_sha256"] != sha(PROTOCOL):
        raise RuntimeError("frozen protocol hash drift")
    for section in ("input_hashes", "source_hashes"):
        for path, digest in protocol[section].items():
            if sha(path) != digest:
                raise RuntimeError(f"protocol lineage drift: {path}")
    u0 = protocol["flow"]["reference_u0_m_s"]
    rows = []
    for seed in (1, 2, 3):
        starts = load(ROOT / f"stage95_designs/common_admissible_population_01/starts_s{seed}.json")
        reference, _, length, _, files = matrix_case_v1.load(seed, target_velocity=u0)
        base = reference.u
        if abs(float(base[0, reference.fluid].mean()) - u0) > 1e-15:
            raise RuntimeError("reference mean flow mismatch")
        for factor in protocol["flow"]["candidate_factors"]:
            target = factor * u0
            field, _, returned_length, _, bound_files = matrix_case_v1.load(
                seed, target_velocity=target)
            mean = float(field.u[0, field.fluid].mean())
            max_scaling_error = float(np.max(np.abs(field.u - factor * base)))
            if (returned_length != length or tuple(map(str, files)) != tuple(map(str, bound_files))
                    or not np.array_equal(field.fluid, reference.fluid)
                    or abs(mean - target) > 1e-15 or max_scaling_error > 1e-15):
                raise RuntimeError(f"field scaling/binding mismatch seed={seed} factor={factor}")
            horizon = 2 * length / target
            if not protocol["observation"]["equal_time_query_s"] < horizon:
                raise RuntimeError("common-time query beyond horizon")
            for shape in protocol["shapes"]:
                a, b, _ = protocol["prolate_semiaxes_m"]
                if shape == "equal_volume_sphere":
                    a = b = protocol["equal_volume_sphere_radius_m"]
                diameter = 2 * (a*b*b)**(1/3)
                initial_re = []
                for sample_id in (protocol["population"]["stage_b_sentinel_ids"][str(seed)],
                                  *protocol["population"]["pilot_ids"][str(seed)]):
                    start = starts[sample_id]
                    if start["id"] != sample_id:
                        raise RuntimeError("sample ID/order drift")
                    local_u, _ = field.sample(start["position_m"])
                    initial_re.append(float(protocol["fluid"]["density_kg_m3"] *
                        np.linalg.norm(local_u) * diameter /
                        protocol["fluid"]["dynamic_viscosity_Pa_s"]))
                rows.append({
                    "packing_seed": seed, "shape": shape, "flow_factor": factor,
                    "mean_interstitial_velocity_m_s": mean,
                    "horizon_2pv_s": horizon,
                    "max_exact_field_scaling_error_m_s": max_scaling_error,
                    "max_initial_background_slip_re_for_sentinel_and_pilot": max(initial_re),
                    "initial_re_is_trajectory_bound": False,
                })
    if len(rows) != 18:
        raise RuntimeError("missing preflight rows")
    result = {
        "status": "code_scaling_preflight_passed_physical_linearity_unverified",
        "rows": rows,
        "checks": {"all_18_configurations_present": True,
                   "mean_velocity_and_exact_code_scaling": True,
                   "same_geometry_and_bound_field_per_packing": True,
                   "common_40s_query_within_all_2pv_horizons": True,
                   "dynamic_Re_gate": "not tested; initial background-slip Re is diagnostic only",
                   "physical_LBM_linearity_at_scaled_flows": "not tested",
                   "comparison_runner_uses_target_velocity": "not yet; existing run_local loads reference U0"},
        "input_hashes": {str(path): sha(path) for path in (PROTOCOL, COMPLETION,
                          *(ROOT / f"stage95_designs/common_admissible_population_01/starts_s{s}.json"
                            for s in (1, 2, 3)))},
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                          str(Path(matrix_case_v1.__file__).resolve()): sha(matrix_case_v1.__file__)},
        "claim_boundary": "Configuration and code-scaling preflight only; no physical flow linearity, contact dynamics, transport, or shape/flow contrast verified.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"status": result["status"],
                                    "results_sha256": sha(OUT / "results.json")})
    print(json.dumps({"status": result["status"], "rows": len(rows),
                      "maximum_initial_re": max(row["max_initial_background_slip_re_for_sentinel_and_pilot"]
                                            for row in rows)}))


if __name__ == "__main__":
    main()
