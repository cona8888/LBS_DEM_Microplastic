"""Inactive, pure pre-event timestep-cap HYPOTHESIS; no physical admission.

Only original near-contact operands and caller-frozen numerical scales are
used. No force/geometry/model call, gap projection, state update, installation
or accuracy-test override occurs. The caller MUST run its unchanged actual
coarse/two-half, physical, restart and full-path gates. Scalar gap/(U*h) is
not a bound on six-dimensional velocity error.
"""
from types import MappingProxyType
import hashlib
import json
import math


POLICY = MappingProxyType(dict(schema='paper1.finite-precontact-cap.v1',
    precontact_fraction=0.5, release_proxy_fraction=0.5,
    minimum_closing_over_U=0.005,
    release_cap_basis='current_monotone_selected_cap',
    maximum_passes='len(original_near_contacts)+1',
    gap_operands='literal_original_no_projection_or_zeroing',
    below_minimum_or_unrepresentable='fail_closed_never_clip_up',
    accuracy_admission='unchanged_actual_caller_gates_only'))
POLICY_SHA256 = hashlib.sha256(json.dumps(dict(POLICY), sort_keys=True,
    separators=(',', ':')).encode()).hexdigest()


class EventCapError(ValueError):
    def __init__(self, reason, witness=None):
        super().__init__('Precontact cap hypothesis: ' + reason)
        self.witness = witness


def _require(condition, reason, witness=None):
    if not condition:
        raise EventCapError(reason, witness)


def _scalar(value, name, *, positive=False):
    _require(type(value) in (int, float) and math.isfinite(value),
             'finite original scalar ' + name)
    result = float(value)
    _require(not positive or result > 0., 'positive original scalar ' + name)
    return result


def _vector(value, length, name):
    _require(isinstance(value, (tuple, list)) and len(value) == length,
             'literal original ' + name + ' dimension')
    return tuple(_scalar(item, name) for item in value)


def _clock(time_s, h, minimum_h_s, witness):
    _require(minimum_h_s <= h, 'candidate below unchanged minimum; no upward clipping', witness)
    midpoint, end = time_s + h / 2., time_s + h
    _require(math.isfinite(midpoint) and math.isfinite(end) and time_s < midpoint < end,
             'literal midpoint/end unrepresentable; no clock rewriting', witness)
    return dict(origin_time_s=time_s, midpoint_time_s=midpoint, end_time_s=end,
        first_interval_s=midpoint-time_s, second_interval_s=end-midpoint,
        no_time_alignment_or_interpolation=True)


def select(original_cap_s, near, q, a, U, velocity_epsilon, minimum_h_s, time_s=0.):
    """Return ``(h, witness)``; the result only tightens the caller's old cap.

    A contact arms when raw g>0, closing>.005U, tau=g/closing<current cap,
    and g/(U*current cap)>epsilon/2. Its fixed candidate is tau/2. Releases
    are recomputed after any other contact reduces the cap; there are at most
    N strict reductions because every candidate belongs to an original
    contact and never changes inside this pure call. Across successive physical
    states, no finite-progress or multidimensional accuracy bound is claimed.
    """
    H = _scalar(original_cap_s, 'original_cap_s', positive=True)
    a = _scalar(a, 'length_scale_m', positive=True)
    U = _scalar(U, 'speed_m_s', positive=True)
    epsilon = _scalar(velocity_epsilon, 'unchanged_velocity_epsilon', positive=True)
    minimum = _scalar(minimum_h_s, 'unchanged_minimum_h_s', positive=True)
    t = _scalar(time_s, 'time_s')
    velocity = _vector(q, 6, 'generalized_velocity')
    _require(isinstance(near, (tuple, list)), 'explicit original near-contact inventory')
    contacts, ids = [], set()
    for value in near:
        _require(isinstance(value, (tuple, list)) and len(value) >= 4,
                 'complete original contact operands')
        gid, gap, normal, lever = value[:4]
        _require(type(gid) is int and gid not in ids, 'unique original integer grain identity')
        ids.add(gid)
        g = _scalar(gap, 'raw_gap_m')
        n, lever = _vector(normal, 3, 'normal'), _vector(lever, 3, 'lever')
        cross = (lever[1]*n[2]-lever[2]*n[1], lever[2]*n[0]-lever[0]*n[2],
                 lever[0]*n[1]-lever[1]*n[0])
        closing = -(sum(n[i]*velocity[i] for i in range(3))
                    + sum(cross[i]*velocity[3+i] for i in range(3))/a)
        _require(math.isfinite(closing), 'finite original closing arithmetic')
        tau = g/closing if g > 0. and closing > 0. else None
        _require(tau is None or math.isfinite(tau) and tau > 0.,
                 'positive finite forecast from unchanged operands')
        contacts.append(dict(grain_id=gid, raw_gap_m=g, normal=n, lever_m=lever,
            normal_not_renormalized=True, closing_m_s=closing, forecast_tau_s=tau))
    witness = dict(schema='paper1.finite-precontact-cap.witness.v1', policy=dict(POLICY),
        policy_sha256=POLICY_SHA256, original_cap_s=H, velocity_generalized=velocity,
        length_scale_m=a, speed_m_s=U, unchanged_velocity_epsilon=epsilon,
        unchanged_minimum_h_s=minimum, original_time_s=t, passes=[],
        original_gap_operands_unchanged=True, scalar_proxy_is_not_sixD_error_bound=True,
        actual_accuracy_override=False, numerical_or_physical_qualification=False,
        numerical_launch_ready=False)
    cap = H
    for index in range(len(contacts)+1):
        scale = U*cap
        _require(math.isfinite(scale) and scale > 0., 'finite nonunderflowing U*cap', witness)
        observations, candidates = [], []
        for original in contacts:
            item = dict(original)
            g, closing, tau = item['raw_gap_m'], item['closing_m_s'], item['forecast_tau_s']
            proxy = g/scale
            _require(math.isfinite(proxy), 'finite unchanged gap/(U*cap)', witness)
            item.update(release_proxy=proxy, release_threshold=POLICY['release_proxy_fraction']*epsilon)
            if g <= 0.:
                item['action'] = 'nonpositive_raw_gap_original_cap'
            elif closing <= POLICY['minimum_closing_over_U']*U:
                item['action'] = 'below_closing_floor_original_cap'
            elif tau >= cap:
                item['action'] = 'event_outside_current_cap'
            elif proxy <= POLICY['release_proxy_fraction']*epsilon:
                item['action'] = 'released_for_current_cap'
            else:
                candidate = POLICY['precontact_fraction']*tau
                item.update(action='precontact_cap_candidate', candidate_s=candidate)
                candidates.append(candidate)
            observations.append(item)
        selected = min([cap]+candidates)
        witness['passes'].append(dict(index=index, input_cap_s=cap,
            contact_witnesses=observations, output_cap_s=selected))
        _require(0. < selected <= cap <= H, 'strictly positive tightening only', witness)
        if selected == cap:
            witness.update(selected_cap_s=cap, strict_reductions=index,
                literal_clock=_clock(t, cap, minimum, witness), selector_completed=True)
            return cap, witness
        _require(selected >= minimum, 'candidate below unchanged minimum; no upward clipping', witness)
        cap = selected
    raise EventCapError('finite monotone contact pass bound exceeded', witness)
