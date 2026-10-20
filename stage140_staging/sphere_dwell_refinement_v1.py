"""Three-step-level, nonabsorbing sphere dwell test; no equilibrium time skip."""
from pathlib import Path
import copy
import gzip
import json
import os
import subprocess
import sys
import time
import traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage139_staging'))
import sphere_only_verification_v1 as qualified
api,engine,hot=qualified.api,qualified.engine,qualified.hot
BASE='sphere_finite_dwell_refinement_20260918'
DESIGN=ROOT/'stage140_designs'/BASE/'design_01.json'
RUN=ROOT/'stage140_runs'/BASE/'refinement_01'
OUT=ROOT/'stage140_evaluations'/BASE/'independent_evaluation_01'

def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design hash')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);qualified.verify(api.read(qualified.DESIGN))
    q=api.read(qualified.OUT/'results.json')
    api.require(q['passed'] and api.read(qualified.OUT/'completion.json')['results_sha256']==api.sha(qualified.OUT/'results.json'),'sphere-only qualification')
    api.verify_mapping(q['artifacts'])

def prepare():
    qd=api.read(qualified.DESIGN);qualified.verify(qd)
    ev=qualified.OUT/'results.json';seal=qualified.OUT/'completion.json'
    api.require(api.read(ev)['passed'] and api.read(seal)['results_sha256']==api.sha(ev),'qualified result required')
    c=next(c for c in qd['cases'] if c['id']=='sphere_12_terminal')
    source=api.read(c['source'])['result'];cp=source['checkpoint']
    api.require(cp['state']['pending_trial'] is None and not source['persistent_contact_observed'],'clean refinement boundary required')
    cases=[]
    for factor in [1.,.5,.25]:
        spec=copy.deepcopy(c['spec']);spec['horizon_s']=1.3;spec['horizon_pv']=1.3*spec['field_metadata']['pv_per_second']
        for key in api.DT_CONTROLS:spec['config']['numerics'][key]*=factor
        spec['case_id']=f'sphere_dwell_factor_{factor:g}'
        cases.append({'id':spec['case_id'],'spec':spec,'factor':factor,'source':c['source'],'source_state_sha256':cp['state_sha256']})
    d={'stage':'Stage140','physical_changes':[],'cases':cases,
       'question':'Does the almost stationary sphere sustain the declared 0.5 s contact dwell under normal integration, and is that local result stable to two timestep halvings?',
       'numerical_changes':'Sphere-only algebraically checked branch; all four timestep controls scaled by 1, 1/2, 1/4. Horizon 1.3 s. Preserve all incoming histories. No skipped time or absorbing dwell.',
       'acceptance':{'position_over_b':1e-8,'axis_vector_norm':1e-8,'generalized_velocity_relative':1e-7,'clock_s':1e-12,
                     'event_time_tolerance':'twice the largest accepted step','all_three_complete':True,'health':True,'exact_hash_chain':True},
       'budget':{'segments_per_case':9,'segment_s':45,'stage_dispatch_s':850},
       'claim_boundary':'Local finite-duration contact dwell from one saved sphere state only. Not irreversible retention, full-path convergence, absolute permeability validation, or population release. Fibre excluded after Stage138 discrepancy.',
       'sources':{str(Path(__file__).resolve()):api.sha(__file__)},
       'inputs':{str(p):api.sha(p) for p in [qualified.DESIGN,ev,seal,Path(c['source'])]}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);verify(d)
    print('FROZEN',api.sha(DESIGN),flush=True)

def initial(d,c):
    cp=copy.deepcopy(api.read(c['source'])['result']['checkpoint']);bound=api.digest([d['binding'],c['id']])
    api.require(cp['state_sha256']==c['source_state_sha256']==api.digest(cp['state']),'source state')
    cp['contract']=engine.prior.contracts.expected_contract(c['spec'],bound)
    return cp,bound

