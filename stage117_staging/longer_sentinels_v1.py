"""Prospective 0.5-s paired sentinels; unchanged physics, bounded restart chain."""
from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage116_staging"), str(ROOT / "stage115_staging")]
import refine_short_velocity_v1 as ancestor
import evaluate_corrected_diagnostics_v1 as reference
import evaluate_short_matrix_v1 as contracts
api = ancestor.api
candidate = ancestor.parent.opt.candidate
DESIGN = ROOT / "stage117_designs/longer_paired_sentinels_20260915/design_01.json"
RUN = ROOT / "stage117_runs/longer_paired_sentinels_20260915/diagnostic_01"
EVAL = ROOT / "stage117_evaluations/longer_paired_sentinels_20260915"
SEAL = ROOT / "stage116_evaluations/fibre_cost_attribution_20260915/completion.json"
PREFLIGHT = EVAL / "preflight_01/results.json"


def prepare():
    api.require(not DESIGN.exists(), "immutable design exists")
    ancestor.verify(api.read(ancestor.DESIGN))
    api.verify_mapping(api.read(SEAL)["artifacts"])
    prior = api.read(api.DESIGN)
    cases = []
    groups = []
    for seed, cpd in [(1, 2), (2, 2), (2, 4)]:
        for shape in api.SHAPES:
            levels = [.5, .25, .125] if seed == 2 and shape == api.SHAPES[1] else [1., .5, .25]
            names = []
            for level in levels:
                template = next(s for s in prior["cases"] if s["seed"] == seed and s["cpd"] == cpd and s["shape"] == shape and s["flow_factor"] == 1. and s["refinement"] == 1.)
                spec = copy.deepcopy(template)
                spec["refinement"] = level
                spec["case_id"] = api.case_id(seed, 1., cpd, shape, level) + "_h0p5"
                for key in api.DT_CONTROLS:
                    spec["config"]["numerics"][key] *= level
                spec["horizon_s"] = .5
                spec["horizon_pv"] = .5 * spec["field_metadata"]["pv_per_second"]
                cases.append(spec)
                names.append(spec["case_id"])
            groups.append({"seed": seed, "cpd": cpd, "shape": shape, "case_ids": names})
    sources = {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values())
               if getattr(m, "__file__", None) and Path(m.__file__).suffix == ".py" and ROOT in Path(m.__file__).resolve().parents}
    sources.update({str(p.resolve()): api.sha(p) for p in Path(__file__).parent.glob("*.py")})
    d = {"stage": "Stage117", "question": "Do the previously passing timestep triplets remain accurate and affordable through a doubled contact-rich observation window?",
         "cases": cases, "groups": groups, "acceptance": prior["acceptance"],
         "event_acceptance": {"same_dwell_observation": True, "first_dwell_time_difference_max_s": .0025, "finest_max_accepted_interval_s": .0025},
         "budget": {"segment_integrator_s": 45., "max_fibre_segments": 3, "max_sphere_segments": 1, "stage_wall_s": 2100., "fresh_process_per_segment": True, "further_automatic_refinement": False},
         "telemetry": "Read-only observer of every accepted TrapMonitor interval, preserving its full state and law. Save endpoint pose, velocity, supported contacts and finite-dwell event. Event helper remains the previously tested constant-motion helper, not a global nonmonotone crossing certificate.",
         "physical_changes": [], "query_s": .5,
         "checkpoint_policy": "All cases start fresh. Same horizon and binding across at most three 45-s segments. No migration of old-horizon checkpoints. Budget-incomplete is unresolved, never retained or exited.",
         "claim_boundary": "Local single-sentinel numerical and measured-cost evidence. No 2-PV cost extrapolation, population release, empirical validation or new physics. CPD comparison retains each achieved SI speed.",
         "source_hashes": sources, "input_hashes": {str(SEAL): api.sha(SEAL), str(ancestor.DESIGN): api.sha(ancestor.DESIGN)},
         "authority": {"bounded_longer_diagnostic": True, "population_campaign": False, "new_physics": False}}
    d["binding"] = api.digest(d)
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    api.write(DESIGN, d)
    print("FROZEN", api.sha(DESIGN), "cases", len(cases), flush=True)


