"""Freeze a shape-by-flow comparison design without launching transport jobs."""
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
POP = ROOT / "stage95_designs/common_admissible_population_01"
OBS = ROOT / "stage108_runs/first_iid_fibre_2pv_01"
OUT = ROOT / "stage109_designs/shape_flow_protocol_20260914"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def verify_population():
    result = load(POP / "results.json")
    completion = load(POP / "completion.json")
    if not result["passed"] or completion["status"] != "complete_passed":
        raise RuntimeError("population prerequisite failed")
    if completion["results_sha256"] != sha(POP / "results.json"):
        raise RuntimeError("population result hash drift")
    for section in ("source_hashes", "input_hashes", "artifact_hashes"):
        for path, digest in result[section].items():
            if sha(path) != digest:
                raise RuntimeError(f"population lineage drift: {path}")
    return result


def verify_stage108():
    manifest = load(OBS / "manifest.json")
    if manifest["horizon_pv"] != 2.0 or manifest["wall_budget_s"] != 300.0:
        raise RuntimeError("Stage108 horizon or budget drift")
    for section in ("source_hashes", "input_hashes"):
        for path, digest in manifest[section].items():
            if sha(path) != digest:
                raise RuntimeError(f"Stage108 lineage drift: {path}")
    binding = hashlib.sha256(json.dumps(
        [manifest["source_hashes"], manifest["input_hashes"]],
        sort_keys=True).encode()).hexdigest()
    if manifest["binding"] != binding:
        raise RuntimeError("Stage108 binding drift")
    segments = sorted(OBS.glob("segment_[0-9][0-9][0-9][0-9]"))
    if len(segments) != 42:
        raise RuntimeError("Stage108 segment count drift")
    previous_time = 0.0
    previous_hash = None
    runtime = 0.0
    for index, segment in enumerate(segments, 1):
        if segment.name != f"segment_{index:04d}":
            raise RuntimeError("Stage108 segment-order drift")
        result = load(segment / "result.json")
        completion = load(segment / "completion.json")
        launch = load(segment / "launch.json")
        if (completion["result_sha256"] != sha(segment / "result.json")
                or completion["manifest_sha256"] != sha(OBS / "manifest.json")
                or launch["manifest_sha256"] != completion["manifest_sha256"]
                or launch["prior_result_sha256"] != previous_hash
                or launch["start_time_s"] != previous_time
                or completion["start_time_s"] != previous_time
                or completion["status"] != result["status"]
                or completion["time_s"] != result["time_s"]
                or not completion["numerical_health_passed"]):
            raise RuntimeError(f"Stage108 segment {index} chain/health drift")
        if result["time_s"] <= previous_time or list(segment.glob("*failure*")):
            raise RuntimeError(f"Stage108 segment {index} time/failure drift")
        if index < 42:
            checkpoint = result["checkpoint"]
            if result["status"] != "incomplete_budget" or not completion["checkpoint_verified"]:
                raise RuntimeError(f"Stage108 segment {index} not resumable")
            digest = hashlib.sha256(json.dumps(checkpoint["state"],
                sort_keys=True, allow_nan=True).encode()).hexdigest()
            if digest != checkpoint["state_sha256"]:
                raise RuntimeError(f"Stage108 segment {index} checkpoint drift")
        previous_time = result["time_s"]
        previous_hash = sha(segment / "result.json")
        runtime += completion["runtime_s"]
    terminal = load(segments[-1] / "result.json")
    if (terminal["status"] != "present_at_horizon"
            or terminal["time_s"] != manifest["horizon_s"]
            or terminal["checkpoint"] is not None):
        raise RuntimeError("Stage108 terminal outcome drift")
    return {"segments": 42, "status": terminal["status"],
            "observed_pv": 2.0, "cumulative_runtime_s": runtime,
            "fibre_exit_observed": False}


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    population = verify_population()
    observation = verify_stage108()
    pilot, heldout, sentinel = {}, {}, {"1": 77, "2": 0, "3": 154}
    starts = {}
    for seed in (1, 2, 3):
        rows = load(POP / f"starts_s{seed}.json")
        if len(rows) != 256 or [row["id"] for row in rows] != list(range(256)):
            raise RuntimeError(f"packing {seed} population count/order drift")
        starts[str(seed)] = sha(POP / f"starts_s{seed}.json")
        eligible = np.arange(1 if seed == 2 else 0, 256)
        order = np.random.Generator(np.random.PCG64(109001 + seed)).permutation(eligible)
        pilot[str(seed)] = sorted(map(int, order[:10]))
        heldout[str(seed)] = sorted(map(int, order[10:20]))
        if seed != 2 and int(order[20]) != sentinel[str(seed)]:
            raise RuntimeError("sentinel selection drift")
        if set(pilot[str(seed)]) & set(heldout[str(seed)]):
            raise RuntimeError("pilot/held-out overlap")
        if sentinel[str(seed)] in pilot[str(seed)] + heldout[str(seed)]:
            raise RuntimeError("sentinel/pilot overlap")
    lengths = {str(row["packing_seed"]): row["cell_length_m"]
               for row in population["packings"]}
    u0 = 1e-4
    common_time = 40.0
    if any(common_time >= 2*length/(2*u0) for length in lengths.values()):
        raise RuntimeError("common-time query exceeds high-flow 2-PV horizon")
    protocol = {
        "status": "design_frozen_pending_stage_b_admissibility_and_cost",
        "research_question": "How do flow, shape, and their interaction affect whole-body downstream export from a common-admissible synthetic resident population?",
        "claim_domain": "Dilute independent particles, saturated fixed sand, prescribed steady one-way flow, rigid equal-volume sphere versus AR4 prolate; periodic transverse and continued axial geometry.",
        "shapes": ["equal_volume_sphere", "rigid_prolate_ar4"],
        "prolate_semiaxes_m": [2e-4, 5e-5, 5e-5],
        "equal_volume_sphere_radius_m": (2e-4*(5e-5)**2)**(1/3),
        "particle_density_kg_m3": 1380.0,
        "initial_generalized_velocity": "zero for both shapes",
        "flow": {"quantity": "mean_interstitial_velocity_m_s", "reference_u0_m_s": u0,
                 "candidate_factors": [0.5, 1.0, 2.0],
                 "field_scaling": "candidate only; verify linear response and domain at every flow before transport comparison"},
        "fluid": {"density_kg_m3": 998.2, "dynamic_viscosity_Pa_s": 0.001002},
        "gravity_m_s2": [0.0, 0.0, -9.80665],
        "friction_coefficient": 0.3,
        "population": {"source": str(POP), "packings": [1, 2, 3],
                       "source_count_per_packing": 256,
                       "source_conditioning": "uniform-centre/isotropic-axis proposals conditioned on both shapes fitting with positive exact grain gap",
                       "pilot_count_per_packing": 10,
                       "pilot_weight_per_placement": 1/30,
                       "selection_rule": "For each packing, PCG64(109001+seed) permutation of sample IDs; exclude previously observed seed2 sample0; first 10 pilot, next 10 held-out, then first unused ID for seed1/3 sentinel.",
                       "pilot_ids": pilot, "heldout_ids": heldout,
                       "stage_b_sentinel_ids": sentinel,
                       "stage_b_sentinel_note": "seed2 sample0 is the known difficult original-IID development case; sentinel results do not enter held-out confirmation"},
        "observation": {"event": "first whole-body downstream crossing of x=L",
                        "denominator": "all selected initial particles; unresolved remain in denominator",
                        "primary_equal_pv_queries": [0.5, 1.0, 2.0],
                        "equal_time_query_s": common_time,
                        "pv_formula": "U_mean*t/L for constant flow",
                        "per_packing_2pv_horizon_s_by_flow_factor": {
                            seed: {str(factor): 2*length/(u0*factor)
                                   for factor in (0.5, 1.0, 2.0)}
                            for seed, length in lengths.items()}},
        "contrasts": {"shape": "R(fibre,U,P)-R(sphere,U,P)",
                      "flow": "R(shape,2U0,P)-R(shape,0.5U0,P)",
                      "interaction": "D_shape(2U0,P)-D_shape(0.5U0,P)",
                      "minimum_effect_absolute_fraction": 0.20,
                      "planning_rationale": "20 percentage points equals six of 30 equally weighted pilot placements; smaller effects require a larger study than this pilot can reliably resolve."},
        "missing_outcomes": {"fraction_bounds": "[E/N,(E+M)/N] at each query; failure and unrun selected cases count in M",
                             "contrast_bounds": "[L_A-U_B,U_A-L_B]",
                             "finite_horizon_present": "observed no export by query, not permanent retention"},
        "pilot_trajectory_count_if_gated": 2*3*10*3,
        "stage_b_gate": {"required": ["one frozen comparison core for both shapes and all flows",
                                      "flow-field scaling and Re/other physical-domain checks",
                                      "both-shape free-fluid, near-wall, throat/contact and outlet-event tests",
                                      "three time resolutions at common queries on a prospective matched subset",
                                      "full cost distribution including difficult fibre trajectories",
                                      "numerical error and unresolved bounds below the asserted contrast"],
                         "campaign_authorized_by_this_protocol": False},
        "heldout_rule": "Keep held-out IDs unexamined until the pilot analysis and confirmatory method are frozen; use new packings if inference requires them.",
        "stage108_feasibility_evidence": observation,
        "input_hashes": {str(POP / name): sha(POP / name)
                         for name in ("protocol.json", "results.json", "completion.json",
                                      "starts_s1.json", "starts_s2.json", "starts_s3.json")}
                        | {str(OBS / name): sha(OBS / name)
                           for name in ("manifest.json", "segment_0042/result.json",
                                        "segment_0042/completion.json")},
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__)},
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "protocol.json", protocol)
    write(OUT / "completion.json", {
        "status": protocol["status"],
        "protocol_sha256": sha(OUT / "protocol.json"),
        "claim_boundary": "Frozen proposed design only; no comparative pilot, validation, or population release fraction executed."})
    print(json.dumps({"output": str(OUT), "status": protocol["status"],
                      "pilot_trajectories_if_gated": protocol["pilot_trajectory_count_if_gated"]}))


if __name__ == "__main__":
    main()
