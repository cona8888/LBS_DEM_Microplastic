"""Ten archived frozen-pose probes and fail-closed provenance tests, zero steps."""
from pathlib import Path
import copy
import os
import sys
import traceback
import numpy as np
import contact_trial_trace_v1 as trace
import audit_contact_trial_trace_v1 as audit
import audit_optimized_record_v3 as kernel

ROOT = trace.ROOT
sys.path.insert(0, str(ROOT / 'stage188_staging'))
import diagnose_inner_outer_association_v1 as diag
job, api = trace.old, trace.old.api
WORK = ROOT / 'stage189_designs/four_hour_repair_20260924/contract_01.json'
BASE = 'trial_provenance_20260924'
DESIGN = ROOT / 'stage189_designs' / BASE / 'design_01.json'
OUT = ROOT / 'stage189_evaluations' / BASE / 'zero_step_01'


def prepare():
    job.verify(api.read(job.DESIGN)); diag.verify(api.read(diag.DESIGN))
    api.require(job.utc() < job.policy.utc(api.read(WORK)['agent_work_end_utc']), 'authorized clock')
    inputs = [WORK, job.DESIGN, diag.DESIGN, diag.OUT/'results.json', diag.OUT/'completion.json']
    probes = []
    paths = [(job.paths(job.RUN, diag.CASE, 138)['raw'], api.sha(job.DESIGN), i, 'optimized') for i in (2793, 2794, 2795)]
    for c in api.read(job.DESIGN)['cases']:
        paths.append((job.PREFLIGHT/'probes'/(c['id']+'_contact.json.xz'), api.sha(job.DESIGN), 500, 'optimized'))
    paths.append((job.qualified.RUN/'legacy_active_fallback.json.xz', api.sha(job.qualified.DESIGN), 250, 'legacy'))
    for i, (path, design_sha, index, mode) in enumerate(paths):
        env = job.codec.base.read_record(path, design_sha)
        record = env['payload']
        prev, row = record['rows'][index-1:index+1]
        probes.append({'id': f'probe_{i:02d}', 'source': str(path), 'row_index': index, 'mode': mode,
            'spec': record['spec'], 'expected_row': row,
            'state': {'x': prev['position_m'], 'p': prev['orientation'], 'q': prev['velocity_generalized'],
                      't': prev['time_s'], 'recovery': mode == 'legacy'}})
        inputs.extend([path, path.with_suffix('.seal.json')])
    d = {'stage': 'Stage189 exact trial-provenance qualification', 'probes': probes,
         'maximum_pose_calls': len(probes), 'trajectory_steps_authorized': 0,
         'sources': job.parent.source_map(), 'inputs': {str(p): api.sha(p) for p in inputs},
         'observer_structure': trace.STRUCTURAL_IDENTITY, 'audit_structure': kernel.STRUCTURAL_IDENTITY,
         'claim': 'Observational-only repair; exact archived algebraic results and strict evidence rejection. Not trajectory qualification or a release result.'}
    d['binding'] = api.digest(d)
    DESIGN.parent.mkdir(parents=True, exist_ok=True); api.write(DESIGN, d)
    print('FROZEN', api.sha(DESIGN), flush=True)


def verify(d):
    api.require(d['binding'] == api.digest({k:v for k,v in d.items() if k!='binding'}), 'frozen design')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    api.require(d['observer_structure'] == trace.STRUCTURAL_IDENTITY and d['audit_structure'] == kernel.STRUCTURAL_IDENTITY, 'observer/auditor AST bindings')
    job.verify(api.read(job.DESIGN))


def replay(probe):
    spec = probe['spec']; job.clear_telemetry(); job.fast.capture_systems = True
    with job.prior.snapshot.scope(api, spec['field_metadata']):
        field, data, meta = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
    geometry = diag.exact_load.capture.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    core = job.parent.api.frozen.oldcore; saved = core.integrate; calls = []
    before_outer = trace.backend.inertial_contact_step
    before_step = trace.backend.stage42.inertial_contact_step
    def algebra_only(*args, **kwargs):
        api.require(not calls, 'one fixed-pose callback')
        calls.append(True)
        return {'pose': diag.REPLAY(field, geometry, spec, probe['state'], probe['expected_row']['dt_s'])}
    core.integrate = algebra_only
    stop = api.read(WORK)['agent_work_end_utc']
    solver = job.deadline.scope(job.parent.engine.runtime, stop, True) if probe['mode'] == 'optimized' else job.fast.old.scope(job.parent.engine.runtime, True)
    try:
        with job.prior.p.hot.scope(), job.parent.fix.scope(), solver, job.capture.scope(job.parent.engine.runtime, True), trace.scope(job.parent.engine.runtime, True) as log:
            with job.parent.engine.runtime.repair_scope():
                result = job.parent.api.frozen.parent.integrate()
        q, detail = result['pose']
    finally:
        core.integrate = saved
    api.require(trace.backend.inertial_contact_step is before_outer and trace.backend.stage42.inertial_contact_step is before_step, 'scope restoration')
    api.require(len(calls) == 1 and np.array_equal(q, probe['expected_row']['velocity_generalized']), 'exact archived fixed-pose velocity')
    record = {'spec': spec, 'rows': [probe['expected_row']],
              'sweep_certificates': [{'dt_s': probe['expected_row']['dt_s']}],
              'contact_trial_trace': copy.deepcopy(log), 'early_attempts': copy.deepcopy(job.fast.attempts),
              'fallback_systems': copy.deepcopy(job.capture.records), 'repairs': copy.deepcopy(job.fast.old.telemetry),
              'result': {'stage119_repair_calls': copy.deepcopy(job.parent.engine.runtime.calls)}}
    # The runtime restores its call list after scope exit; use the observed
    # immutable fallback input/output records to construct this algebra-only
    # fixture. Production tests must use the actual runtime result instead.
    record['result']['stage119_repair_calls'] = [{'accepted': s['accepted'], 'health': s['health'], 'dt_s': s['dt_s'], 'gaps_m': s['gaps_m']} for s in record['fallback_systems']]
    before = {'state': {'q': probe['state']['q']}}
    return record, before, audit.evaluate(record, before), detail


