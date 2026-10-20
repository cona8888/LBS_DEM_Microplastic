"""Hash-bound read-only adapter for the qualified Stage130 CPD6 field."""
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage131_staging"), str(ROOT / "stage39_staging")]
import refine_cpd4_timesteps_v1 as lineage
import wall_field_v1

api = lineage.api
GEOMETRY = ROOT / "stage125_designs/third_grid_cost_20260916/geometry_cpd6.npz"
FIELD = ROOT / "stage130_runs/cpd6_final_stationarity_20260916/gpu_confirmation_01/stage130_cpd6_final_stationarity/final_fields.npz"
EVALUATION = ROOT / "stage130_evaluations/cpd6_final_stationarity_20260916/independent_evaluation_01/results.json"
COMPLETION = ROOT / "stage130_evaluations/cpd6_final_stationarity_20260916/completion.json"
CPD4_GEOMETRY = ROOT / "stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/s31b_n216_s2_clean/geometry_cpd4.npz"


def load():
    result = api.read(EVALUATION)
    seal = api.read(COMPLETION)
    api.require(result["qualified"] is True and result["status"] == "stationary_mean_matched_cpd6_qualified", "CPD6 field not qualified")
    api.require(seal["qualified"] is True, "CPD6 completion seal not qualified")
    with np.load(GEOMETRY) as geom, np.load(FIELD) as flow:
        geometry = {key: geom[key].copy() for key in geom.files}
        api.require(np.array_equal(flow["phase"], geometry["phase"]), "CPD6 phase drift")
        fluid = (flow["phase"] == 0).transpose(2, 1, 0)
        velocity = flow["velocity_xyz_lu"].astype(np.float64).transpose(0, 3, 2, 1)
    dx = float(geometry["spacing_m"][0])
    nu_si = 0.001002 / 998.2
    speed_unit = nu_si / (0.1 * dx)
    velocity *= speed_unit
    achieved = float(velocity[0, fluid].mean())
    api.require(np.isfinite(velocity).all() and np.all(velocity[:, ~fluid] == 0), "invalid CPD6 velocity")
    api.require(abs(achieved / result["mean_interstitial_velocity_m_s"] - 1.0) < 2e-6, "CPD6 SI reconstruction drift")
    field = wall_field_v1.WallCellField(velocity, dx, fluid)
    length = float(geometry["cell_length_m"][0])
    metadata = {
        "case_id": "s2_f1p0_cpd6", "cpd": 6,
        "achieved_mean_interstitial_velocity_m_s": achieved,
        "target_mean_interstitial_velocity_m_s": result["target_mean_velocity_m_s"],
        "speed_unit_m_s": speed_unit, "cell_length_m": length,
        "two_pore_volume_horizon_s": 2 * length / achieved,
        "pv_per_second": achieved / length,
        "geometry": {"path": str(GEOMETRY), "sha256": api.sha(GEOMETRY)},
        "field": {"path": str(FIELD), "sha256": api.sha(FIELD)},
        "evaluation": {"path": str(EVALUATION), "sha256": api.sha(EVALUATION)},
        "completion": {"path": str(COMPLETION), "sha256": api.sha(COMPLETION)},
        "loader": {"path": str(Path(__file__).resolve()), "sha256": api.sha(Path(__file__).resolve())},
        "interpolator": {"path": str(Path(wall_field_v1.__file__).resolve()), "sha256": api.sha(wall_field_v1.__file__)},
        "normalization_to_target_applied": False,
        "particle_transport_authorized": False,
        "limitation": "Read-only adapter qualification; transport requires a separate frozen design."
    }
    return field, geometry, metadata


def preflight():
    out = ROOT / "stage132_evaluations/cpd6_particle_field_adapter_20260916/preflight_01"
    field, geometry, metadata = load()
    with np.load(CPD4_GEOMETRY) as g4:
        same_particles = np.array_equal(geometry["sand_centres_m"], g4["sand_centres_m"]) and np.array_equal(geometry["sand_radii_m"], g4["sand_radii_m"])
        same_cell = float(geometry["cell_length_m"][0]) == float(g4["cell_length_m"][0])
    probes = []
    length = metadata["cell_length_m"]
    for position in ([0.1*length,0.2*length,0.3*length], [0.9*length,0.8*length,0.7*length], [1.1*length,-0.2*length,0.3*length]):
        velocity, gradient = field.sample(position)
        probes.append({"position_m": list(position), "velocity_m_s": velocity.tolist(), "gradient_s_inv": gradient.tolist(),
                       "finite": bool(np.isfinite(velocity).all() and np.isfinite(gradient).all())})
    checks = {"qualified_source": True, "shape": list(field.u.shape) == [3,279,279,279],
              "same_physical_particles": bool(same_particles), "same_periodic_cell": bool(same_cell),
              "finite_periodic_probes": all(x["finite"] for x in probes),
              "mean_match": abs(metadata["achieved_mean_interstitial_velocity_m_s"] / metadata["target_mean_interstitial_velocity_m_s"] - 1) <= 5e-4,
              "no_transport": metadata["particle_transport_authorized"] is False}
    result = {"passed": all(checks.values()), "status": "cpd6_particle_field_adapter_preflight_passed" if all(checks.values()) else "cpd6_particle_field_adapter_preflight_failed",
              "checks": checks, "metadata": metadata, "probes": probes,
              "claim": "Loader and identical-particle geometry compatibility only; no particle trajectory executed."}
    out.mkdir(parents=True, exist_ok=False)
    api.write(out / "results.json", result)
    api.write(out / "completion.json", {"passed": result["passed"], "results_sha256": api.sha(out / "results.json"),
                                         "adapter_sha256": api.sha(Path(__file__).resolve())})
    print(result["status"], checks)
    return 0 if result["passed"] else 4


if __name__ == "__main__":
    raise SystemExit(preflight())
