"""Zero-trajectory-step diagnosis of Stage187's original failed association.

Replay one archived pose through the unchanged contact stack. The innermost
trajectory entry is fenced by an algebra-only callback; no pose is advanced.
Capture successful finalizers, including within-pose reuse, without changing
their inputs or outputs. Never promote the original failed campaign.
"""
from pathlib import Path
from contextlib import contextmanager
import copy
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'stage187_staging'), str(ROOT / 'stage168_staging')]
import integrated_paired_campaign_v1 as job
import diagnose_frozen_contact_v2 as exact_load
import audit_fallback_systems_v1 as independent

api = job.api
REPLAY = exact_load.capture.diag.replay
CASE = 's2_i0_sphere_f0p03125'
BASE = 'inner_outer_association_20260924'
DESIGN = ROOT / 'stage188_designs' / BASE / 'design_01.json'
OUT = ROOT / 'stage188_evaluations' / BASE / 'diagnosis_01'


def load_payload(index):
    raw = job.paths(job.RUN, CASE, index)['raw']
    return job.codec.base.read_record(raw, api.sha(job.DESIGN))['payload']


def prepare():
    job.verify(api.read(job.DESIGN))
    files = [job.DESIGN, job.OUT / 'evaluation_01/results.json',
             job.OUT / 'evaluation_01/completion.json']
    for index in (138, 139):
        paths = job.paths(job.RUN, CASE, index)
        files.extend([paths['raw'], paths['raw'].with_suffix('.seal.json'),
                      paths['ready'], paths['receipt']])
    d = {'stage': 'Stage188 bounded diagnosis',
         'authorization': 'User next after explicit zero-step diagnosis handoff.',
         'question': 'Does within-pose reuse explain the failed early-attempt/accepted-row identity exactly?',
         'case': CASE, 'segment': 138, 'early_attempt_index': 24,
         'accepted_row_index': 2794, 'maximum_pose_calls': 1,
         'maximum_finalizer_calls': 200, 'trajectory_steps_authorized': 0,
         'physics_changes': [], 'acceptance_gate_changes': [],
         'sources': job.parent.source_map(), 'inputs': {str(p): api.sha(p) for p in files},
         'claim': 'Exact local diagnostic only. Stage187 remains failed/incomplete; no release result, repair, restart, or campaign authority.'}
    d['binding'] = api.digest(d)
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    api.write(DESIGN, d)
    print('FROZEN', api.sha(DESIGN), flush=True)


def verify(d):
    api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'diagnostic binding')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    job.verify(api.read(job.DESIGN))


@contextmanager
def capture_finalizers(records, cap):
    hot = job.prior.p.hot
    original = hot.s50._finish
    saved_compiled = hot.PRIMARY.__globals__['_finish']

    def observe(*args, **kwargs):
        api.require(len(records) < cap, 'bounded finalizer count')
        names = ['vfree', 'mobility', 'jacobian', 'force', 'z', 'A', 'gaps_m',
                 'dt_s', 'friction', 'steps', 'iterations', 'solver', 'extra']
        item = {k: copy.deepcopy(v) for k, v in zip(names, args)}
        api.require(not kwargs, 'known positional finalizer interface')
        records.append(item)
        try:
            q, health = original(*args, **kwargs)
        except Exception as error:
            item.update(accepted=False, error=repr(error))
            raise
        else:
            item.update(accepted=True, velocity=q.copy(), health=copy.deepcopy(health))
            return q, health

    hot.s50._finish = observe
    hot.PRIMARY.__globals__['_finish'] = observe
    try:
        yield
    finally:
        hot.s50._finish = original
        hot.PRIMARY.__globals__['_finish'] = saved_compiled


