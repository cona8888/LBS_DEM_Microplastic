"""Bounded twelve-hour, gate-driven coarser timestep investigation.

Unchanged Stage219 integrator and independent physics auditor in a new namespace.
No population, flow-level, spatial-convergence or experimental-validation claim.
"""
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace
from datetime import timedelta
import copy, cProfile, os, pstats, shutil, sys, time, traceback
import psutil
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage220_staging'))
import recover_fibre_v1 as inherited
api, old = inherited.api, inherited.job
source = inherited.source
SELF = Path(__file__).resolve()
BASE = 'overnight_coarser_20261007'
PLAN = ROOT/'stage222_designs'/BASE/'design_01.json'
RUN = ROOT/'stage222_runs'/BASE/'run_01'
OUT = ROOT/'stage222_evaluations'/BASE
PREREQUISITE = inherited.OUT/'combined_evaluation_01/results.json'
job = ModuleType('_stage222_unchanged_numerical_core')
job.__dict__.update(vars(old))
for name, fn in list(vars(old).items()):
    if isinstance(fn, FunctionType) and fn.__globals__ is vars(old):
        setattr(job, name, FunctionType(fn.__code__, vars(job), fn.__name__, fn.__defaults__, fn.__closure__))
job.DESIGN = PLAN
job.RUN, job.OUT, job.ROOT = RUN, OUT, ROOT
execute = FunctionType(source.execute.__code__, {**source.execute.__globals__, 'job': job},
                       'execute_segment', source.execute.__defaults__, source.execute.__closure__)
inner = FunctionType(source.inner.__code__, {**source.inner.__globals__, 'job': job},
                     'inner_kernel', source.inner.__defaults__, source.inner.__closure__)
kernel = FunctionType(source.kernel.__code__, {**source.kernel.__globals__, '_kernel': inner},
                      'kernel', source.kernel.__defaults__, source.kernel.__closure__)
job.kernel = SimpleNamespace(evaluate=kernel)


def sealed(path):
    row = api.read(path)
    api.require(api.read(path.parent/'completion.json')['results_sha256'] == api.sha(path), 'Sealed evidence')
    return row


def clone_check():
    api.require(execute.__code__ is source.execute.__code__ and inner.__code__ is source.inner.__code__
                and kernel.__code__ is source.kernel.__code__, 'Unchanged integrator adapter and physics auditor bytecode')
    api.require(execute.__globals__['job'] is job and inner.__globals__['job'] is job
                and kernel.__globals__['_kernel'] is inner, 'Isolated actual execution bindings')
    api.require(execute.__globals__['WORK'] == inner.__globals__['WORK'] == old.WORK,
                'Original numerical-gap policy remains unchanged')
    api.require(job.binding.__code__ is old.binding.__code__ and job.binding.__globals__ is vars(job),
                'New physical identity, original binding algorithm')


