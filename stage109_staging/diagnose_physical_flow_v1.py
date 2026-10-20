"""Physical-scale diagnostics for Stage109 candidate flows; no flow solve."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage40_staging"))
import matrix_case_v1

PROTOCOL = ROOT / "stage109_designs/shape_flow_protocol_20260914/protocol.json"
POP = ROOT / "stage95_designs/common_admissible_population_01/results.json"
OUT = ROOT / "stage109_evaluations/physical_flow_diagnostics_20260914"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    protocol = read(PROTOCOL)
    completion = read(PROTOCOL.with_name("completion.json"))
    population = read(POP)
    if sha(PROTOCOL) != completion["protocol_sha256"]:
        raise RuntimeError("frozen protocol drift")
    if sha(matrix_case_v1.__file__) != population["source_hashes"][str(Path(matrix_case_v1.__file__).resolve())]:
        raise RuntimeError("field-loader source drift")
    expected_inputs = population["input_hashes"]
    rho = protocol["fluid"]["density_kg_m3"]
    mu = protocol["fluid"]["dynamic_viscosity_Pa_s"]
    rows = []
    for seed in (1, 2, 3):
        for factor in protocol["flow"]["candidate_factors"]:
            target = protocol["flow"]["reference_u0_m_s"] * factor
            field, geometry, length, spacing, files = matrix_case_v1.load(seed, target)
            for path in files:
                if str(path) not in expected_inputs or sha(path) != expected_inputs[str(path)]:
                    raise RuntimeError(f"packing artifact drift: {path}")
            fluid_velocity = field.u[:, field.fluid]
            max_speed = float(np.linalg.norm(fluid_velocity, axis=0).max())
            median_diameter = float(np.median(2 * geometry.r))
            min_diameter = float(np.min(2 * geometry.r))
            rows.append({
                "packing_seed": seed,
                "flow_factor": factor,
                "target_mean_interstitial_velocity_m_s": target,
                "measured_mean_axial_velocity_m_s": float(field.u[0, field.fluid].mean()),
                "maximum_local_cell_speed_m_s": max_speed,
                "maximum_local_to_mean_speed_ratio": max_speed / target,
                "median_sand_diameter_m": median_diameter,
                "minimum_sand_diameter_m": min_diameter,
                "field_cell_spacing_m": spacing,
                "median_grain_reynolds_at_mean_speed": rho * target * median_diameter / mu,
                "median_grain_reynolds_at_max_local_cell_speed": rho * max_speed * median_diameter / mu,
                "cell_reynolds_at_max_local_cell_speed": rho * max_speed * spacing / mu,
                "cells_across_fibre_minor_diameter": 2 * protocol["prolate_semiaxes_m"][1] / spacing,
                "cells_across_equal_volume_sphere_diameter": 2 * protocol["equal_volume_sphere_radius_m"] / spacing,
                "cells_across_fibre_major_length": 2 * protocol["prolate_semiaxes_m"][0] / spacing,
                "domain_length_m": length,
            })
    result = {
        "status": "physical_scale_diagnostics_only_flow_validity_open",
        "rows": rows,
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                          str(Path(matrix_case_v1.__file__).resolve()): sha(matrix_case_v1.__file__)},
        "input_hashes": {str(PROTOCOL): sha(PROTOCOL),
                         str(PROTOCOL.with_name("completion.json")): sha(PROTOCOL.with_name("completion.json")),
                         str(POP): sha(POP)},
        "claim_boundary": "Reynolds and cells-per-particle diagnostics from linearly rescaled archived LBM fields. These are not new flow solutions, a linear-response proof, wall-gradient error estimate, or transport validation.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"status": result["status"],
                                    "results_sha256": sha(OUT / "results.json")})
    print(json.dumps({
        "status": result["status"], "rows": len(rows),
        "max_median_grain_re_at_local_cell_speed": max(r["median_grain_reynolds_at_max_local_cell_speed"] for r in rows),
        "min_cells_across_fibre_minor_diameter": min(r["cells_across_fibre_minor_diameter"] for r in rows),
    }))


if __name__ == "__main__":
    main()