def run():
    d = api.read(DESIGN); verify(d)
    OUT.mkdir(parents=True, exist_ok=False)
    api.write(OUT / 'launch.json', {'design_sha256': api.sha(DESIGN),
              'utc': job.utc().isoformat(), 'trajectory_steps_authorized': 0})
    record = load_payload(138)
    attempt = record['early_attempts'][d['early_attempt_index']]
    row = record['rows'][d['accepted_row_index']]
    prev = record['rows'][d['accepted_row_index'] - 1]
    state = {'x': prev['position_m'], 'p': prev['orientation'],
             'q': prev['velocity_generalized'], 't': prev['time_s'], 'recovery': False}
    spec = record['spec']
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api, spec['field_metadata']):
        field, data, meta = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
    geometry = exact_load.capture.diag.core.geometry_tools.GrainGeometry(
        data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    core = job.parent.api.frozen.oldcore
    original_integrate = core.integrate
    calls = []
    finalizers = []

    def algebra_only(*args, **kwargs):
        api.require(len(calls) < d['maximum_pose_calls'], 'one algebra-only callback')
        calls.append('fixed_pose_only')
        return {'diagnostic_pose': REPLAY(field, geometry, spec, state, row['dt_s'])}

    job.clear_telemetry(); job.fast.capture_systems = True
    # This time limit bounds this algebraic diagnostic, not the stopped campaign.
    deadline = (job.utc() + job.timedelta(minutes=5)).isoformat()
    core.integrate = algebra_only
    started = time.perf_counter()
    try:
        with job.prior.p.hot.scope(), job.parent.fix.scope(), \
             job.deadline.scope(job.parent.engine.runtime, deadline, True), \
             job.capture.scope(job.parent.engine.runtime, True), \
             capture_finalizers(finalizers, d['maximum_finalizer_calls']):
            with job.parent.engine.runtime.repair_scope():
                result = job.parent.api.frozen.parent.integrate()
        q, detail = result['diagnostic_pose']
    finally:
        core.integrate = original_integrate
    replay_early = copy.deepcopy(job.fast.attempts)
    accepted = [f for f in finalizers if f['accepted']]
    physical = [independent.physical(f) for f in accepted]
    first, last = accepted[0], accepted[-1]
    # Compare every saved matrix and contact input, not only the small velocity.
    early_keys = ['vfree', 'mobility', 'jacobian', 'gaps_m', 'dt_s', 'friction', 'velocity']
    exact_initial = {k: np.array_equal(first[k], attempt[k]) for k in early_keys}
    fault = None
    try:
        independent.record_coverage(record, job.fast.old.__name__)
    except RuntimeError as error:
        fault = str(error)
    delta = np.asarray(last['velocity']) - np.asarray(first['velocity'])
    checks = {
        'one_fenced_pose_call': len(calls) == 1,
        'exact_archived_early_system': all(exact_initial.values()),
        'exact_archived_early_reactions': np.array_equal(first['health']['reactions'], attempt['health']['reactions']),
        'exact_accepted_row_velocity': np.array_equal(q, row['velocity_generalized']),
        'final_finish_is_returned_velocity': np.array_equal(q, last['velocity']),
        'intermediate_differs_from_final': not np.array_equal(first['velocity'], last['velocity']),
        'final_is_within_pose_reuse': last['solver'] == 'within_pose_verified_prior',
        'same_reactions_reused': np.array_equal(first['force'], last['force']),
        'all_successful_finalizers_physically_checked': all(p['passed'] for p in physical),
        'original_association_failure_preserved': fault == 'early solve belongs to accepted trial',
        'legacy_sources_and_evidence_unchanged': True,
    }
    api.write(OUT / 'captured_finalizers.json', finalizers, raw=True)
    api.write(OUT / 'replayed_early_attempts.json', replay_early, raw=True)
    report = {'stage': d['stage'], 'diagnosis_passed': all(checks.values()), 'checks': checks,
              'pose_calls': len(calls), 'trajectory_steps_advanced': 0,
              'captured_finalizer_calls': len(finalizers), 'accepted_finalizer_calls': len(accepted),
              'exact_early_inputs': exact_initial, 'independent_physical_checks': physical,
              'final_minus_early_velocity': delta.tolist(), 'velocity_difference_norm': float(np.linalg.norm(delta)),
              'frozen_pose_detail': detail, 'elapsed_wall_s': time.perf_counter() - started,
              'original_failed_guard': fault, 'original_stage187_passed': False,
              'full_observation_complete': False, 'production_promotion': False,
              'evidence_boundary': 'Compressed and uncompressed envelope seals verified; no full prefix-history reconstruction or retroactive segment acceptance.',
              'root_cause': 'Early acceptance records an inner contact solve, not final accepted timestep velocity. The unchanged Stage79 within-pose reaction reuse performs a later inner solve whose velocity differs. Exact final-row equality is an invalid association contract for that intermediate record.',
              'proposed_next_only': 'Versioned trace of timestep/trial/inner-iteration identity plus every accepted inner-system/reuse binding and final output; independent completeness/corruption tests and full-stack qualification. Preserve original physical gates. Do not replace exact identity with a numerical tolerance.',
              'design_sha256': api.sha(DESIGN), 'claim': d['claim']}
    verify(d)
    report['artifacts'] = {str(p): api.sha(p) for p in OUT.iterdir() if p.is_file()}
    api.write(OUT / 'results.json', report, raw=True)
    api.write(OUT / 'completion.json', {'results_sha256': api.sha(OUT / 'results.json'),
              'diagnosis_passed': report['diagnosis_passed'], 'trajectory_steps_advanced': 0})
    print('DIAGNOSIS', checks, 'finalizers', len(finalizers), 'delta', delta.tolist(), flush=True)
    api.require(report['diagnosis_passed'], 'exact diagnostic reproduction')


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']:
        prepare()
    elif sys.argv[1:] == ['run']:
        run()
    else:
        raise ValueError('prepare or run; no trajectory execution mode')
