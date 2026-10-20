"""Independent replay of the dt-only onset selector; no integration or solve.

This supplements, and never replaces, the original per-record physical audit.
The complete old-state journal is checked against the original assembly,
immutable field and geometry. Only an authenticated uncommitted budget trial
may leave one journal entry without an accepted row.
"""
from pathlib import Path
import copy
import hashlib
import numpy as np

import contact_onset_timecap_v1 as selector
import reconstruct_fixed_pose_v3 as reconstruction

api = reconstruction.s.api
SELF = Path(__file__).resolve()
FROZEN_POLICY = dict(schema='paper1.approaching-contact-timecap.v1', subdivision=16,
                     lookahead_base_steps=4., minimum_closing_over_U=.005)


def _require(value, message):
    api.require(value, 'Independent onset timestep audit: ' + message)


def _plain_near(near):
    return [[int(c[0]), float(c[1]), np.asarray(c[2], float).tolist(),
             np.asarray(c[3], float).tolist()] for c in near]


def _decision(base, full, near, q, a, speed, enabled, policy):
    """Recompute the frozen inequality without calling the production selector."""
    _require(np.isfinite([base, full, a, speed]).all()
             and 0 < base <= full and min(a, speed) > 0,
             'finite original positive numerical and physical scales')
    velocity = np.asarray(q, float)
    _require(velocity.shape == (6,) and np.isfinite(velocity).all(),
             'finite six-component old generalized velocity')
    triggers = []
    if enabled:
        for grain, gap, normal, lever in near:
            normal = np.asarray(normal, float)
            lever = np.asarray(lever, float)
            _require(normal.shape == lever.shape == (3,)
                     and np.isfinite(np.r_[gap, normal, lever]).all(),
                     'finite reconstructed near-contact geometry')
            closing = -float(normal @ velocity[:3]
                             + np.cross(lever, normal) @ velocity[3:] / a)
            if (closing > policy['minimum_closing_over_U'] * speed
                    and gap <= policy['lookahead_base_steps'] * closing * full):
                triggers.append(int(grain))
    chosen = min(base, full / policy['subdivision']) if triggers else base
    _require(np.isfinite(chosen) and 0 < chosen <= base,
             'selector only tightens original timestep caps')
    return chosen, triggers