def worker(name,segment):
    d=api.read(DESIGN);verify(d);qualified.old.prior.prior.configure();hot.warmup()
    c=next(c for c in d['cases'] if c['id']==name);cp,bound=initial(d,c)
    folder=RUN/name/f'segment_{segment:02d}';previous=None
    if segment>1:
        p=folder.parent/f'segment_{segment-1:02d}/record.json';r=api.read(p)
        api.require(api.read(p.parent/'completion.json')['record_sha256']==api.sha(p) and r['result']['status']=='incomplete_budget','previous segment')
        previous=api.sha(p);cp=r['result']['checkpoint']
    api.require(cp['state_sha256']==api.digest(cp['state']) and cp['contract']==engine.prior.contracts.expected_contract(c['spec'],bound),'checkpoint contract')
    folder.mkdir(parents=True,exist_ok=False)
    api.write(folder/'launch.json',{'pid':os.getpid(),'command':sys.argv,'design_sha256':api.sha(DESIGN)})
    try:
        with hot.scope(),qualified.scope(c['spec']):
            r,rows=engine.runtime.execute(c['spec'],bound,checkpoint=cp)
        health=engine.prior.reference.independent_health(r,c['spec']);verify(d)
        with gzip.open(folder/'intervals.json.gz','xb',compresslevel=1) as stream:
            stream.write(json.dumps(rows,sort_keys=True,allow_nan=False).encode())
        rec={'case':name,'segment':segment,'design_sha256':api.sha(DESIGN),'source_record_sha256':api.sha(c['source']),
             'previous_record_sha256':previous,'checkpoint_input_sha256':api.digest(cp),
             'result':r,'health':health,'candidate_work':dict(qualified.fast.work),'intervals_sha256':api.sha(folder/'intervals.json.gz')}
        api.write(folder/'record.json',rec,raw=True)
        api.write(folder/'completion.json',{'record_sha256':api.sha(folder/'record.json'),'launch_sha256':api.sha(folder/'launch.json')})
        okay=health['passed'] and r['status'] in ['incomplete_budget','present_at_horizon','full_window_exit']
        if not okay:api.write(folder/'failure.json',{'status':r['status'],'health':health,'reason':r.get('reason')})
        print(name,segment,r['status'],r['time_s'],'dwell',r['persistent_contact_observed'],'wall',r['runtime_seconds'],flush=True)
        return 0 if okay else 4
    except Exception as exc:
        if not (folder/'failure.json').exists():api.write(folder/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()})
        raise

def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'launch.json',{'pid':os.getpid(),'command':sys.argv,'design_sha256':api.sha(DESIGN)})
    start=time.perf_counter();ledger=[];failed=False
    for c in d['cases']:
        entry={'case':c['id'],'records':[],'status':'not_dispatched'}
        for segment in range(1,d['budget']['segments_per_case']+1):
            if failed or time.perf_counter()-start+60>d['budget']['stage_dispatch_s']:break
            stem=c['id']+f'_{segment:02d}'
            with (RUN/(stem+'.stdout.txt')).open('x') as stdout,(RUN/(stem+'.stderr.txt')).open('x') as stderr:
                child=subprocess.run([sys.executable,'-B','-u',__file__,'worker',c['id'],str(segment)],stdout=stdout,stderr=stderr)
            p=RUN/c['id']/f'segment_{segment:02d}/record.json'
            if p.exists():
                r=api.read(p)['result'];entry['records'].append({'path':str(p),'sha256':api.sha(p)});entry['status']=r['status']
                print(c['id'],segment,r['status'],r['time_s'],'dwell',r['persistent_contact_observed'],flush=True)
            if child.returncode:failed=True;break
            if entry['status']!='incomplete_budget':break
        ledger.append(entry)
    verify(d);api.write(RUN/'completion.json',{'design_sha256':api.sha(DESIGN),'ledger':ledger,'failed':failed,'dispatch_wall_s':time.perf_counter()-start})