def corruption_checks(record, before):
    def tr(r): return r['contact_trial_trace']['detailed_trials'][0]
    mutations = [
        ('drop_trial', lambda r:r['contact_trial_trace']['detailed_trials'].clear()),
        ('drop_inner', lambda r:tr(r)['inner_systems'].pop()),
        ('reverse_inner', lambda r:tr(r)['inner_systems'].reverse()),
        ('duplicate_trial', lambda r:r['contact_trial_trace']['detailed_trials'].append(copy.deepcopy(tr(r)))),
        ('bad_trial_id', lambda r:tr(r).update(trial_index=5)),
        ('bad_inner_id', lambda r:tr(r)['inner_systems'][0].update(inner_index=3)),
        ('bad_count', lambda r:r['contact_trial_trace']['trial_inner_counts'].__setitem__(0,1)),
        ('bad_dt', lambda r:tr(r)['inner_systems'][0].update(dt_s=0)),
        ('bad_output', lambda r:tr(r)['velocity'].__setitem__(0,1.)),
        ('bad_old_q', lambda r:tr(r)['outer_inputs'][0].__setitem__(0,1.)),
        ('bad_free', lambda r:tr(r)['inner_systems'][1]['vfree'].__setitem__(0,1.)),
        ('bad_reuse', lambda r:tr(r)['inner_systems'][1]['health']['reactions'].__setitem__(0,-1.)),
        ('drop_early', lambda r:r['early_attempts'].clear()),
        ('bad_early_velocity', lambda r:r['early_attempts'][0]['velocity'].__setitem__(0,1.)),
        ('bad_range', lambda r:tr(r)['inner_systems'][0]['early_range'].__setitem__(1,0)),
        ('bad_route_count', lambda r:r['contact_trial_trace']['trial_route_counts'].__setitem__(0,[0,0])),
        ('bad_final_contact', lambda r:tr(r)['health']['contact'].update(residual=1.)),
        ('missing_schema', lambda r:r.pop('contact_trial_trace')),
    ]
    guards = []
    for name, mutate in mutations:
        bad = copy.deepcopy(record); mutate(bad)
        try: audit.evaluate(bad, before)
        except (RuntimeError, ValueError, KeyError, IndexError, np.linalg.LinAlgError): guards.append(name)
        else: raise AssertionError('corruption accepted: '+name)
    return guards


def run():
    d = api.read(DESIGN); verify(d)
    OUT.mkdir(parents=True, exist_ok=False)
    api.write(OUT/'launch.json', {'pid':os.getpid(), 'design_sha256':api.sha(DESIGN), 'trajectory_steps_authorized':0})
    reports = []; reference = None
    try:
        job.parent.b.old.parent.configure()
        for p in d['probes']:
            api.require(job.utc() < job.policy.utc(api.read(WORK)['agent_work_end_utc']), 'work cutoff')
            record, before, summary, detail = replay(p)
            api.write(OUT/(p['id']+'.json'), {'record':record, 'before':before, 'audit':summary, 'detail':detail}, raw=True)
            reports.append({'probe':p['id'], 'mode':p['mode'], 'exact_velocity':True, 'audit':summary})
            if p['id'] == 'probe_01': reference = (record, before)
            print('POSE_PASS', p['id'], summary, flush=True)
        guards = corruption_checks(*reference)
        # Disabled and exceptional observer scopes must not modify the backend.
        saved = trace.backend.inertial_contact_step
        with trace.scope(job.parent.engine.runtime, False) as disabled:
            api.require(disabled is None and trace.backend.inertial_contact_step is saved, 'disabled identity')
        failure = RuntimeError('expected scope-restoration fixture')
        try:
            with trace.scope(job.parent.engine.runtime, True): raise failure
        except RuntimeError as error: api.require(error is failure, 'identical exception propagation')
        api.require(trace.backend.inertial_contact_step is saved, 'exceptional scope restored')
        try:
            with trace.scope(job.parent.engine.runtime, True):
                with trace.scope(job.parent.engine.runtime, True): pass
        except RuntimeError as error: api.require(str(error)=='nested contact trial observer is unsupported', 'nested observer refused')
        else: raise AssertionError('nested observer accepted')
        verify(d)
        result = {'passed':True, 'trajectory_steps_advanced':0, 'pose_calls':len(reports), 'probes':reports,
                  'corruption_rejections':guards, 'scope_tests':3, 'design_sha256':api.sha(DESIGN),
                  'artifacts':{str(p):api.sha(p) for p in OUT.iterdir() if p.is_file()}, 'claim':d['claim']}
        api.write(OUT/'results.json',result,raw=True)
        api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('ZERO_STEP_PASS',len(reports),len(guards),flush=True)
    except Exception as error:
        api.write(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'trajectory_steps_advanced':0,'completed_pose_calls':len(reports)})
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare or run')