def verify(d):
    api.require(d["binding"] == api.digest({k: v for k, v in d.items() if k != "binding"}), "design binding drift")
    api.verify_mapping(d["source_hashes"])
    api.verify_mapping(d["input_hashes"])
    api.verify_mapping(api.read(SEAL)["artifacts"])
    ancestor.verify(api.read(ancestor.DESIGN))
    old = api.read(api.DESIGN)
    api.require(len(d["cases"]) == 18 and len({s["case_id"] for s in d["cases"]}) == 18, "case set drift")
    api.require([n for g in d["groups"] for n in g["case_ids"]] == [s["case_id"] for s in d["cases"]], "order drift")
    for spec in d["cases"]:
        base = copy.deepcopy(next(s for s in old["cases"] if s["seed"] == spec["seed"] and s["cpd"] == spec["cpd"] and s["shape"] == spec["shape"] and s["flow_factor"] == 1. and s["refinement"] == 1.))
        base.update(case_id=spec["case_id"], refinement=spec["refinement"], horizon_s=.5, horizon_pv=.5 * base["field_metadata"]["pv_per_second"])
        for key in api.DT_CONTROLS:
            base["config"]["numerics"][key] *= spec["refinement"]
        api.require(base == spec, "unexpected physical/config change")


def binding(d, name):
    return api.digest([d["binding"], name])


def execute(spec, bound, checkpoint=None, pause=None, observe=True):
    """An observational subclass adds no checkpoint state and changes no decisions."""
    core = api.frozen.core
    original_monitor = core.trap_event_v2.TrapMonitor
    original_sweep = candidate.legacy.swept_gap
    rows = []
    start = spec["initial_state"] if checkpoint is None else checkpoint["state"]
    state = {"t": 0. if checkpoint is None else start["t"],
             "x": copy.deepcopy(start["position_m"] if checkpoint is None else start["x"]),
             "p": copy.deepcopy(start["orientation"] if checkpoint is None else start["p"])}
    a = spec["config"]["prolate_semiaxes_m"][0]

    class ObservedMonitor(original_monitor):
        def update(self, dt, position, generalized_velocity, contact_ids, load_bearing_contact_ids):
            result = super().update(dt, position, generalized_velocity, contact_ids, load_bearing_contact_ids)
            x, p = core.mechanics.advance_pose(state["x"], state["p"], generalized_velocity, a, dt)
            api.require(api.np.allclose(x, position, rtol=0, atol=1e-14), "observer pose mismatch")
            state.update(t=state["t"] + dt, x=x, p=p)
            rows.append(api.normalized({"time_s": state["t"], "dt_s": dt, "position_m": position,
                "orientation": p, "velocity_generalized": generalized_velocity, "active_contact_ids": contact_ids,
                "supported_bearing_ids": load_bearing_contact_ids, "dwell": result}))
            return result

    try:
        candidate.legacy.swept_gap = candidate.swept_gap
        if observe:
            core.trap_event_v2.TrapMonitor = ObservedMonitor
        result = api.normalized(api.execute(spec, bound, 45., checkpoint=checkpoint, pause=pause))
    finally:
        candidate.legacy.swept_gap = original_sweep
        core.trap_event_v2.TrapMonitor = original_monitor
    if observe and rows:
        api.require(abs(rows[-1]["time_s"] - result["time_s"]) < 1e-12, "observer clock mismatch")
        api.require(api.np.allclose(rows[-1]["orientation"], result["orientation"], rtol=0, atol=1e-12), "observer axis mismatch")
    return result, rows


