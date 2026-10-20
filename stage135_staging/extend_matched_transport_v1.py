"""Bounded continuation of qualified CPD6 sphere/AR4 states; no calibration."""
from pathlib import Path
import copy
import os
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'stage134_staging')]
import sphere_combined_budget_refinement_v1 as previous

api, engine = previous.api, previous.engine
BASE = 'matched_transport_extension_20260918'
DESIGN = ROOT/'stage135_designs'/BASE/'design_01.json'
RUN = ROOT/'stage135_runs'/BASE/'pilot_01'
EVAL = ROOT/'stage135_evaluations'/BASE
PRIOR = previous.EVAL/'independent_evaluation_01/results.json'
PRIOR_SEAL = previous.EVAL/'independent_evaluation_01/completion.json'
SOURCE_DESIGNS = [previous.DESIGN, previous.prior6.DESIGN]


def configure():
    api.fields.load = lambda *args, **kwargs: previous.cpd6.load()


def expected_cases():
    evidence = api.read(PRIOR)
    api.require(evidence['passed'] and evidence['no_failure_or_stderr'], 'prior response not qualified')
    books = [(p, api.read(p)) for p in SOURCE_DESIGNS]
    cases = []
    for shape in evidence['shapes']:
        ref = shape['record_bindings']['cpd6']
        api.require(api.sha(ref['path']) == ref['sha256'], 'source record drift')
        record = api.read(ref['path'])
        path, source_case = next((p,c) for p,d in books for c in d['cases'] if c['id']==record['case_id'])
        api.require(record['design_sha256']==api.sha(path), 'source design drift')
        r = record['result']
        api.require(r['status']=='present_at_horizon' and r['time_s']==.5, 'invalid source endpoint')
        spec = copy.deepcopy(source_case['spec'])
        spec['horizon_pv'] = .1
        spec['horizon_s'] = .1 / spec['field_metadata']['pv_per_second']
        spec['case_id'] = f"s2_{shape['shape']}_cpd6_extension_0p1pv"
        cp = r['checkpoint']
        api.require(cp['state_sha256']==api.digest(cp['state']), 'source state hash drift')
        api.require(cp['state']['pending_trial'] is None, 'source has pending adaptive trial')
        api.require(engine.prior.reference.independent_health(r,source_case['spec'])['passed'], 'source health')
        cases.append({'id':spec['case_id'],'spec':spec,'source_spec':source_case['spec'],
                      'source_record':ref,'source_design':str(path),
                      'source_state_sha256':cp['state_sha256']})
    return cases


def bound(d,c):
    return api.digest([d['binding'],c['id']])


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}), 'design self-binding')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    api.require(d['cases']==expected_cases() and d['physical_changes']==[], 'case/physics drift')
    api.require(d['budget']=={'segment_s':45,'max_segments_per_case':12,'stage_wall_s':1200,'threads':1}, 'budget drift')


def prepare():
    api.require(not DESIGN.exists(), 'immutable design exists')
    cases=expected_cases()
    inputs={str(p):api.sha(p) for p in [PRIOR,PRIOR_SEAL,*SOURCE_DESIGNS]}
    for c in cases:
        inputs[c['source_record']['path']]=c['source_record']['sha256']
        inputs[str(Path(c['source_record']['path']).parent/'completion.json')]=api.sha(Path(c['source_record']['path']).parent/'completion.json')
        for v in c['spec']['field_metadata'].values():
            if isinstance(v,dict) and 'path' in v and 'sha256' in v:
                api.require(api.sha(v['path'])==v['sha256'], 'field lineage drift')
                inputs[v['path']]=v['sha256']
    paths={Path(m.__file__).resolve() for m in list(sys.modules.values())
           if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents}
    paths.add(Path(__file__).resolve())
    d={'stage':'Stage135','cases':cases,'physical_changes':[],
       'question':'Can the same matched sphere and AR4 trajectories advance from 0.5 s to 0.1 PV within a bounded cost, and is whole-body downstream passage observed?',
       'scope':'Two conditional near-outlet continuations in the same seed-2 fixed matrix and prescribed CPD6 field. No population, other flow level, new GPU solve or parameter fit.',
       'checkpoint_policy':'Preserve every accepted state field exactly and explicitly rebind only the immutable contract for the longer horizon/new run. Do not alter the original records. This is a piecewise continuation, not a fresh unsplit-path convergence test.',
       'budget':{'segment_s':45,'max_segments_per_case':12,'stage_wall_s':1200,'threads':1},
       'budget_rule':'Cooperative checks between adaptive trials and before each dispatch. Never kill an existing job; a single solver call or I/O may overshoot. Stop on health/source failure. Budget-incomplete is unresolved, never trapped.',
       'acceptance':{'inherited_health_gates':api.read(previous.DESIGN)['acceptance'],
                     'query_completion':'present_at_horizon at the exact declared horizon, or verified full_window_exit',
                     'new_long_horizon_temporal_spatial_convergence_claim':False,
                     'population_release_inference':False,'experimental_validation_claim':False},
       'sources':{str(p):api.sha(p) for p in sorted(paths)},'inputs':inputs}
    d['binding']=api.digest(d)
    DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);verify(d)
    print('FROZEN',api.sha(DESIGN),'target_s',cases[0]['spec']['horizon_s'],flush=True)