def prepare():
    clone_check()
    original = api.read(old.DESIGN)
    start = job.policy.utc('2026-10-07T00:10:57+00:00')
    end = start + timedelta(hours=12)
    api.require(end <= job.policy.utc(original['simulation_cutoff_utc']), 'Within original work window')
    d = copy.deepcopy(original)
    d.pop('binding')
    cases = []
    allowed = ('max_dt_s', 'displacement_fraction', 'angle_limit_rad', 'relaxation_fraction')
    for sample in (0, 124):
        for shape in ('rigid_prolate_ar4', 'equal_volume_sphere'):
            ref = next(c for c in original['cases'] if c['sample_id'] == sample and c['shape'] == shape and c['factor'] == .0625)
            case = copy.deepcopy(ref)
            case['reference_case'] = ref['id']
            case['id'] = ref['id'].replace('f0p0625', 'f0p125')
            case['factor'], case['step_ceiling'] = .125, 5000000
            spec = case['spec']
            spec['case_id'] = case['id']
            spec['refinement'] *= 2
            for key in allowed:
                spec['config']['numerics'][key] *= 2
            cases.append(case)
    d.update(stage='Stage222 bounded coarser-timestep numerical investigation', cases=cases,
             fresh_start_required=True, physical_changes=[], numerical_changes=list(allowed),
             production_authorized=True, authorized_start_utc=start.isoformat(), authorized_end_utc=end.isoformat(),
             simulation_cutoff_utc=(end-timedelta(minutes=10)).isoformat(), final_audit_deadline_utc=end.isoformat(),
             minimum_free_disk_bytes=20*1024**3, maximum_saved_steps_including_diagnostics=10000000,
             maximum_calls_per_case=1500, step_cap_per_call=10000, workers=1, threads=1, logical_cpu=10,
             maximum_unverified_records=1, qualification_steps_per_case=512,
             prerequisite=str(PREREQUISITE), prerequisite_required_pass=True,
             case_order=[c['id'] for c in cases], early_stop_on_any_failed_physical_or_full_path_gate=True,
             automatic_factor_escalation=False, original_policy_sha256=api.sha(old.WORK),
             sources={**original['sources'], **{str(p):api.sha(p) for p in SELF.parent.glob('*.py')}},
             inputs={**original['inputs'], str(old.DESIGN):api.sha(old.DESIGN),
                     str(inherited.PLAN):api.sha(inherited.PLAN),
                     str(ROOT/'stage221_evaluations/cost_review_20261007/snapshot_01/results.json'):
                     api.sha(ROOT/'stage221_evaluations/cost_review_20261007/snapshot_01/results.json')},
             claim='Finite-level temporal and affordability investigation for two labelled starts at one packing/flow. Diagnostic steps are separate; no population shape/flow trend or spatial/experimental validation.',
             resource_limit='Twelve-hour window is a maximum, not a promise to finish four cases. Stop on failure, gates, disk, time, calls or saved steps; incomplete outcomes remain explicit.')
    d['binding'] = api.digest(d)
    job.commit(PLAN, d)
    verify(d)
    print('OVERNIGHT_PREPARED', d['authorized_end_utc'], flush=True)


def verify(d):
    clone_check()
    api.require(d['binding'] == api.digest({k:v for k,v in d.items() if k != 'binding'}), 'Frozen overnight design')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    original = api.read(old.DESIGN)
    api.require(d['physical_changes'] == [] and d['numerical_gates'] == original['numerical_gates'], 'Unchanged scientific gates')
    for case in d['cases']:
        ref = next(c for c in original['cases'] if c['id'] == case['reference_case'])
        expected = copy.deepcopy(ref['spec'])
        expected['case_id'] = case['id']; expected['refinement'] *= 2
        for key in d['numerical_changes']:
            expected['config']['numerics'][key] *= 2
        api.require(case['spec'] == expected and case['factor'] == .125, 'Only predeclared numerical scaling')
    api.require(d['original_policy_sha256'] == api.sha(old.WORK), 'Unchanged numerical-gap acceptance')


