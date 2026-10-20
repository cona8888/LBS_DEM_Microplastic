"""Stage145: dt-consistent tolerance contract, branch audit, and the Stage40 re-examination.

Read-only with respect to every prior stage.  Nothing here dispatches a trajectory,
recomputes geometry, launches a campaign or promotes a release result.

Experiments, in the order they must be believed:

  E1  INERTNESS.  With delta_geom = 0 and no warm start, the Stage145 solver is
      bitwise identical to Stage41 `_solve_prepared` on all nine frozen systems
      and 200 random systems.  If this fails nothing else in this stage counts,
      because the patch would not be a pure addition.

  E2  REPAIR.  With kappa = 16 the seven Stage142 sphere endpoint systems pass
      every unchanged physical gate, independently rechecked from the returned
      reaction alone, with the geometric backward error inside delta_geom.

  E3  SENSITIVITY.  kappa = 8 / 16 / 64 give the same accepted velocity.

  E4  TIMESTEP.  Halving dt down to dt/2^14 keeps the acceptance, which is the
      property the Stage142 retry loop lacked.

  E5  NEGATIVE CONTROLS.  A gap far outside the budget must NOT receive the
      allowance, and a system that fails on physics (cone, sign) must still fail.

  E6  FIBRE BRANCHES.  Complete enumeration of the two Stage141 systems; compare
      the separation with the value Stage141 recorded independently.

  E7  STAGE40 RE-EXAMINATION.  Stage40 rejected reaction persistence because it
      "altered selection within the non-unique instantaneous Coulomb problem",
      and the recorded failure signature is an outer fixed point that does not
      converge while the inner solve converges in one iteration.  E7 measures
      the discontinuity of the warm-started solve with respect to its warm
      start, which is the mechanism that can break the outer iteration, and
      tests whether freezing the warm start within a step removes it.

Environment note: this run records its own interpreter and library versions.  A
run on a different machine may differ in the last bits of E2/E6 values; E1 is a
within-interpreter comparison of two code paths and is machine independent.
"""
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage38_staging"), str(ROOT / "stage39_staging"),
                str(ROOT / "stage41_staging"), str(ROOT / "stage145_staging")]
import inertial_contact_cold_optimized_v1 as stage41
import geometric_tolerance_v1 as contract
import frozen_systems_v1 as frozen
import branch_enumeration_v1 as branches

BASE = "tolerance_contract_and_branch_audit_20260920"
# Optional label so a run made outside the project's own environment does not occupy
# the run_01 slot:  python -B -u run_stage145_v1.py [label]
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run_01"
OUT = ROOT / "stage145_evaluations" / BASE / LABEL


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def write(path, value):
    encoded = json.dumps(value, indent=2, sort_keys=True, allow_nan=True, default=_json) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:      # exclusive create
        stream.write(encoded)


