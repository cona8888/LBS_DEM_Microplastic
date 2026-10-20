"""Local replay of the immutable matrix-profile contact failure."""
import argparse, json, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage37_staging"), str(ROOT / "stage39_staging")]
import transport_contact as mechanics
import trajectory_inertial_v2 as trajectory
import wall_field_v1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    parent_path = ROOT / "stage39_evaluations/matrix_profile_01/results.json"
    parent = json.loads(parent_path.read_text())
    state = parent["result"]
    geometry_path = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/s31b_n216_s2_clean/geometry_cpd2.npz"
    field_path = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01/stage31e_s31b_n216_s2_clean_cpd2/final_fields.npz"
    geometry_data = np.load(geometry_path)
    field_data = np.load(field_path)
    spacing = float(geometry_data["spacing_m"][0])
    length = float(geometry_data["cell_length_m"][0])
    phase = np.asarray(field_data["phase"]).transpose(2, 1, 0)
    velocity = np.asarray(field_data["velocity_xyz_lu"], float).transpose(0, 3, 2, 1)
    fluid = phase == 0
    velocity *= 1e-4 / float(velocity[0, fluid].mean())
    field = wall_field_v1.WallCellField(velocity, spacing, fluid)
    geometry = mechanics.GrainGeometry(
        np.asarray(geometry_data["sand_centres_m"]),
        np.asarray(geometry_data["sand_radii_m"]), length,
    )

    original_solve = trajectory.inertial.contact_model.contact_solve
    rows = []
    for contact_tolerance in (1e-10, 1e-8):
        for friction in (0.0, 0.3):
            def declared_solve(vfree, mobility, contacts, ell, dt, mu, tol=1e-9, maxiter=2000,
                               _tol=contact_tolerance):
                return original_solve(vfree, mobility, contacts, ell, dt, mu,
                                      tol=_tol, maxiter=10000)
            trajectory.inertial.contact_model.contact_solve = declared_solve
            started = time.perf_counter()
            result = trajectory.integrate(
                field, geometry, state["position_m"], state["orientation"],
                state["velocity_generalized"], 2e-4, 5e-5, 0.001002,
                1380, 998.2, [0, 0, -9.80665], friction, length, 0.02,
                added_mass_fraction=1, cutoff_ratio=0.2, roughness_ratio=0.01,
                displacement_fraction=0.1, relaxation_fraction=0.5,
                max_dt=0.01, max_steps=100000, wall_budget=60,
            )
            rows.append({"contact_tolerance": contact_tolerance, "friction": friction,
                         "external_runtime_s": time.perf_counter() - started, "result": result})
    trajectory.inertial.contact_model.contact_solve = original_solve
    checks = {
        "at_least_one_frictional_replay_advances": any(
            row["friction"] == 0.3 and row["result"]["time_s"] >= 0.019999 for row in rows
        ),
        "at_least_one_frictionless_replay_advances": any(
            row["friction"] == 0 and row["result"]["time_s"] >= 0.019999 for row in rows
        ),
        "reynolds_in_domain": max(row["result"]["max_reynolds"] for row in rows) <= 3,
        "no_material_penetration": min(row["result"]["minimum_gap_m"] for row in rows) >= -5e-10,
    }
    audit = {"completed": True, "passed": all(checks.values()),
             "checks": checks, "rows": rows,
             "claim_boundary": "local failure replay only; not a release result"}
    (output / "results.json").write_text(json.dumps(audit, indent=2))
    print(json.dumps({"passed": audit["passed"], "checks": checks,
                      "rows": [{"tol": row["contact_tolerance"], "friction": row["friction"],
                                "status": row["result"]["status"],
                                "time": row["result"]["time_s"],
                                "steps": row["result"]["steps"],
                                "runtime": row["external_runtime_s"]} for row in rows]}, indent=2))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
