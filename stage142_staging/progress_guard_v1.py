"""Dispatch-only affordability guard; never mutates solver state or physics."""
import math


def assess(start_s, end_s, horizon_s, nominal_dt_s, status):
    values = (start_s, end_s, horizon_s, nominal_dt_s)
    if not all(math.isfinite(x) for x in values) or nominal_dt_s <= 0 or end_s < start_s or start_s > horizon_s:
        raise ValueError('invalid progress record')
    if status != 'incomplete_budget':
        return {'continue': False, 'reason': 'terminal_or_checkpoint_status', 'advance_s': end_s-start_s}
    # After one fully consumed segment budget, less than 1% of one currently
    # admissible step is not enough to authorize another identical segment.
    # This is a compute policy, not a physical trapping or convergence test.
    threshold = .01*min(nominal_dt_s, horizon_s-start_s)
    useful = end_s-start_s >= threshold and end_s > start_s and end_s < horizon_s
    return {'continue': useful, 'reason': 'useful_progress' if useful else 'stop_no_useful_progress',
            'advance_s': end_s-start_s, 'minimum_useful_advance_s': threshold}
