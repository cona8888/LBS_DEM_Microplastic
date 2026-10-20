"""Deterministic release bounds for a frozen weighted sample pool.

Never assume independent runtime censoring. Unrun, failed and insufficiently
observed weight contributes to the upper bound. These are finite-pool bounds;
sampling uncertainty for the underlying synthetic population is separate.
"""
import math


def release_bounds(planned, observed, horizon_pv):
    if not math.isfinite(horizon_pv) or horizon_pv <= 0:
        raise ValueError("positive finite horizon required")
    identities = [p["id"] for p in planned]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate planned identifier")
    if set(observed)-set(identities):
        raise ValueError("observation not in plan")
    total = sum(p["weight"] for p in planned)
    if any(not math.isfinite(p["weight"]) or p["weight"] <= 0 for p in planned) or abs(total-1)>1e-12:
        raise ValueError("positive weights must sum to one")
    mass = {"released":0.,"observed_no_release":0.,"unrun":0.,"unresolved":0.}
    for p in planned:
        row = observed.get(p["id"])
        if row is None:
            mass["unrun"] += p["weight"]
            continue
        t = row["observed_pv"]
        if not math.isfinite(t) or t < 0:
            raise ValueError("invalid observation time")
        if not row["health_passed"]:
            state = "unresolved"
        elif row["status"] == "full_window_exit":
            state = "released" if t <= horizon_pv else "observed_no_release"
        elif row["status"] in {"present_at_horizon","incomplete_budget"} and t >= horizon_pv:
            state = "observed_no_release"
        else:
            state = "unresolved"
        mass[state] += p["weight"]
    return {"horizon_pv":horizon_pv,"release_lower_bound":mass["released"],
            "release_upper_bound":min(1.,mass["released"]+mass["unrun"]+mass["unresolved"]),
            "weight_accounting":mass,
            "point_estimate_identified":mass["unrun"]+mass["unresolved"] <= 1e-14}