def audit():
    d=api.read(DESIGN);verify(d);done=api.read(RUN/'completion.json');summaries=[];endpoints=[];artifacts={}
    api.require(done['design_sha256']==api.sha(DESIGN) and [e['case'] for e in done['ledger']]==[c['id'] for c in d['cases']],'dispatch binding/order')
    for c,e in zip(d['cases'],done['ledger']):
        cp,bound=initial(d,c);last_hash=None;maxdt=0.;healthy=True;all_supported=True;count=0;last=None
        start_x=api.np.array(cp['state']['x']);maxdrift=0.
        for segment,b in enumerate(e['records'],1):
            p=Path(b['path']);rec=api.read(p);seal=api.read(p.parent/'completion.json');r=rec['result']
            api.require(b['sha256']==api.sha(p)==seal['record_sha256'] and seal['launch_sha256']==api.sha(p.parent/'launch.json'),'record seal')
            api.require(rec['case']==c['id'] and rec['segment']==segment and rec['design_sha256']==api.sha(DESIGN),'case binding')
            api.require(rec['source_record_sha256']==api.sha(c['source']) and rec['previous_record_sha256']==last_hash and rec['checkpoint_input_sha256']==api.digest(cp),'source/chain binding')
            with gzip.open(p.parent/'intervals.json.gz','rb') as f:rows=json.load(f)
            api.require(rec['intervals_sha256']==api.sha(p.parent/'intervals.json.gz'),'interval binding')
            api.require(abs(sum(x['dt_s'] for x in rows)-(r['time_s']-cp['state']['t']))<1e-9,'elapsed integration closure')
            api.require(len(rows)==r['steps']-cp['state']['steps'] and all(x['dt_s']>0 for x in rows),'accepted step count')
            if rows:
                api.require(abs(rows[-1]['time_s']-r['time_s'])<1e-12 and rows[-1]['position_m']==r['position_m'],'endpoint closure')
                maxdt=max(maxdt,max(x['dt_s'] for x in rows));maxdrift=max(maxdrift,max(float(api.np.linalg.norm(api.np.array(x['position_m'])-start_x)) for x in rows))
                all_supported &= all(x['supported_bearing_ids']==[85,110,163] for x in rows)
            h=engine.prior.reference.independent_health(r,c['spec']);api.require(h==rec['health'],'independent health')
            healthy &= h['passed'];count+=len(rows);last=r
            cp=r['checkpoint'];api.require(cp['state_sha256']==api.digest(cp['state']) and cp['contract']==engine.prior.contracts.expected_contract(c['spec'],bound),'output state hash')
            last_hash=b['sha256']
        summary={'case':c['id'],'factor':c['factor'],'status':e['status'],'accepted_intervals':count,'health_passed':healthy and last is not None,
                 'all_intervals_same_supported_contacts':all_supported,'max_dt_s':maxdt,'max_drift_m':maxdrift,
                 'time_s':None if last is None else last['time_s'],'finite_dwell':False if last is None else last['persistent_contact_observed'],
                 'first_dwell_s':None if last is None else last['first_contact_dwell_time_s'],'dwell_not_absorbing':last is not None and not last['dwell_is_absorbing']}
        summaries.append(summary);endpoints.append(last)
    comparisons=[]
    if all(endpoints):
        for a,b,ca in zip(endpoints[:-1],endpoints[1:],d['cases'][:-1]):
            compare=qualified.old.prior.compare_results(a,b,ca['spec'],d['acceptance'])
            event=None if a['first_contact_dwell_time_s'] is None or b['first_contact_dwell_time_s'] is None else abs(a['first_contact_dwell_time_s']-b['first_contact_dwell_time_s'])
            compare['event_shift_s']=event;compare['event_passed']=event is not None and event<=2*max(s['max_dt_s'] for s in summaries)
            compare['passed'] &= compare['event_passed'];comparisons.append(compare)
    clean=not done['failed'] and not list(RUN.rglob('failure.json')) and not any(p.stat().st_size for p in RUN.glob('*.stderr.txt'))
    complete=all(s['status']=='present_at_horizon' and s['time_s']==1.3 for s in summaries)
    passed=complete and clean and all(s['health_passed'] and s['all_intervals_same_supported_contacts'] and s['finite_dwell'] and s['dwell_not_absorbing'] for s in summaries) and len(comparisons)==2 and all(c['passed'] for c in comparisons)
    for p in RUN.rglob('*'):
        if p.is_file():artifacts[str(p)]=api.sha(p)
    OUT.mkdir(parents=True,exist_ok=False)
    result={'passed':passed,'all_queries_complete':complete,'no_failure_or_stderr':clean,'rows':summaries,'comparisons':comparisons,
            'source_checkpoint_artifact_audit_passed':True,'population_release_fraction':None,'artifacts':artifacts,
            'claim':d['claim_boundary']}
    api.write(OUT/'results.json',result);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'design_sha256':api.sha(DESIGN)})
    print({k:v for k,v in result.items() if k!='artifacts'},flush=True)

if __name__=='__main__':
    action=sys.argv[1]
    if action=='prepare':prepare()
    elif action=='run':run()
    elif action=='worker':raise SystemExit(worker(sys.argv[2],int(sys.argv[3])))
    elif action=='audit':audit()
    else:raise ValueError(action)
