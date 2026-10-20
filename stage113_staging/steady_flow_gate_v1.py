"""Fail-closed steady-field gate for future flow runs, not legacy promotion."""
from __future__ import annotations

import math


def check_steady_flow(regular, adjacent, *, export_exact, fatal_health_code,
                      relative_tolerance=5e-5, balance_tolerance=.005):
    """Require long-window stability plus eight genuinely consecutive states.

    Each row is measured from copied populations, not cached convergence flags.
    `field_change_relative_l2` compares to the preceding sampled field; the
    first adjacent row is deliberately excluded from one-step comparisons.
    """
    def bounded(row, key, limit):
        value = row.get(key)
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and 0 <= value <= limit)

    def magnitude(value, centre=0.):
        return abs(value-centre) if isinstance(value,(int,float)) and not isinstance(value,bool) else math.inf

    regular_steps = [r.get("step") for r in regular]
    adjacent_steps = [r.get("step") for r in adjacent]
    valid_steps = all(isinstance(s, int) and not isinstance(s, bool) for s in regular_steps + adjacent_steps)
    consecutive = valid_steps and len(adjacent) >= 8 and all(b-a == 1 for a,b in zip(adjacent_steps, adjacent_steps[1:]))
    # Both parities in spaced diagnostics prevents the former all-even gate.
    regular_order = valid_steps and len(regular) >= 4 and all(b>a for a,b in zip(regular_steps, regular_steps[1:]))
    checks = {
        "spaced_samples_include_both_parities": bool(regular_order and {x % 2 for x in regular_steps[-4:]} == {0, 1}),
        "eight_consecutive_samples": bool(consecutive),
        "long_window_field_stable": bool(len(regular) >= 4 and all(bounded(r,"field_change_relative_l2",relative_tolerance) for r in regular[-4:])),
        "adjacent_field_stable": bool(consecutive and all(bounded(r,"field_change_relative_l2",relative_tolerance) for r in adjacent[1:])),
        "adjacent_mean_stable": bool(consecutive and all(bounded({"x": magnitude(r.get("delta_mean_relative"))},"x",relative_tolerance) for r in adjacent[1:])),
        "steady_force_balance": bool(consecutive and all(bounded(r,"steady_force_balance_relative",balance_tolerance) for r in adjacent)),
        "dynamic_momentum_balance": bool(consecutive and all(bounded(r,"dynamic_momentum_residual_relative",balance_tolerance) for r in adjacent)),
        "density_drift": bool(consecutive and all(bounded({"x":magnitude(r.get("mean_density"),1)},"x",5e-6) for r in adjacent)),
        "mach": bool(consecutive and all(bounded(r,"maximum_speed_lu",.05/math.sqrt(3)) for r in adjacent)),
        "export_exact": export_exact is True,
        "health": type(fatal_health_code) is int and fatal_health_code == 0 and all(type(r.get("fatal_health_code")) is int and r["fatal_health_code"] == 0 for r in regular + adjacent),
    }
    return {"passed": all(checks.values()), "checks": checks}