def audit(record, before_checkpoint, case, config, ctx):
    """Verify a raw ``onset_timecap`` journal using only saved old states.

    ``config`` must explicitly contain ``enabled`` and the frozen ``policy``.
    ``ctx`` is the original Paper1 transport context. Its original physics and
    guard audits must still run independently of this supplementary check.
    """
    _require(isinstance(config, dict) and type(config.get('enabled')) is bool
             and api.digest(config.get('policy')) == api.digest(FROZEN_POLICY)
             and api.digest(selector.POLICY) == api.digest(FROZEN_POLICY),
             'explicit frozen policy and Boolean mode')
    enabled, policy = config['enabled'], config['policy']
    spec = case['spec']
    _require(record['spec'] == spec, 'exact resolved case specification')
    _require(record['input_checkpoint_sha256'] == api.digest(before_checkpoint),
             'exact complete input checkpoint binding')
    if before_checkpoint is not None:
        _require(before_checkpoint['state_sha256'] == api.digest(before_checkpoint['state']),
                 'complete input physical state hash')
    evidence = record['onset_timecap']
    _require(type(evidence['enabled']) is bool and evidence['enabled'] == enabled
             and api.digest(evidence['policy']) == api.digest(policy),
             'raw mode and policy agree with frozen case')
    _require(evidence['source_sha256'] == api.sha(selector.__file__),
             'actual selector source bytes')
    expected_proof = dict(
        only_change='One extra dt=min-cap assignment after all original caps, before pending restoration',
        original_source_digest=hashlib.sha256(reconstruction.modal.GENERATED_SOURCE.encode()).hexdigest(),
        ast_after_removing_cap_identical=True, policy=FROZEN_POLICY)
    _require(evidence['source_ast_proof'] == expected_proof,
             'declared dt-only source transformation')
    journal = evidence['journal']
    rows = record['rows']
    _require(isinstance(journal, list) and isinstance(rows, list)
             and len(rows) <= len(journal) <= len(rows) + 1,
             'one journal entry per accepted trial, at most one pending trial')
    result = record['result']
    checkpoint = result['checkpoint']
    state = checkpoint['state']
    _require(checkpoint['state_sha256'] == api.digest(state),
             'complete output state hash')
    pending = state.get('pending_trial')
    _require((pending is not None) == (len(journal) == len(rows) + 1),
             'extra journal witness if and only if an uncommitted trial is saved')
    if before_checkpoint is None:
        initial = spec['initial_state']
        old = dict(t=0., steps=0, x=copy.deepcopy(initial['position_m']),
                   p=copy.deepcopy(initial['orientation']),
                   q=copy.deepcopy(initial['velocity_generalized']))
        inherited_pending = None
    else:
        old = copy.deepcopy(before_checkpoint['state'])
        inherited_pending = old.get('pending_trial')
    if inherited_pending is not None:
        _require(inherited_pending['attempt'] == 0
                 and inherited_pending['time_s'] == old['t'],
                 'original inherited uncommitted trial contract')
    cfg = spec['config']
    a, b, _ = cfg['prolate_semiaxes_m']
    n = cfg['numerics']
    speed = cfg['target_mean_interstitial_velocity_m_s']
    geometry = ctx.geometry_for(case)
    enriched = reconstruction.ASSEMBLE.__globals__['enrich']
    triggered = tightened = 0
    start = old['t']
    with ctx.job.prior.snapshot.scope(api, spec['field_metadata']):
        field, _, metadata = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
        _require(metadata == spec['field_metadata'], 'immutable original field metadata')
        for index, entry in enumerate(journal):
            t, steps = old['t'], old['steps']
            x, p, q = [np.asarray(old[k], float) for k in ('x', 'p', 'q')]
            _require(entry['time_s'] == t and entry['steps'] == steps
                     and entry['velocity_generalized'] == q.tolist(),
                     'journal time, cumulative steps and exact old velocity')
            operands = reconstruction.ASSEMBLE(
                field, geometry, x, p, q, a, b, cfg['dynamic_viscosity_Pa_s'],
                cfg['particle_density_kg_m3'], cfg['fluid_density_kg_m3'],
                cfg['gravity_m_s2'], cfg['friction_coefficient'], np.inf, t,
                cfg['added_mass_fraction'], .2, .01, n['displacement_fraction'],
                n['angle_limit_rad'], n['relaxation_fraction'], n['max_dt_s'],
                n['reynolds_limit'])
            full = float(operands[8])
            base = min(full, spec['horizon_s'] - t)
            near = enriched(geometry, geometry.contacts(
                x, p, a, b, .2 * float(geometry.r.max())))
            witness = _plain_near(near)
            _require(entry['untruncated_dt_s'] == full
                     and entry['base_dt_s'] == base and entry['near'] == witness,
                     'original untruncated/horizon caps and complete near geometry')
            selected, triggers = _decision(base, full, witness, q, a, speed, enabled, policy)
            _require(entry['selected_dt_s'] == selected
                     and entry['trigger_grain_ids'] == triggers,
                     'exact independently reconstructed cap and trigger list')
            triggered += bool(triggers)
            tightened += selected < base
            if index == 0 and inherited_pending is not None:
                _require(inherited_pending['dt_s'] == selected,
                         'inherited pending timestep is identical to this policy')
            if index < len(rows):
                row = rows[index]
                proof = record['sweep_certificates'][index]
                _require(proof['dt_s'] == selected,
                         'actual original solver/sweep trial uses selected timestep')
                accepted = row['dt_s']
                _require(0 < accepted <= selected and t + accepted == row['time_s'],
                         'exact accepted clock and positive trial prefix')
                _require(accepted == selected or (index == len(rows) - 1
                         and result['status'] == 'full_window_exit'),
                         'only original terminal export may truncate a trial')
                old.update(t=row['time_s'], steps=steps + 1,
                           x=copy.deepcopy(row['position_m']),
                           p=copy.deepcopy(row['orientation']),
                           q=copy.deepcopy(row['velocity_generalized']))
            else:
                _require(pending is not None and result['status'] == 'incomplete_budget'
                         and pending['attempt'] == 0 and pending['time_s'] == t
                         and pending['dt_s'] == selected,
                         'sole unmatched witness is the exact saved budget trial')
    _require(all(state[key] == old[key] for key in ('t', 'steps', 'x', 'p', 'q')),
             'journal/rows end at the complete output physical state')
    _require(result['time_s'] == state['t'] and result['steps'] == state['steps'],
             'result and checkpoint clock/step identity')
    return dict(passed=True, accepted_rows=len(rows), journal_entries=len(journal),
                pending_witnesses=int(pending is not None), trigger_count=triggered,
                tightened_steps=tightened, start_s=start, stop_s=state['t'],
                original_caps_never_increased=True, independent_geometry_and_policy_replayed=True,
                replaces_original_physics_audit=False, native_solver_calls=0,
                new_saved_steps=0)