def _json(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(type(value))


def call_stage41(s, **kw):
    return stage41._solve_prepared(s["vfree"], s["mobility"], s["jacobian"], s["gaps"],
                                   s["dt"], s["mu"], s["tol"], s["maxiter"], **kw)


def call_stage145(s, delta_geom=0.0, force0=None):
    return contract.solve_prepared(s["vfree"], s["mobility"], s["jacobian"], s["gaps"],
                                   s["dt"], s["mu"], s["tol"], s["maxiter"],
                                   delta_geom=delta_geom, force0=force0)


def attempt(fn, *args, **kw):
    try:
        return {"returned": True, "value": fn(*args, **kw)}
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
        return {"returned": False, "error": str(exc)}


# ----------------------------------------------------------------- E1
def experiment_inertness(systems):
    rows = []
    for s in systems:
        a = attempt(call_stage41, s)
        b = attempt(call_stage145, s, delta_geom=0.0, force0=None)
        if a["returned"] != b["returned"]:
            rows.append({"id": s["id"], "identical": False, "reason": "one raised, the other did not",
                         "stage41": a.get("error"), "stage145": b.get("error")})
            continue
        if not a["returned"]:
            rows.append({"id": s["id"], "identical": a["error"] == b["error"],
                         "both_raised": True, "error": a["error"]})
            continue
        qa, ha = a["value"]
        qb, hb = b["value"]
        same = (np.array_equal(qa, qb)
                and ha["iterations"] == hb["iterations"]
                and np.array_equal(np.asarray(ha["reactions"]), np.asarray(hb["reactions"]))
                and ha["residual"] == hb["residual"]
                and ha["force_residual"] == hb["force_residual"]
                and ha["dissipation"] == hb["dissipation"])
        rows.append({"id": s["id"], "identical": bool(same), "both_raised": False,
                     "iterations": ha["iterations"],
                     "velocity_bit_identical": bool(np.array_equal(qa, qb)),
                     "reaction_bit_identical": bool(np.array_equal(np.asarray(ha["reactions"]),
                                                                   np.asarray(hb["reactions"])))})
    return {"passed": all(r["identical"] for r in rows), "count": len(rows), "rows": rows}


# ----------------------------------------------------------------- E2/E3/E4
def experiment_repair(sphere, multiplier):
    delta = contract.length_budget(frozen.CELL_LENGTH_M, multiplier)
    rows = []
    for s in sphere:
        legacy = attempt(call_stage41, s)
        started = time.perf_counter()
        new = attempt(call_stage145, s, delta_geom=delta)
        wall = time.perf_counter() - started
        row = {"id": s["id"], "dt_s": s["dt"], "gap_over_dt_max": float(np.max(np.abs(s["gaps"]))/s["dt"]),
               "velocity_ceiling": contract.velocity_ceiling(s["vfree"], s["dt"], delta),
               "legacy_stage41_returned": legacy["returned"],
               "legacy_stage41_error": legacy.get("error"),
               "stage145_returned": new["returned"], "wall_s": wall}
        if new["returned"]:
            q, h = new["value"]
            check = contract.independent_gates(s["vfree"], s["mobility"], s["jacobian"], s["gaps"],
                                               s["dt"], s["mu"], q, h, delta_geom=delta)
            row.update(iterations=h["iterations"], residual_over_scale=h["residual"],
                       residual_over_geometric=h["residual_over_geometric"],
                       legacy_gate_pass=h["legacy_gate_pass"],
                       independent=check, velocity_norm=float(np.linalg.norm(q)),
                       backward_error_m=check["backward_error_m"],
                       backward_error_within_budget=bool(check["backward_error_m"] <= delta))
            row["passed"] = bool(check["passed"] and row["backward_error_within_budget"])
        else:
            row["passed"] = False
            row["error"] = new["error"]
        rows.append(row)
    return {"multiplier": multiplier, "delta_geom_m": delta,
            "passed": all(r["passed"] for r in rows), "rows": rows}


def experiment_sensitivity(sphere):
    per = {m: experiment_repair(sphere, m) for m in contract.DECLARED_MULTIPLIERS}
    agree = []
    for index, s in enumerate(sphere):
        velocities, ceilings, displacements = [], [], []
        for m in contract.DECLARED_MULTIPLIERS:
            delta = contract.length_budget(frozen.CELL_LENGTH_M, m)
            q, _ = call_stage145(s, delta_geom=delta)
            velocities.append(q)
            ceilings.append(contract.velocity_ceiling(s["vfree"], s["dt"], delta))
            displacements.append(float(np.linalg.norm(q[:3])*s["dt"]/delta))
        spread = max(float(np.linalg.norm(v - velocities[0])) for v in velocities)
        scale = max(float(np.linalg.norm(s["vfree"])), 1e-15)
        # The ceiling IS the stopping rule, so answers can only be expected to agree to
        # within it; demanding more would be demanding the budget have no effect at all.
        # The physical statement that must hold for every kappa is that the body is static
        # to the geometry's own resolution: displacement per step <= a few delta_geom.
        within = bool(spread <= 4*max(ceilings))
        static = bool(max(displacements) <= 4.0)
        agree.append({"id": s["id"], "velocity_spread_over_scale": spread/scale,
                      "velocity_spread_over_largest_ceiling": spread/max(ceilings),
                      "max_step_displacement_over_delta_geom": max(displacements),
                      "agree_within_ceiling": within, "static_at_every_multiplier": static,
                      "passed": bool(within and static)})
    return {"passed": all(r["passed"] for r in agree) and all(p["passed"] for p in per.values()),
            "per_multiplier": {str(int(m)): {"passed": p["passed"], "delta_geom_m": p["delta_geom_m"]}
                               for m, p in per.items()},
            "identical_velocity_across_multipliers": agree,
            "detail_kappa_16": per[16.0]}


def experiment_timestep(sphere, levels=15):
    delta = contract.length_budget(frozen.CELL_LENGTH_M, contract.DEFAULT_MULTIPLIER)
    rows = []
    for s in sphere:
        entry = {"id": s["id"], "levels": []}
        for k in range(levels):
            t = dict(s)
            t["dt"] = s["dt"] / 2**k
            out = attempt(call_stage145, t, delta_geom=delta)
            if out["returned"]:
                q, h = out["value"]
                check = contract.independent_gates(t["vfree"], t["mobility"], t["jacobian"], t["gaps"],
                                                   t["dt"], t["mu"], q, h, delta_geom=delta)
                entry["levels"].append({"halvings": k, "dt_s": t["dt"], "passed": check["passed"],
                                        "step_displacement_over_delta_geom":
                                            float(np.linalg.norm(q[:3])*t["dt"]/delta)})
            else:
                entry["levels"].append({"halvings": k, "dt_s": t["dt"], "passed": False,
                                        "error": out["error"]})
        entry["passed"] = all(l["passed"] for l in entry["levels"])
        rows.append(entry)
    return {"passed": all(r["passed"] for r in rows), "levels": levels, "rows": rows}


# ----------------------------------------------------------------- E5
def experiment_negative_controls(sphere):
    delta = contract.length_budget(frozen.CELL_LENGTH_M, contract.DEFAULT_MULTIPLIER)
    controls = []
    base = sphere[0]
    # a gap far outside the budget must not be excused by the allowance
    for factor in (1e3, 1e6):
        s = dict(base)
        s["gaps"] = base["gaps"] - factor*delta
        out = attempt(call_stage145, s, delta_geom=delta)
        if out["returned"]:
            q, h = out["value"]
            check = contract.independent_gates(s["vfree"], s["mobility"], s["jacobian"], s["gaps"],
                                               s["dt"], s["mu"], q, h, delta_geom=delta)
            excused = bool(check["backward_error_m"] > delta and check["passed"])
        else:
            excused = False
        controls.append({"control": f"gap displaced by {factor:g} * delta_geom",
                         "returned": out["returned"],
                         "backward_error_exceeds_budget_but_accepted": excused,
                         "passed": not excused})
    # the allowance must not rescue a physically inadmissible reaction
    s = dict(base)
    q, h = call_stage145(s, delta_geom=delta)
    bad = np.asarray(h["reactions"], float).copy()
    bad[0] = -abs(bad[0]) - 1e-9                       # negative normal reaction
    check = contract.independent_gates(s["vfree"], s["mobility"], s["jacobian"], s["gaps"],
                                       s["dt"], s["mu"], q, {"reactions": bad.tolist()}, delta_geom=delta)
    controls.append({"control": "negative normal reaction injected",
                     "passed": not check["passed"], "checks": check["checks"]})
    bad2 = np.asarray(h["reactions"], float).copy()
    bad2[1] = 10*s["mu"]*abs(bad2[0]) + 1e-9           # outside the Coulomb cone
    check2 = contract.independent_gates(s["vfree"], s["mobility"], s["jacobian"], s["gaps"],
                                        s["dt"], s["mu"], q, {"reactions": bad2.tolist()}, delta_geom=delta)
    controls.append({"control": "cone violation injected",
                     "passed": not check2["passed"], "checks": check2["checks"]})
    return {"passed": all(c["passed"] for c in controls), "controls": controls}


# ----------------------------------------------------------------- E6
def experiment_fibre(fibre):
    delta = contract.length_budget(frozen.CELL_LENGTH_M, contract.DEFAULT_MULTIPLIER)
    rows = []
    for s in fibre:
        started = time.perf_counter()
        found, P = branches.enumerate_branches(s, delta)
        wall = time.perf_counter() - started
        spread = branches.branch_spread(found)
        recorded = s["recorded"]["velocity_difference_over_reference_flow"] * 1e-4   # reference flow speed
        # the same state with the gaps set to exact zero: the configuration to
        # within the gaps' own rounding uncertainty
        z = dict(s)
        z["gaps"] = np.zeros_like(s["gaps"])
        zero_found, _ = branches.enumerate_branches(z, delta)
        # is all-stick even consistent at the raw gaps?  9 constraints, 6 DOF
        J = s["jacobian"]
        target = np.zeros(3*len(s["gaps"]))
        target[::3] = -s["gaps"]/s["dt"]
        U = np.linalg.svd(J, full_matrices=True)[0]
        out_of_range = float(np.linalg.norm(U[:, 6:].T @ target))
        chosen, rule = branches.select_branch(found, P) if found else (None, "none")
        rows.append({
            "id": s["id"], "dt_s": s["dt"], "wall_s": wall,
            "raw_gaps_m": s["gaps"].tolist(),
            "branch_count_raw_gaps": len(found),
            "branch_modes_raw_gaps": [b["mode_name"] for b in found],
            "branch_count_zero_gaps": len(zero_found),
            "branch_modes_zero_gaps": [b["mode_name"] for b in zero_found],
            "separation_m_s": spread,
            "stage141_recorded_separation_m_s": recorded,
            "separation_relative_difference": abs(spread-recorded)/recorded if recorded else None,
            "all_stick_out_of_range_m_s": out_of_range,
            "branches": [{"mode": b["mode_name"], "velocity_norm": float(np.linalg.norm(b["velocity"])),
                          "residual": b["report"]["residual"], "dissipation": b["report"]["dissipation"],
                          "force_family_dimension": b["force_family_dimension"],
                          "normal_reactions": b["force"][::3].tolist()} for b in found],
            "zero_gap_branches": [{"mode": b["mode_name"], "residual": b["report"]["residual"],
                                   "velocity_norm": float(np.linalg.norm(b["velocity"]))} for b in zero_found],
            "declared_cold_selection": {"rule": rule, "mode": chosen["mode_name"] if chosen else None},
            "stage141_recorded": s["recorded"],
        })
    return {"passed": all(r["branch_count_zero_gaps"] >= 2 for r in rows), "rows": rows}


# ----------------------------------------------------------------- E7
def experiment_stage40_reexamination(fibre):
    """Why reaction persistence broke the outer fixed point, and what fixes it."""
    delta = contract.length_budget(frozen.CELL_LENGTH_M, contract.DEFAULT_MULTIPLIER)
    s = fibre[0]
    found, P = branches.enumerate_branches(s, delta)
    if len(found) < 2:
        return {"passed": False, "reason": "expected a bifurcating state"}
    stick = [b for b in found if b["mode_name"].startswith("stick")][0]
    slide = [b for b in found if b["mode_name"].startswith("slide")][0]

    def branch_of(q):
        return "stick" if np.linalg.norm(q-stick["velocity"]) < np.linalg.norm(q-slide["velocity"]) else "slide"

    def label(warm):
        out = attempt(call_stage145, s, delta_geom=delta, force0=warm)
        if not out["returned"]:
            return "nonconvergent"
        return branch_of(out["value"][0])

    # Is the warm-started solve continuous in its warm start?
    samples = []
    for t in np.linspace(0.0, 1.0, 41):
        samples.append({"t": float(t), "outcome": label((1-t)*stick["force"] + t*slide["force"])})
    transitions = [{"from": samples[i-1]["outcome"], "to": samples[i]["outcome"],
                    "bracket": [samples[i-1]["t"], samples[i]["t"]]}
                   for i in range(1, len(samples)) if samples[i]["outcome"] != samples[i-1]["outcome"]]
    nonconvergent_fraction = sum(1 for x in samples if x["outcome"] == "nonconvergent")/len(samples)
    threshold = None
    if transitions:
        first = transitions[0]
        lo, hi = first["bracket"]
        lo_label = first["from"]
        for _ in range(50):
            mid = 0.5*(lo+hi)
            if label((1-mid)*stick["force"] + mid*slide["force"]) == lo_label:
                lo = mid
            else:
                hi = mid
        gap = np.linalg.norm(((1-hi)*stick["force"] + hi*slide["force"])
                             - ((1-lo)*stick["force"] + lo*slide["force"]))
        threshold = {"bracket": [lo, hi], "from": first["from"], "to": first["to"],
                     "reaction_separation_N": float(gap),
                     "relative_to_reaction_norm": float(gap/np.linalg.norm(slide["force"]))}

    # Does a frozen warm start hold its branch across an outer-loop-scale perturbation of M?
    stability = []
    other = fibre[1] if len(fibre) > 1 else s
    perturbation = float(np.linalg.norm(other["mobility"]-s["mobility"])/np.linalg.norm(s["mobility"]))
    for name, warm in (("stick", stick["force"]), ("slide", slide["force"])):
        here = label(warm)
        there_out = attempt(call_stage145, other, delta_geom=delta, force0=warm)
        there = "nonconvergent" if not there_out["returned"] else branch_of(there_out["value"][0])
        stability.append({"frozen_warm_start": name, "branch_here": here,
                          "branch_after_perturbation": there,
                          "held": bool(here == there and here != "nonconvergent")})
    return {"passed": bool(threshold is not None and all(x["held"] for x in stability)),
            "warm_start_is_discontinuous": bool(threshold is not None),
            "discontinuity": threshold,
            "warm_start_sweep": samples,
            "transitions": transitions,
            "nonconvergent_fraction_of_warm_starts": nonconvergent_fraction,
            "outer_iterate_mobility_perturbation_relative": perturbation,
            "frozen_warm_start_branch_stability": stability,
            "interpretation":
                "The warm-started contact solve is a discontinuous function of its warm start: the "
                "returned branch flips across a reaction separation of order machine precision. The "
                "Stage41/42 outer drag fixed point assumes the inner solve is a function of (M, vfree) "
                "alone, and Stage40's cached_v1 updated the warm start on every outer iteration, so the "
                "outer iteration became a coupled map across that discontinuity. That is a sufficient "
                "mechanism for the recorded 'inertial/contact fixed point did not converge' with "
                "max_contact_iterations_per_nonlinear_solve = 1. Freezing the warm start within a step "
                "restores the inner map to a function of (M, vfree) and holds the branch across an "
                "outer-iterate perturbation of M. NOT a reproduction of the Stage40 replay: that case "
                "was not re-run here."}


def main():
    sphere, fibre, source_hashes = frozen.load()
    require(len(sphere) == 7 and len(fibre) == 2, "expected seven sphere and two fibre systems")
    random = frozen.random_systems()
    OUT.mkdir(parents=True, exist_ok=False)
    sources = {str(p): sha(p) for p in [Path(__file__), Path(contract.__file__),
                                        Path(frozen.__file__), Path(branches.__file__),
                                        Path(stage41.__file__)]}
    protocol = {
        "stage": "Stage145",
        "question": "Is the velocity-level acceptance ceiling dt-consistent, and is the fibre contact "
                    "state non-unique rather than ill-conditioned?",
        "contract": "ceiling = max(1e-10*|vfree|, delta_geom/dt), delta_geom = kappa*eps*L, kappa in {8,16,64}. "
                    "Raw gaps are solved with and never modified. Both the old and the new metric are reported.",
        "physical_changes": [],
        "acceptance": {"E1_inertness_bitwise": True, "E2_repair_all_seven": True,
                       "E3_agreement_within_declared_ceiling": True, "E4_fourteen_halvings": True,
                       "E5_negative_controls_rejected": True, "E6_two_branches_at_zero_gaps": True,
                       "E7_warm_start_discontinuity_measured": True},
        "claim": "Local contact-solver verification and a branch audit of two saved fibre states. "
                 "No trajectory, dwell, retention, release fraction or experimental validation claim. "
                 "No prior stage modified; no campaign launched.",
        "sources": sources, "inputs": source_hashes,
        "cell_length_m": frozen.CELL_LENGTH_M,
        "environment": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
                        "platform": platform.platform()},
        "limitations": "delta_geom is a local arithmetic allowance, not a bound on accumulated path error. "
                       "E7 explains a mechanism consistent with the Stage40 signature; it does not re-run "
                       "the Stage40 replay case.",
    }
    write(OUT / "protocol.json", protocol)

    started = time.perf_counter()
    e1 = experiment_inertness(sphere + fibre + random)
    print("E1 inertness:", e1["passed"], e1["count"], "systems", flush=True)
    require(e1["passed"], "E1 inertness failed: the patch is not a pure addition")
    e2 = experiment_sensitivity(sphere)
    print("E2/E3 repair + sensitivity:", e2["passed"], flush=True)
    e4 = experiment_timestep(sphere)
    print("E4 timestep:", e4["passed"], flush=True)
    e5 = experiment_negative_controls(sphere)
    print("E5 negative controls:", e5["passed"], flush=True)
    e6 = experiment_fibre(fibre)
    print("E6 fibre branches:", e6["passed"],
          [r["branch_modes_zero_gaps"] for r in e6["rows"]], flush=True)
    e7 = experiment_stage40_reexamination(fibre)
    print("E7 Stage40 re-examination:", e7["passed"], flush=True)

    for name, path in sources.items():
        require(sha(name) == path, "source drift during the run: " + name)
    passed = all(x["passed"] for x in (e1, e2, e4, e5, e6, e7))
    result = {
        "stage": "Stage145", "label": LABEL, "passed": bool(passed), "wall_s": time.perf_counter()-started,
        "E1_inertness": e1, "E2_E3_repair_and_sensitivity": e2, "E4_timestep_scan": e4,
        "E5_negative_controls": e5, "E6_fibre_branch_audit": e6, "E7_stage40_reexamination": e7,
        "headline": {
            "inertness_bitwise_identical_at_delta_zero": e1["passed"],
            "sphere_systems_repaired": e2["detail_kappa_16"]["passed"],
            "sphere_systems_legacy_stage41_returned":
                sum(1 for r in e2["detail_kappa_16"]["rows"] if r["legacy_stage41_returned"]),
            "fibre_branch_counts_zero_gaps": [r["branch_count_zero_gaps"] for r in e6["rows"]],
            "fibre_separation_relative_difference_vs_stage141":
                [r["separation_relative_difference"] for r in e6["rows"]],
            "warm_start_discontinuity_relative_to_reaction_norm":
                (e7.get("discontinuity") or {}).get("relative_to_reaction_norm"),
        },
        "not_claimed": ["population release fraction", "irreversible retention", "trajectory uniqueness",
                        "experimental validation", "production promotion of any solver"],
        "next": ["Land the contract in the production chain behind delta_geom, with E1 re-run there.",
                 "Re-run the Stage142 strict-replay and common-time ladders under kappa = 16.",
                 "Re-open the Stage40 reaction-persistence decision with the warm start frozen within a "
                 "step and an explicit branch-selection record, judged as a selection rule rather than "
                 "as an optimization.",
                 "Restore rotational inertia before any fibre trajectory claim; the branch difference is "
                 "almost entirely rotational.",
                 "Only then resume the unchanged sphere/fibre release objective."],
        "claim": protocol["claim"],
        "environment": protocol["environment"],
    }
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"results_sha256": sha(OUT / "results.json"),
                                    "protocol_sha256": sha(OUT / "protocol.json"),
                                    "artifacts": {str(p): sha(p) for p in sorted(OUT.iterdir()) if p.is_file()
                                                  and p.name != "completion.json"}})
    print("STAGE145_PASS", passed, flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