def migrated_checkpoint(d,c,spec=None):
    source=api.read(c['source_record']['path'])['result']['checkpoint']
    api.require(source['state_sha256']==c['source_state_sha256']==api.digest(source['state']), 'source checksum')
    cp=copy.deepcopy(source)
    cp['contract']=engine.prior.contracts.expected_contract(spec or c['spec'],bound(d,c))
    api.require(cp['state']==source['state'], 'source state modified')
    return cp


def preflight():
    d=api.read(DESIGN);verify(d);configure();out=EVAL/'preflight_01'
    api.require(not out.exists(), 'immutable preflight exists')
    checks=[]
    for c in d['cases']:
        replay=copy.deepcopy(c['source_spec'])
        cp=migrated_checkpoint(d,c,replay)
        r,rows=engine.runtime.execute(replay,bound(d,c),checkpoint=cp)
        exact=r['checkpoint']['state']==cp['state'] and r['checkpoint']['state_sha256']==cp['state_sha256']
        checks.append({'case_id':c['id'],'zero_advance_exact_state':exact,
                       'time_s':r['time_s'],'new_intervals':len(rows),
                       'physics_and_numerics_unchanged':c['spec']['config']==replay['config'],
                       'initial_state_unchanged':c['spec']['initial_state']==replay['initial_state']})
        api.require(exact and not rows and r['time_s']==.5,'zero-advance replay mismatch')
    # Deterministic corruption and forbidden-change tests, no trajectory advancement.
    tampered=copy.deepcopy(d);tampered['cases'][0]['spec']['config']['friction_coefficient']+=.1
    rejected=False
    try:verify(tampered)
    except (RuntimeError,ValueError,AssertionError):rejected=True
    api.require(rejected,'tamper not rejected')
    out.mkdir(parents=True)
    api.write(out/'results.json',{'passed':True,'design_sha256':api.sha(DESIGN),'checks':checks,
                                'tampered_physics_rejected':rejected,'trajectory_time_advanced_s':0})
    print('PREFLIGHT_PASS',checks,flush=True)


