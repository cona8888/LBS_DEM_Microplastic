"""Derive physical-Re-matched lattice flow targets from accepted clean fields."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/resolved_config.json"
CONFIG_COMPLETION = CONFIG.with_name("completion.json")
STAGE95_RESULT = ROOT / "stage95_designs/common_admissible_population_01/results.json"
PROTOCOL = ROOT / "stage109_designs/shape_flow_protocol_20260914/protocol.json"
OUT = ROOT / "stage110_evaluations/flow_similarity_design_20260915"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    config, completion = read(CONFIG), read(CONFIG_COMPLETION)
    population, protocol = read(STAGE95_RESULT), read(PROTOCOL)
    pcompletion = read(PROTOCOL.with_name("completion.json"))
    if (not completion["passed"] or sha(CONFIG) != completion["config_sha256"]
            or sha(PROTOCOL) != pcompletion["protocol_sha256"]
            or sha(STAGE95_RESULT) != protocol["input_hashes"][str(STAGE95_RESULT)]):
        raise RuntimeError("frozen configuration/protocol drift")
    nu_lu = float(config["solver"]["kinematic_viscosity_lu"])
    rho = protocol["fluid"]["density_kg_m3"]
    mu = protocol["fluid"]["dynamic_viscosity_Pa_s"]
    if nu_lu <= 0 or rho <= 0 or mu <= 0:
        raise RuntimeError("invalid viscosity/density")
    c_s_lu = 1 / np.sqrt(3)
    input_paths = [CONFIG, CONFIG_COMPLETION, STAGE95_RESULT, PROTOCOL,
                   PROTOCOL.with_name("completion.json")]
    rows = []
    for seed in (1, 2, 3):
        case = f"s31b_n216_s{seed}_clean"
        geometry_path = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01" / case / "geometry_cpd2.npz"
        run = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01" / f"stage31e_{case}_cpd2"
        field_path, record_path = run / "final_fields.npz", run / "record.json"
        for path in (geometry_path, field_path, record_path):
            if str(path) not in population["input_hashes"] or sha(path) != population["input_hashes"][str(path)]:
                raise RuntimeError(f"accepted field/geometry drift: {path}")
        record = read(record_path)
        if (not record["passed"] or not record["converged"]
                or sha(field_path) != record["artifacts"]["final_fields_npz_sha256"]):
            raise RuntimeError(f"clean flow failed: {seed}")
        geometry, field = np.load(geometry_path), np.load(field_path)
        if not np.array_equal(geometry["phase"], field["phase"]):
            raise RuntimeError(f"phase mismatch: {seed}")
        fluid = field["phase"] == 0
        mean_lu = float(field["velocity_xyz_lu"][0, fluid].mean())
        diameter_m = float(np.median(2 * geometry["sand_radii_m"]))
        diameter_lu = diameter_m / float(geometry["spacing_m"][0])
        re_archived = mean_lu * diameter_lu / nu_lu
        if mean_lu <= 0 or diameter_lu <= 0 or re_archived <= 0:
            raise RuntimeError("invalid lattice flow scale")
        for factor in protocol["flow"]["candidate_factors"]:
            target = protocol["flow"]["reference_u0_m_s"] * factor
            re_physical = rho * target * diameter_m / mu
            matched_mean_lu = re_physical * nu_lu / diameter_lu
            rows.append({
                "packing_seed": seed,
                "flow_factor": factor,
                "physical_mean_interstitial_velocity_m_s": target,
                "median_sand_diameter_m": diameter_m,
                "median_sand_diameter_lu": diameter_lu,
                "physical_median_grain_Re_at_mean_speed": re_physical,
                "archived_mean_interstitial_velocity_lu": mean_lu,
                "archived_median_grain_Re_at_mean_speed": re_archived,
                "physical_to_archived_Re_ratio": re_physical / re_archived,
                "candidate_Re_matched_mean_interstitial_velocity_lu": matched_mean_lu,
                "candidate_Re_matched_mean_Mach_lu": matched_mean_lu / c_s_lu,
            })
        input_paths += [geometry_path, field_path, record_path]
    result = {
        "status": "re_similarity_targets_derived_no_flow_solve",
        "kinematic_viscosity_lu": nu_lu,
        "rows": rows,
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__)},
        "input_hashes": {str(p): sha(p) for p in input_paths},
        "claim_boundary": "Same median-grain/mean-interstitial Reynolds definition in lattice and SI units. Derived target velocities are a design diagnostic, not a converged physical-Re flow field or proof that the archived Stokes-like field can be linearly scaled.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"status": result["status"],
                                    "results_sha256": sha(OUT / "results.json")})
    print(json.dumps({"status": result["status"],
                      "archived_Re_range": [min(r["archived_median_grain_Re_at_mean_speed"] for r in rows),
                                            max(r["archived_median_grain_Re_at_mean_speed"] for r in rows)],
                      "target_Re_range": [min(r["physical_median_grain_Re_at_mean_speed"] for r in rows),
                                          max(r["physical_median_grain_Re_at_mean_speed"] for r in rows)],
                      "max_target_mean_Mach_lu": max(r["candidate_Re_matched_mean_Mach_lu"] for r in rows)}))


if __name__ == "__main__":
    main()
