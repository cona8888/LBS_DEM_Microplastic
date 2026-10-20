"""Lightweight argument-level regression; does not execute DEM transport."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np

import comparison_case_core_v1 as adapter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stage109_evaluations/flow_adapter_regression_20260914"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


class Capture:
    @staticmethod
    def integrate(*args, **kwargs):
        return args, kwargs


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    config, state = adapter.resolve(2, 0, "rigid_prolate_ar4", 1.0)
    sphere_config, sphere_state = adapter.resolve(1, 77, "equal_volume_sphere", 2.0)
    a, b, _ = config["prolate_semiaxes_m"]
    radius = sphere_config["prolate_semiaxes_m"][0]
    equal_volume = abs(radius**3 - a*b*b) <= 1e-20
    paired_initial_velocity = (state["velocity_generalized"] ==
                               sphere_state["velocity_generalized"] == [0.0] * 6)
    field_cache = {}
    geometry = object()
    calls = []

    def fake_load(seed, target_velocity=1e-4):
        calls.append((seed, target_velocity))
        key = (seed, target_velocity)
        if key not in field_cache:
            class Field:
                pass
            field = Field()
            field.u = np.zeros((3, 1, 1, 1))
            field.u[0, 0, 0, 0] = target_velocity
            field.fluid = np.ones((1, 1, 1), dtype=bool)
            field_cache[key] = field
        return field_cache[key], geometry, 0.004680605809919908, 1e-5, ()

    with patch.object(adapter.h.matrix_case_v1, "load", side_effect=fake_load), \
            patch.object(adapter.h.geometry_exact_v1.GrainGeometry,
                         "from_geometry", return_value=geometry):
        original = adapter.h.run_local(Capture, config, state, 2, 0.01, 1.0)
        reference = adapter.run_local(Capture, config, state, 2, 0.01, 1.0)
        high = adapter.run_local(Capture, sphere_config, sphere_state, 1, 0.01, 1.0)
    checks = {
        "reference_integrator_arguments_unchanged": original == reference,
        "reference_load_requested_u0": calls[:2] == [(2, 1e-4), (2, 1e-4)],
        "high_flow_load_requested_2u0": calls[2] == (1, 2e-4),
        "high_flow_integrator_received_target_trap_speed": high[1]["trap_reference_speed"] == 2e-4,
        "equal_particle_volume": equal_volume,
        "zero_initial_generalized_velocity": paired_initial_velocity,
        "different_shape_semiaxes": high[0][5] == radius and high[0][6] == radius,
    }
    if not all(checks.values()):
        raise RuntimeError(f"flow adapter regression failed: {checks}")
    result = {
        "status": "argument_regression_passed_no_transport_run",
        "checks": checks,
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                          str(Path(adapter.__file__).resolve()): sha(adapter.__file__),
                          str(Path(adapter.h.__file__).resolve()): sha(adapter.h.__file__)},
        "input_hashes": {str(adapter.PROTOCOL): sha(adapter.PROTOCOL),
                         str(adapter.PROTOCOL.with_name("completion.json")):
                             sha(adapter.PROTOCOL.with_name("completion.json"))},
        "claim_boundary": "Argument-level regression and flow-selection check only; no physical flow-linearity, dynamics, numerical convergence or campaign-cost result.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"status": result["status"],
                                    "results_sha256": sha(OUT / "results.json")})
    print(json.dumps({"status": result["status"], "checks": checks}))


if __name__ == "__main__":
    main()