def worker(name,segment):
    d=api.read(DESIGN);verify(d);configure();c=next(c for c in d['cases'] if c['id']==name)
    api.require(1<=segment<=d['budget']['max_segments_per_case'],'segment outside budget')
    out=RUN/name/f'segment_{segment:02d}';prior_hash=None
    if segment==1:
        cp=migrated_checkpoint(d,c)
    else:
        p=out.parent/f'segment_{segment-1:02d}/record.json';old=api.read(p);prior_hash=api.sha(p)
        api.require(api.read(p.parent/'completion.json')['record_sha256']==prior_hash,'prior record checksum')
        api.require(old['design_sha256']==api.sha(DESIGN) and old['case_id']==name and old['result']['status']=='incomplete_budget','invalid continuation')
        cp=old['result']['checkpoint']
    api.require(cp['state_sha256']==api.digest(cp['state']) and cp['contract']==engine.prior.contracts.expected_contract(c['spec'],bound(d,c)),'checkpoint contract')
    out.mkdir(parents=True,exist_ok=False)
    api.write(out/'launch.json',{'pid':os.getpid(),'command':sys.argv,'design_sha256':api.sha(DESIGN),'case_id':name,'segment':segment,'python':sys.version})
    try:
        r,rows=engine.runtime.execute(c['spec'],bound(d,c),checkpoint=cp)
        health=engine.prior.reference.independent_health(r,c['spec'])
        verify(d)
        api.write(out/'accepted_intervals.json',rows,raw=True)
        record={'case_id':name,'segment':segment,'design_sha256':api.sha(DESIGN),
                'source_record_sha256':c['source_record']['sha256'],'prior_record_sha256':prior_hash,
                'checkpoint_input_sha256':api.digest(cp),'checkpoint_start_time_s':cp['state']['t'],
                'migration_exact_state':segment==1 and cp['state_sha256']==c['source_state_sha256'],
                'result':r,'health':health,'accepted_intervals_sha256':api.sha(out/'accepted_intervals.json')}
        api.write(out/'record.json',record,raw=True)
        api.write(out/'completion.json',{'record_sha256':api.sha(out/'record.json'),'launch_sha256':api.sha(out/'launch.json'),'status':r['status']})
        okay=health['passed'] and r['status'] in ['present_at_horizon','full_window_exit','incomplete_budget']
        if not okay:api.write(out/'failure.json',{'status':r['status'],'reason':r.get('reason'),'health':health})
        print(name,segment,r['status'],'t',r['time_s'],'wall',r['runtime_seconds'],flush=True)
        return 0 if okay else 4
    except Exception as exc:
        if not (out/'failure.json').exists():api.write(out/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()})
        raise


def run():
    d=api.read(DESIGN);verify(d);p=EVAL/'preflight_01/results.json'
    api.require(api.read(p)['passed'] and api.read(p)['design_sha256']==api.sha(DESIGN),'preflight required')
    RUN.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    api.write(RUN/'manifest.json',{'pid':os.getpid(),'command':sys.argv,'design_sha256':api.sha(DESIGN),
              'case_order':[c['id'] for c in d['cases']],'preflight_sha256':api.sha(p),'threads':1})
    started=time.perf_counter();ledger=[];stopped=False
    for c in d['cases']:
        paths=[];entry={'case_id':c['id'],'status':'not_run','records':paths}
        for segment in range(1,d['budget']['max_segments_per_case']+1):
            if stopped or time.perf_counter()-started+55>d['budget']['stage_wall_s']:break
            stem=c['id']+f'_{segment:02d}'
            with (RUN/(stem+'.stdout.txt')).open('x') as stdout,(RUN/(stem+'.stderr.txt')).open('x') as stderr:
                child=subprocess.run([sys.executable,'-B','-u',__file__,'worker',c['id'],str(segment)],stdout=stdout,stderr=stderr,env=env)
            path=RUN/c['id']/f'segment_{segment:02d}/record.json'
            if path.exists():
                paths.append({'path':str(path),'sha256':api.sha(path)})
                r=api.read(path)['result'];entry.update(status=r['status'],time_s=r['time_s'])
                print(c['id'],segment,r['status'],'t',round(r['time_s'],8),'wall_s',round(r['runtime_seconds'],3),flush=True)
            else:entry['status']='worker_failure'
            if child.returncode:
                stopped=True;entry['worker_returncode']=child.returncode;break
            if entry['status']!='incomplete_budget':break
        ledger.append(entry)
    verify(d)
    api.write(RUN/'completion.json',{'design_sha256':api.sha(DESIGN),'manifest_sha256':api.sha(RUN/'manifest.json'),
              'ledger':ledger,'stopped_on_failure':stopped,'wall_s':time.perf_counter()-started})
    print('BOUNDED_DISPATCH_COMPLETE',not stopped,flush=True)
    return 4 if stopped else 0


