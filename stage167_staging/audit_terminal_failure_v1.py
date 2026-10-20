"""Read-only Stage167 failure localization; no retry, repair or integration."""
from pathlib import Path
import collections
import datetime
import sys
import numpy as np
import audit_paired_deadline_campaign_v3 as audit

c, api = audit.c, audit.api
OUT = c.OUT.parent / 'failure_assessment_01'


def main():
    d = api.read(c.DESIGN); c.verify(d); c.verify_preflight()
    root = api.read(c.RUN/'completion.json')
    evaluated = api.read(c.OUT/'results.json')
    api.require(api.read(c.OUT/'completion.json')['results_sha256'] == audit.file_sha(c.OUT/'results.json'), 'terminal audit seal')
    api.require(not root['all_observations_complete'] and not evaluated['passed'], 'failed/incomplete verdict preserved')
    case = next(x for x in d['cases'] if x['id'] == 's2_i0_sphere_f0p03125')
    folder = c.RUN/case['id']; paths = sorted(folder.glob('segment_*.json.gz'))
    api.require(len(paths) == 138 and len(root['failures']) == 1 and root['failures'][0]['case_id'] == case['id'], 'observed failure target')
    OUT.mkdir(parents=True, exist_ok=False)
    prefix = audit.case_audit(d, case, paths[:-1], OUT, False)
    previous = c.storage.read_record(paths[-2], audit.file_sha(c.DESIGN))['result']['checkpoint']
    record = c.storage.read_record(paths[-1], audit.file_sha(c.DESIGN)); r = record['result']
    api.require(record['spec'] == case['spec'], 'failing record spec')
    api.require(record['input_checkpoint_sha256'] == api.digest(previous), 'failed-segment chain')
    effective = c.model.binding_for(c.case_binding(d,case), True)
    api.require(record['effective_binding'] == effective and r['checkpoint']['contract'] == c.engine.prior.contracts.expected_contract(case['spec'],effective), 'failed-segment physics binding')
    api.require(r['checkpoint']['state_sha256'] == api.digest(r['checkpoint']['state']), 'failed state hash')
    clock = c.b.old.parent.prior.w.prior.audit.clock_chain(previous['state']['t'],record['rows'],r['time_s'])
    api.require(clock['passed'] and len(record['rows']) == r['steps']-previous['state']['steps'], 'failed-segment accepted-clock accounting')
    api.require(np.isfinite(np.asarray([[row['time_s'], row['dt_s'], *row['position_m'], *row['orientation'], *row['velocity_generalized']] for row in record['rows']])).all(), 'finite saved trace')
    rejected = r['checkpoint']['state']['rejected_trials']
    api.require(previous['state']['rejected'] == 0 and len(rejected) == r['rejected'] == 28, '28 observed rejected trials')
    try: c.check(record, previous, case['spec'], c.case_binding(d,case), d['budget']['step_cap_per_call'])
    except RuntimeError as error:
        api.require(str(error) == 'no newly rejected trial', 'independently reproduce exact frozen gate failure')
    else: raise RuntimeError('failed gate unexpectedly passed')
    first = rejected[0]
    pose = next(row for row in reversed(record['rows']) if row['time_s'] <= first['time_s'])
    api.require(pose['time_s'] == first['time_s'], 'saved pose at first rejection')
    fibres = [x for x in evaluated['records'] if x.get('shape') == 'rigid_prolate_ar4' and x.get('sample_id') == 0]
    api.require(len(fibres) == 2 and all(x['health']['passed'] and not x['complete_observation'] for x in fibres), 'healthy but incomplete fibre prefixes')
    records = list(c.RUN.rglob('*'))
    result = {'audit_integrity_passed': True, 'scientific_gates_passed': False, 'all_observations_complete': False,
        'new_simulation_executed': False, 'failing_case': case['id'], 'healthy_sphere_prefix': prefix,
        'first_rejection': first, 'first_rejection_pose': pose,
        'rejection_reason_counts': dict(collections.Counter(x['reason'] for x in rejected)),
        'failed_segment': {'path': str(paths[-1]), 'sha256': audit.file_sha(paths[-1]), 'accepted_steps':len(record['rows']),
                           'final_time_s':r['time_s'], 'pending_trial': r['checkpoint']['state']['pending_trial'],
                           'accepted_state_health':c.engine.prior.reference.independent_health(r,case['spec']), 'clock':clock},
        'total_saved_accepted_steps': sum(x['steps'] for x in fibres)+r['steps'],
        'unrun_cases':root['unrun_cases'], 'fibre_stop_reason':'supervisor_cooperative_stop',
        'conclusion':'Frozen zero-new-rejection gate failed at three-grain sphere contact. The last accepted state passes health bounds, but 28 cone/residual solver rejections invalidate promotion. Algebraic root cause is not yet established; no tolerance or policy relaxation is authorized.',
        'deadline':'24 September completion is no longer supported by the current failed campaign; any remedy needs a bounded scientific review and explicit new authority.',
        'design_sha256': audit.file_sha(c.DESIGN), 'evaluator_sha256': audit.file_sha(__file__),
        'terminal_evaluation_sha256':audit.file_sha(c.OUT/'results.json'),
        'artifacts':{str(p):audit.file_sha(p) for p in records if p.is_file()},
        'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    c.verify(d)
    api.write(OUT/'results.json', result, raw=True)
    api.write(OUT/'completion.json', {'audit_integrity_passed':True,'scientific_gates_passed':False,'results_sha256':audit.file_sha(OUT/'results.json')})
    print('FAILURE VERIFIED',result['rejection_reason_counts'],'accepted steps',result['total_saved_accepted_steps'],flush=True)


if __name__ == '__main__': main()
