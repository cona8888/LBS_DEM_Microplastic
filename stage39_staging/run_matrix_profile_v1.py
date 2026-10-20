"""One-trajectory physical-PET cost/applicability profile; no release estimate."""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage37_staging"), str(ROOT / "stage39_staging")]
import transport_contact as mechanics
import trajectory_inertial_v2 as trajectory
import wall_field_v1


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)

    seed = 2
    case = f"s31b_n216_s{seed}_clean"
    geometry_path = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01" / case / "geometry_cpd2.npz"
    run_path = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01" / f"stage31e_{case}_cpd2"
    field_path = run_path / "final_fields.npz"
    record_path = run_path / "record.json"
    starts_path = ROOT / "stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s2.json"
    record = json.loads(record_path.read_text())
    if not record.get("passed") or sha(field_path) != record["artifacts"]["final_fields_npz_sha256"]:
        raise RuntimeError("archived flow record is not accepted or hash bound")

    geometry_data = np.load(geometry_path)
    field_data = np.load(field_path)
    spacing = float(geometry_data["spacing_m"][0])
    length = float(geometry_data["cell_length_m"][0])
    phase = np.asarray(field_data["phase"]).transpose(2, 1, 0)
    geometry_phase = np.asarray(geometry_data["phase"]).transpose(2, 1, 0)
    if not np.array_equal(phase, geometry_phase):
        raise RuntimeError("field/geometry phase mismatch")
    velocity = np.asarray(field_data["velocity_xyz_lu"], float).transpose(0, 3, 2, 1)
    fluid = phase == 0
    target_velocity = 1e-4
    velocity *= target_velocity / float(velocity[0, fluid].mean())
    field = wall_field_v1.WallCellField(velocity, spacing, fluid)
    geometry = mechanics.GrainGeometry(
        np.asarray(geometry_data["sand_centres_m"]),
        np.asarray(geometry_data["sand_radii_m"]), length,
    )
    start = json.loads(starts_path.read_text())[0]
    a, b = 2e-4, 5e-5
    horizon = 0.1 * length / target_velocity
    result = trajectory.integrate(
        field, geometry, start["position_m"], start["orientation"], np.zeros(6),
        a, b, 0.001002, 1380, 998.2, [0, 0, -9.80665], 0.3, length, horizon,
        added_mass_fraction=1, cutoff_ratio=0.2, roughness_ratio=0.01,
        displacement_fraction=0.1, relaxation_fraction=0.1,
        max_dt=0.01, max_steps=500000, wall_budget=120,
    )
    sources = [Path(__file__), Path(trajectory.__file__), Path(trajectory.previous.__file__),
               Path(trajectory.inertial.__file__), Path(wall_field_v1.__file__),
               geometry_path, field_path, record_path, starts_path]
    audit = {
        "completed": True,
        "passed": result["status"] not in ("numerical_failure", "unresolved_field"),
        "result": result,
        "profile": {"packing_seed": seed, "shape": "prolate_AR4", "horizon_pore_volumes": 0.1,
                    "initial_velocity": "rest", "friction": 0.3,
                    "roughness_over_grain_radius": 0.01, "added_mass": "potential_flow"},
        "input_hashes": {str(path.resolve()): sha(path) for path in sources},
        "claim_boundary": "single physical-PET cost/applicability profile; not release fraction",
    }
    (output / "results.json").write_text(json.dumps(audit, indent=2))
    print(json.dumps({"passed": audit["passed"], "status": result["status"],
                      "simulated_time_s": result["time_s"], "steps": result["steps"],
                      "runtime_s": result["runtime_seconds"], "max_re": result["max_reynolds"],
                      "minimum_gap_m": result["minimum_gap_m"]}, indent=2))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