def audit():
    d=api.read(DESIGN);verify(d);done=api.read(RUN/'completion.json');rows=[]
    api.require(done['design_sha256']==api.sha(DESIGN) and done['manifest_sha256']==api.sha(RUN/'manifest.json'),'dispatch binding')
    api.require([e['case_id'] for e in done['ledger']]==[c['id'] for c in d['cases']],'case order')
    for c,e in zip(d['cases'],done['ledger']):
        previous_cp=migrated_checkpoint(d,c);previous_hash=None;integration=0.;all_health=True;last=None
        for k,b in enumerate(e['records'],1):
            p=Path(b['path']);r=api.read(p);seal=api.read(p.parent/'completion.json')
            api.require(b['sha256']==api.sha(p)==seal['record_sha256'],'record hash')
            api.require(seal['launch_sha256']==api.sha(p.parent/'launch.json'),'launch hash')
            api.require(r['design_sha256']==api.sha(DESIGN) and r['case_id']==c['id'] and r['segment']==k,'case chain')
            api.require(r['prior_record_sha256']==previous_hash and r['checkpoint_input_sha256']==api.digest(previous_cp),'restart chain')
            api.require(r['source_record_sha256']==c['source_record']['sha256'],'source binding')
            api.require(r['accepted_intervals_sha256']==api.sha(p.parent/'accepted_intervals.json'),'interval artifact')
            result=r['result'];cp=result['checkpoint']
            api.require(cp['state_sha256']==api.digest(cp['state']) and cp['contract']==previous_cp['contract'],'output checkpoint')
            health=engine.prior.reference.independent_health(result,c['spec'])
            api.require(health==r['health'],'health re-evaluation disagreement')
            intervals=api.read(p.parent/'accepted_intervals.json')
            if intervals:
                api.require(abs(sum(x['dt_s'] for x in intervals)-(result['time_s']-previous_cp['state']['t']))<1e-9,'interval time closure')
                api.require(abs(intervals[-1]['time_s']-result['time_s'])<1e-10,'observer endpoint clock')
                api.require(api.np.allclose(intervals[-1]['position_m'],result['position_m'],atol=1e-13,rtol=0),'observer endpoint pose')
            all_health &= health['passed'];integration+=result['runtime_seconds']
            previous_hash=b['sha256'];previous_cp=cp;last=result
        rows.append({'case_id':c['id'],'status':e['status'],'segments':len(e['records']),
                     'time_s':None if last is None else last['time_s'],
                     'observed_pv':None if last is None else last['time_s']*c['spec']['field_metadata']['pv_per_second'],
                     'query_horizon_s':c['spec']['horizon_s'],'integration_wall_s':integration,
                     'all_segment_health_passed':all_health and last is not None,
                     'whole_body_downstream_export_observed':last is not None and last['status']=='full_window_exit',
                     'finite_contact_dwell_observed':None if last is None else last['persistent_contact_observed'],
                     'reason':None if last is None else last.get('reason')})
    out=EVAL/'independent_evaluation_01';out.mkdir(parents=True,exist_ok=False)
    complete=all(x['status'] in ['present_at_horizon','full_window_exit'] for x in rows)
    clean=not done['stopped_on_failure'] and not list(RUN.rglob('failure.json')) and not any(p.stat().st_size for p in RUN.glob('*.stderr.txt'))
    result={'source_and_checkpoint_audit_passed':True,'no_failure_or_stderr':clean,
            'all_queries_completed':complete,'all_health_passed':all(x['all_segment_health_passed'] for x in rows),
            'rows':rows,'wall_s':done['wall_s'],'population_release_fraction':None,
            'claim':'Bounded continuation/cost observations only; not a population release estimate, experimental validation or newly converged full path.'}
    api.write(out/'results.json',result)
    api.write(out/'completion.json',{'results_sha256':api.sha(out/'results.json'),'design_sha256':api.sha(DESIGN),'run_completion_sha256':api.sha(RUN/'completion.json')})
    print(result,flush=True)


if __name__=='__main__':
    action=sys.argv[1]
    if action=='prepare':prepare()
    elif action=='preflight':preflight()
    elif action=='run':raise SystemExit(run())
    elif action=='worker':raise SystemExit(worker(sys.argv[2],int(sys.argv[3])))
    elif action=='audit':audit()
    else:raise ValueError(action)