def segment(d, case, geometry, before, prefix, folder, cap, previous, profile_transaction=False):
    folder.mkdir(parents=True, exist_ok=False)
    job.commit(folder/'launch.json', dict(pid=os.getpid(), created=psutil.Process().create_time(),
        argv=psutil.Process().cmdline(), utc=job.utc().isoformat(), design_sha256=api.sha(PLAN),
        input_checkpoint_sha256=api.digest(before), maximum_saved_steps=cap))
    seed = copy.deepcopy(before)
    raw = folder/'call.json.xz'
    profiler = cProfile.Profile() if profile_transaction else None
    if profiler is not None:
        profiler.enable()
    with job.prior.snapshot.scope(api, case['spec']['field_metadata']):
        rec, next_prefix, seal, elapsed = execute(d, case, before, raw, cap, prefix, d['simulation_cutoff_utc'])
    steps = len(rec['rows'])
    job.commit(folder/'accounting.json', dict(saved_steps=steps, raw_sha256=api.sha(raw),
        transaction_seconds=elapsed, rejected=rec['result']['rejected']))
    decoded, checked_prefix = job.codec.read_record(raw, api.sha(PLAN), prefix)
    api.require(api.digest(decoded) == api.digest(rec) and next_prefix.reference() == checked_prefix.reference(), 'Independent archive reconstruction')
    api.require(api.digest(before) == api.digest(seed), 'Caller checkpoint preserved')
    summary = kernel(decoded, case['spec'], job.binding(d, case), seed, geometry, api.sha(PLAN), d['minimum_gap_semantics'])
    api.require(summary['passed'] and rec['result']['rejected'] == 0 and 0 < steps <= cap, 'Original independent physical gates')
    cp = rec['result']['checkpoint']
    api.require(cp['state']['steps']-(0 if seed is None else seed['state']['steps']) == steps, 'Exact incremental step ledger')
    trace = np.asarray([[r['time_s'], *r['position_m'], *r['orientation'], *r['velocity_generalized']] for r in rec['rows']], dtype=np.float64)
    with (folder/'trace.npy').open('xb') as stream:
        np.save(stream, trace, allow_pickle=False)
    if profiler is not None:
        profiler.disable()
        profiler.dump_stats(str(folder/'transaction_profile.pstats'))
    row = dict(passed=True, new_saved_steps=steps, summary=summary, transaction_seconds=elapsed,
        design_sha256=api.sha(PLAN), input_checkpoint_sha256=api.digest(seed), output_checkpoint_sha256=api.digest(cp),
        previous_receipt_sha256=previous, transaction_profiled=profile_transaction,
        profile_limit='Profiled timings include profiler overhead; do not pool with unprofiled performance measurements.' if profile_transaction else None,
        artifacts={str(p):api.sha(p) for p in folder.iterdir() if p.is_file()})
    job.commit(folder/'results.json', row)
    job.commit(folder/'completion.json', dict(passed=True, results_sha256=api.sha(folder/'results.json')))
    return rec, next_prefix, row


def geometry_for(case):
    job.parent.b.old.parent.configure()
    with job.prior.snapshot.scope(api, case['spec']['field_metadata']):
        _, data, meta = api.fields.load(2, 1., 6)
    return job.prior.candidate.original.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])


def qualify(d, case, geometry):
    root = RUN/case['id']/'qualification_01'
    profile = cProfile.Profile(); profile.enable()
    a, pa, ra = segment(d, case, geometry, None, None, root/'serial_01', 256, None)
    profile.disable(); profile.dump_stats(str(root/'serial_profile.pstats'))
    b, pb, rb = segment(d, case, geometry, None, None, root/'split_a_01', 128, None)
    c, pc, rc = segment(d, case, geometry, b['result']['checkpoint'], pb, root/'split_b_01', 128, api.sha(root/'split_a_01/results.json'))
    api.require(ra['new_saved_steps'] == 256 and rb['new_saved_steps'] == rc['new_saved_steps'] == 128, '512 bounded diagnostic steps')
    api.require(a['rows'] == b['rows']+c['rows'] and api.digest(a['result']['checkpoint']) == api.digest(c['result']['checkpoint']), 'Exact serial/split candidate checkpoint and rows')
    stats = pstats.Stats(profile)
    timings = sorted([dict(file=k[0],line=k[1],function=k[2],calls=x[1],self_seconds=x[2],cumulative_seconds=x[3]) for k,x in stats.stats.items()], key=lambda x:x['cumulative_seconds'], reverse=True)[:30]
    row = dict(passed=True, diagnostic_saved_steps=512, exact_serial_split=True, profile_scope='Initial 256-step serial transaction including archive and physical audit; not a full-path cost profile.',
               profile=timings, artifacts={str(p):api.sha(p) for p in root.rglob('*') if p.is_file()})
    job.commit(root/'results.json',row); job.commit(root/'completion.json',dict(passed=True,results_sha256=api.sha(root/'results.json')))
    return 512