def worker(name, segment):
    d = api.read(DESIGN)
    verify(d)
    spec = next(s for s in d["cases"] if s["case_id"] == name)
    limit = d["budget"]["max_sphere_segments" if spec["shape"] == api.SHAPES[0] else "max_fibre_segments"]
    api.require(1 <= segment <= limit, "segment outside frozen budget")
    case_root = RUN / name
    out = case_root / f"segment_{segment:02d}"
    api.require(not out.exists(), "immutable segment exists")
    checkpoint = None
    prior = None
    if segment > 1:
        prior_path = case_root / f"segment_{segment-1:02d}/record.json"
        prior = api.sha(prior_path)
        previous = api.read(prior_path)
        api.require(api.read(prior_path.parent / "completion.json")["record_sha256"] == prior, "previous record drift")
        api.require(previous["case_id"] == name and previous["design_sha256"] == api.sha(DESIGN) and previous["result"]["status"] == "incomplete_budget", "invalid continuation")
        checkpoint = previous["result"]["checkpoint"]
        api.require(checkpoint["contract"] == contracts.expected_contract(spec, binding(d, name)) and checkpoint["state_sha256"] == api.digest(checkpoint["state"]), "checkpoint drift")
    out.mkdir(parents=True)
    api.write(out / "launch.json", {"case_id": name, "segment": segment, "pid": os.getpid(), "command": sys.argv,
        "design_sha256": api.sha(DESIGN), "prior_record_sha256": prior, "python": sys.version})
    try:
        result, rows = execute(spec, binding(d, name), checkpoint=checkpoint)
        health = api.health(result, spec)
        api.write(out / "accepted_intervals.json", rows, raw=True)
        record = {"case_id": name, "segment": segment, "design_sha256": api.sha(DESIGN), "prior_record_sha256": prior,
                  "checkpoint_input_sha256": None if checkpoint is None else api.digest(checkpoint), "result": result, "health": health,
                  "accepted_intervals_sha256": api.sha(out / "accepted_intervals.json"), "pruning_work": candidate.stats()}
        api.write(out / "record.json", record, raw=True)
        api.write(out / "completion.json", {"record_sha256": api.sha(out / "record.json"), "launch_sha256": api.sha(out / "launch.json"), "status": result["status"]})
        okay = health["passed"] and result["status"] in ["incomplete_budget", "present_at_horizon", "full_window_exit"]
        if not okay:
            api.write(out / "failure.json", {"status": result["status"], "reason": result["reason"], "health": health})
        print(name, segment, result["status"], result["time_s"], result["runtime_seconds"], flush=True)
        return 0 if okay else 4
    except Exception as exc:
        if not (out / "failure.json").exists():
            api.write(out / "failure.json", {"error": repr(exc), "traceback": traceback.format_exc()})
        raise


def run():
    d = api.read(DESIGN)
    verify(d)
    test = api.read(PREFLIGHT)
    api.require(test["passed"] and test["design_sha256"] == api.sha(DESIGN), "preflight required")
    api.require(not RUN.exists(), "immutable run exists")
    RUN.mkdir(parents=True)
    env = os.environ.copy()
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    started = time.perf_counter()
    records = {}
    order = [s["case_id"] for s in d["cases"]]
    api.write(RUN / "manifest.json", {"design_sha256": api.sha(DESIGN), "preflight_sha256": api.sha(PREFLIGHT), "case_order": order,
              "pid": os.getpid(), "command": sys.argv, "python": sys.version, "thread_environment": {k: env[k] for k in ["OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"]}})
    try:
        for spec in d["cases"]:
            name = spec["case_id"]
            records[name] = []
            cap = d["budget"]["max_sphere_segments" if spec["shape"] == api.SHAPES[0] else "max_fibre_segments"]
            for segment in range(1, cap + 1):
                api.require(time.perf_counter() - started + 50 < d["budget"]["stage_wall_s"], "stage dispatch budget exhausted")
                stem = f"{name}_seg{segment:02d}"
                with (RUN / (stem + ".stdout.txt")).open("x") as out, (RUN / (stem + ".stderr.txt")).open("x") as err:
                    child = subprocess.run([sys.executable, "-B", "-u", __file__, "worker", "--case", name, "--segment", str(segment)], env=env, stdout=out, stderr=err)
                path = RUN / name / f"segment_{segment:02d}/record.json"
                if path.exists():
                    records[name].append({"path": str(path), "sha256": api.sha(path)})
                api.require(child.returncode == 0, "failed worker: " + stem)
                r = api.read(path)["result"]
                print(stem, r["status"], "t", round(r["time_s"], 7), "wall", round(r["runtime_seconds"], 2), flush=True)
                if r["status"] != "incomplete_budget":
                    break
        verify(d)
        api.write(RUN / "completion.json", {"status": "bounded_matrix_executed_pending_evaluation", "design_sha256": api.sha(DESIGN),
                  "manifest_sha256": api.sha(RUN / "manifest.json"), "records": records, "wall_s": time.perf_counter() - started})
    except Exception as exc:
        api.write(RUN / "failure.json", {"error": repr(exc), "traceback": traceback.format_exc(), "records": records})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run", "worker"])
    parser.add_argument("--case")
    parser.add_argument("--segment", type=int)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "run":
        run()
    else:
        raise SystemExit(worker(args.case, args.segment))
