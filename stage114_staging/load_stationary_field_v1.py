"""Read-only SI loader for evaluated stationary fields; no transport dispatch.

Uses viscosity/spacing conversion, never normalizes the flow to a target.
Unsolved packing/speed combinations fail closed instead of scaling an archive.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

import requalify_stationary_flows_v1 as run

sys.path.insert(0, str(run.ROOT / "stage39_staging"))
import wall_field_v1

EVALUATION = run.ROOT / "stage114_evaluations" / run.STUDY / "independent_evaluation_01/results.json"


def load(seed, flow_factor=1.0, cpd=2, *, evaluation_path=EVALUATION):
    run.require(run.audit.sha(wall_field_v1.__file__) == "85e08f99dfd49e1a53edac222d252ba776d954451af24e2ff9525c52df57b1ca",
                "Stage108-bound wall interpolation changed")
    seed, flow_factor, cpd = int(seed), float(flow_factor), int(cpd)
    allowed = {(2,.5,2), (2,1.,2), (2,2.,2), (1,1.,2), (3,1.,2), (2,1.,4)}
    run.require((seed,flow_factor,cpd) in allowed, "packing/flow/resolution not directly solved and requalified")
    evaluation_path = Path(evaluation_path)
    results = run.audit.read(evaluation_path)
    completion = run.audit.read(evaluation_path.parent / "completion.json")
    run.require(completion["passed"] is True and completion["results_sha256"] == run.audit.sha(evaluation_path), "unbound/failed field evaluation")
    run.require(results["passed"] is True and results["status"] == "stationary_fields_requalified_transport_resolution_required", "field qualification absent")
    run.verify_bindings(results["bindings"])
    design = run.audit.read(run.DESIGN)
    run.require(results["bindings"]["design"]["sha256"] == run.audit.sha(run.DESIGN), "different field design")
    matches = [c for c in results["cases"] if (c["packing_seed"],c["flow_factor"],c["cpd"]) == (seed,flow_factor,cpd)]
    run.require(len(matches) == 1 and matches[0]["passed"] is True, "nonunique/unqualified field")
    result = matches[0]
    run.verify_bindings(result["bundle"])
    spec = next(c for c in design["cases"] + [design["reused_reference"]] if c["case_id"] == result["case_id"])
    run.verify_bindings(spec["geometry"])
    with np.load(spec["geometry"]["path"]) as g, np.load(result["bundle"]["final_fields.npz"]["path"]) as f:
        geometry = {k:g[k].copy() for k in g.files}
        run.require(np.array_equal(f["phase"],g["phase"]), "phase drift")
        fluid = (f["phase"] == 0).transpose(2,1,0)
        velocity = f["velocity_xyz_lu"].astype(np.float64).transpose(0,3,2,1)
    dx = float(geometry["spacing_m"][0])
    nu_si = design["physical_fluid"]["dynamic_viscosity_Pa_s"] / design["physical_fluid"]["density_kg_m3"]
    speed_unit = nu_si / (design["controls"]["nu_lu"] * dx)
    velocity *= speed_unit
    achieved = float(velocity[0,fluid].mean())
    run.require(np.isfinite(velocity).all() and np.all(velocity[:,~fluid] == 0), "invalid flow array")
    run.require(abs(achieved/result["mean_interstitial_velocity_m_s"]-1) < 2e-6, "SI reconstruction drift")
    field = wall_field_v1.WallCellField(velocity, dx, fluid)
    length = float(geometry["cell_length_m"][0])
    metadata = {"case_id":result["case_id"], "nominal_flow_factor":flow_factor,
                "nominal_mean_interstitial_velocity_m_s":1e-4*flow_factor,
                "achieved_mean_interstitial_velocity_m_s":achieved,
                "speed_unit_m_s":speed_unit,"cell_length_m":length,
                "two_pore_volume_horizon_s":2*length/achieved,
                "pv_per_second":achieved/length,
                "normalization_to_target_applied":False,
                "evaluation":run.bind(evaluation_path), "field":result["bundle"]["final_fields.npz"],
                "geometry":spec["geometry"], "loader":run.bind(__file__), "interpolator":run.bind(wall_field_v1.__file__),
                "particle_transport_authorized":False,
                "limitation":"Load-only adapter. Dynamic contact/outlet, near-wall, temporal and transport-resolution verification remain separate."}
    return field, geometry, metadata