def compare(d, case, terminal, entries):
    refname = case['reference_case']
    if case['sample_id'] == 0:
        refname = next(c['id'] for c in api.read(old.DESIGN)['cases'] if c['shape']==case['shape'] and c['sample_id']==0 and c['factor']==.03125)
    proof = sealed(PREREQUISITE)
    api.require(proof['passed'], 'Passing successor prerequisites')
    original_folder = old.RUN/refname
    reference_paths = sorted(original_folder.glob('segment_*.npy'))
    if refname == inherited.NAME:
        reference_paths += [inherited.RUN/'production_01'/f"segment_{x['segment']:05d}"/'trace.npy' for x in inherited.sealed(inherited.RUN/'production_01/results.json')['entries']]
    for path in reference_paths:
        api.require(proof['artifacts'][str(path)] == api.sha(path), 'Comparison trace authenticated by successor seal')
    state = terminal['checkpoint']['state']
    evidence = dict(status=terminal['status'], steps=state['steps'], start_s=0.,stop_s=state['t'],rejected=terminal['rejected'],failure_markers=[],
        pending_trial=state['pending_trial'],first_dwell_s=terminal['first_contact_dwell_time_s'],export_verified=terminal['status']=='full_window_exit',
        raw_hashes_verified=True,clock_steps_verified=True,physics_verified=True,fresh_start=True)
    observation = job.policy.observation(evidence,case['spec']['horizon_s'])
    # Original policy observation dictionaries are retained by the successor.
    reference = next(row for placement in proof['placements'] for row in placement['cases'] if row['case_id']==refname)
    def blocks(paths):
        for path in paths:
            yield np.load(path,mmap_mode='r',allow_pickle=False)
    initial = case['spec']['initial_state']
    row0 = [0.,*initial['position_m'],*initial['orientation'],*initial['velocity_generalized']]
    paths = [RUN/case['id']/f"segment_{x['segment']:05d}"/'trace.npy' for x in entries]
    cfg = case['spec']['config']
    metrics = job.path_metrics.metrics(blocks(paths),blocks(reference_paths),row0,row0,observation['stop_s'],reference['stop_s'],cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
    gates = job.policy.pair_gates(observation,reference,metrics,d['numerical_gates'])
    row = dict(passed=gates['passed'], case=case['id'],reference_case=refname,observation=observation,
               full_path_gates=gates,reference_evaluation_sha256=api.sha(PREREQUISITE),new_trajectory_steps=0)
    destination = OUT/case['id']/'comparison_01'
    job.commit(destination/'results.json',row);job.commit(destination/'completion.json',dict(passed=row['passed'],results_sha256=api.sha(destination/'results.json')))
    return row


def run():
    d = api.read(PLAN); verify(d)
    RUN.mkdir(parents=True,exist_ok=False)
    process = psutil.Process(); process.cpu_affinity([d['logical_cpu']])
    job.commit(RUN/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=job.utc().isoformat(),design_sha256=api.sha(PLAN),affinity=process.cpu_affinity()))
    total = 0; diagnostic = 0; cases = []; reason = 'work_window'; reservation = None
    try:
        launch = api.read(inherited.RUN/'production_launcher_01/launch.json')
        while not (PREREQUISITE.parent/'completion.json').exists():
            api.require(job.utc() < job.policy.utc(d['simulation_cutoff_utc']), 'Prerequisite wait within overnight window')
            api.require(not list((inherited.RUN/'production_01').rglob('failure.json')) and not (PREREQUISITE.parent/'failure.json').exists(), 'Recovery/evaluation failure stops dependent work')
            p = psutil.Process(launch['pid'])
            api.require(abs(p.create_time()-launch['created']) < .001 and p.cmdline()==launch['argv'], 'Exact original recovery identity while waiting')
            time.sleep(20)
        prerequisite = sealed(PREREQUISITE)
        api.require(prerequisite['passed'], 'Full inherited scientific gate must pass')
        job.commit(RUN/'prerequisite_admission.json',dict(passed=True,results_sha256=api.sha(PREREQUISITE),utc=job.utc().isoformat()))
        # No competing trajectory before independent, sequential execution.
        while any(p.pid != process.pid and 'recover_fibre_v1.py' in ' '.join(p.info.get('cmdline') or []) for p in psutil.process_iter(['cmdline'])):
            api.require(job.utc() < job.policy.utc(d['simulation_cutoff_utc']), 'Wait for recovery retirement')
            time.sleep(2)
        old.verify(api.read(old.DESIGN)); source.bindings()
        for case in d['cases']:
            if job.utc() >= job.policy.utc(d['simulation_cutoff_utc'])-timedelta(seconds=120):
                reason='simulation_cutoff';break
            if shutil.disk_usage(ROOT).free <= d['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED:
                reason='disk_reserve';break
            if total+512 > d['maximum_saved_steps_including_diagnostics']:
                reason='step_ceiling';break
            geometry = geometry_for(case)
            reservation=dict(case=case['id'],role='qualification',maximum_saved_steps=512)
            diagnostic += qualify(d,case,geometry);total+=512;reservation=None
            cp = None; prefix = None; previous = None; entries = []; rec = None; case_reason='call_limit'; contact_profiled=False
            for index in range(1,d['maximum_calls_per_case']+1):
                if job.utc() >= job.policy.utc(d['simulation_cutoff_utc'])-timedelta(seconds=120):
                    case_reason='simulation_cutoff';break
                if shutil.disk_usage(ROOT).free <= d['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED:
                    case_reason='disk_reserve';break
                remaining = min(d['maximum_saved_steps_including_diagnostics']-total,case['step_ceiling']-(0 if cp is None else cp['state']['steps']))
                if remaining <= 0:
                    case_reason='step_ceiling';break
                folder=RUN/case['id']/f'segment_{index:05d}'
                reservation=dict(case=case['id'],role='production',segment=index,maximum_saved_steps=min(d['step_cap_per_call'],remaining))
                profile_contact = not contact_profiled and cp is not None and cp['state']['first_contact_dwell_time'] is not None
                rec,prefix,row=segment(d,case,geometry,cp,prefix,folder,reservation['maximum_saved_steps'],previous,profile_contact)
                contact_profiled = contact_profiled or profile_contact
                total+=row['new_saved_steps'];cp=rec['result']['checkpoint'];previous=api.sha(folder/'results.json');reservation=None
                entries.append(dict(segment=index,new_saved_steps=row['new_saved_steps'],results_sha256=previous,stop_s=cp['state']['t']))
                print('OVERNIGHT_VERIFIED',case['id'],index,total,cp['state']['t'],flush=True)
                if rec['result']['status'] in job.policy.COMPLETE:
                    case_reason='observation_complete';break
            folder=RUN/case['id']
            row=dict(case=case['id'],complete_observation=case_reason=='observation_complete',reason=case_reason,
                     physical_steps=0 if cp is None else cp['state']['steps'],entries=entries,final_checkpoint_sha256=api.digest(cp))
            job.commit(folder/'checkpoint.json',cp)
            job.commit(folder/'prefix.json',None if prefix is None else prefix.reference())
            job.commit(folder/'results.json',row);job.commit(folder/'completion.json',dict(results_sha256=api.sha(folder/'results.json'),complete_observation=row['complete_observation']))
            cases.append(row)
            if not row['complete_observation']:
                reason=case_reason;break
            comparison=compare(d,case,rec['result'],entries)
            if not comparison['passed']:
                reason='full_path_gate_failed';break
        else:
            reason='all_four_numerical_cases_complete'
        result=dict(finished=True,reason=reason,saved_steps_including_diagnostics=total,diagnostic_saved_steps=diagnostic,
                    physical_steps=total-diagnostic,cases=cases,utc=job.utc().isoformat(),design_sha256=api.sha(PLAN),
                    claim=d['claim'],whole_overnight_success=reason=='all_four_numerical_cases_complete')
        job.commit(RUN/'results.json',result);job.commit(RUN/'completion.json',dict(results_sha256=api.sha(RUN/'results.json'),finished=True))
        print('OVERNIGHT_FINISHED',reason,total,flush=True)
    except Exception as error:
        job.commit(RUN/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),verified_saved_steps=total,
            diagnostics_verified_steps=diagnostic,unresolved_reservation=reservation,utc=job.utc().isoformat(),design_sha256=api.sha(PLAN)))
        raise


if __name__=='__main__':
    {'prepare':prepare,'check':lambda:verify(api.read(PLAN)),'run':run}[sys.argv[1]]()
