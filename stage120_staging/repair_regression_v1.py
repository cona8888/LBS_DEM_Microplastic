"""Bounded failed-episode and fresh paired-sentinel regression, no population."""
from pathlib import Path
import copy
import os
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage119_staging'),str(ROOT/'stage117_staging')]
import verify_repair_v3 as local
runtime=local.runtime
api=local.api
prior=runtime.previous
BASE='repaired_paired_sentinels_20260916'
DESIGN=ROOT/'stage120_designs'/BASE/'design_01.json'
RUN=ROOT/'stage120_runs'/BASE/'regression_01'
EVAL=ROOT/'stage120_evaluations'/BASE
CHECKPOINT_SOURCE=local.probe.FAILED.parent.parent/'segment_01/record.json'


def prepare():
    local.verify(api.read(local.DESIGN))
    outcome=api.read(local.OUT/'results.json')
    api.require(outcome['passed'],'local repair not verified')
    api.verify_mapping(outcome['artifacts'])
    old=api.read(prior.DESIGN)
    fibre=next(s for s in old['cases'] if s['case_id']==local.probe.CASE)
    sphere=[s for s in old['cases'] if s['seed']==1 and s['shape']==api.SHAPES[0]]
    fibres=[s for s in old['cases'] if s['seed']==1 and s['shape']==api.SHAPES[1]]
    cp=api.read(CHECKPOINT_SOURCE)['result']['checkpoint']
    api.require(cp['state_sha256']==api.digest(cp['state']) and cp['contract']==prior.contracts.expected_contract(fibre,prior.binding(old,fibre['case_id'])),'source checkpoint mismatch')
    cases=[]
    for s in fibres:
        cases.append({'id':'episode_'+s['case_id'],'spec':s,'source_checkpoint':str(CHECKPOINT_SOURCE),'initial_state_sha256':cp['state_sha256']})
    for s in sphere+fibres:
        cases.append({'id':'fresh_'+s['case_id'],'spec':s,'source_checkpoint':None,'initial_state_sha256':api.digest(s['initial_state'])})
    paths=[Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents]
    paths+=list(Path(__file__).parent.glob('*.py'))
    d={'stage':'Stage120','cases':cases,'groups':[{'name':'saved_fibre_episode','ids':[x['id'] for x in cases[:3]]},
            {'name':'fresh_sphere','ids':[x['id'] for x in cases[3:6]]},{'name':'fresh_fibre','ids':[x['id'] for x in cases[6:]]}],
       'physical_changes':[],'numerical_changes':['failure-only Stage119 contact repair','budget checkpoint before adaptive trials','explicit rejected-trial reasons'],
       'acceptance':old['acceptance'],'event_acceptance':old['event_acceptance'],
       'checkpoint_migration':'Explicit source-bound numerical-version boundary: copy the entire Stage117 accepted segment-01 state exactly; replace only the contract digest with each declared case binding and caps. These three runs are local-episode regressions, not fresh-start full-path convergence.',
       'budget':{'segment_s':45,'max_segments_per_case':3,'stage_wall_s':900,'stop_on_numerical_failure':True},
       'scope':'Nine bounded numerical regressions at the same 0.5-second endpoint. No population release, physical validation, new geometry, new flow or physics.',
       'source_hashes':{str(p):api.sha(p) for p in paths},
       'inputs':{str(local.DESIGN):api.sha(local.DESIGN),str(local.OUT/'results.json'):api.sha(local.OUT/'results.json'),str(local.OUT/'completion.json'):api.sha(local.OUT/'completion.json'),str(CHECKPOINT_SOURCE):api.sha(CHECKPOINT_SOURCE),str(prior.DESIGN):api.sha(prior.DESIGN)}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),'cases',len(cases),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design self-binding drift')
    api.verify_mapping(d['source_hashes']);api.verify_mapping(d['inputs'])
    local.verify(api.read(local.DESIGN));api.require(api.read(local.OUT/'results.json')['passed'],'local qualification missing')
    api.verify_mapping(api.read(local.OUT/'results.json')['artifacts'])
    old=api.read(prior.DESIGN)
    for c in d['cases']:
        api.require(c['spec'] in old['cases'] and c['spec']['seed']==1 and c['spec']['horizon_s']==.5,'physical or query drift')
    api.require(len(d['cases'])==9 and d['physical_changes']==[],'case matrix drift')


def binding(d,c):return api.digest([d['binding'],c['id']])


def worker(name,segment):
    d=api.read(DESIGN);verify(d);case=next(c for c in d['cases'] if c['id']==name)
    spec=case['spec'];bound=binding(d,case);cp=None;prior_hash=None;migration=None
    out=RUN/name/f'segment_{segment:02d}';api.require(1<=segment<=3,'segment limit')
    if segment>1:
        path=out.parent/f'segment_{segment-1:02d}/record.json';prior_hash=api.sha(path)
        record=api.read(path);api.require(api.read(path.parent/'completion.json')['record_sha256']==prior_hash,'prior record drift')
        api.require(record['result']['status']=='incomplete_budget','invalid restart');cp=record['result']['checkpoint']
    elif case['source_checkpoint']:
        source=api.read(case['source_checkpoint'])['result']['checkpoint']
        cp=copy.deepcopy(source);cp['contract']=prior.contracts.expected_contract(spec,bound)
        api.require(cp['state_sha256']==case['initial_state_sha256']==api.digest(cp['state']),'migration altered source state')
        migration={'source_record_sha256':api.sha(case['source_checkpoint']),'source_contract':source['contract'],'new_contract':cp['contract'],'exact_state_preserved':cp['state']==source['state']}
    if cp:api.require(cp['contract']==prior.contracts.expected_contract(spec,bound) and cp['state_sha256']==api.digest(cp['state']),'checkpoint integrity mismatch')
    out.mkdir(parents=True,exist_ok=False)
    api.write(out/'launch.json',{'pid':os.getpid(),'command':sys.argv,'python':sys.version,'design_sha256':api.sha(DESIGN),'case_id':name,'segment':segment,'prior_record_sha256':prior_hash})
    try:
        r,rows=runtime.execute(spec,bound,checkpoint=cp)
        verify(d);api.write(out/'accepted_intervals.json',rows,raw=True)
        record={'case_id':name,'segment':segment,'design_sha256':api.sha(DESIGN),'prior_record_sha256':prior_hash,
            'checkpoint_input_sha256':None if cp is None else api.digest(cp),'migration':migration,'result':r,'accepted_intervals_sha256':api.sha(out/'accepted_intervals.json')}
        api.write(out/'record.json',record,raw=True)
        api.write(out/'completion.json',{'record_sha256':api.sha(out/'record.json'),'launch_sha256':api.sha(out/'launch.json'),'status':r['status']})
        okay=r['status'] in ['present_at_horizon','incomplete_budget','full_window_exit'] and prior.reference.independent_health(r,spec)['passed']
        if not okay:api.write(out/'failure.json',{'status':r['status'],'reason':r['reason']})
        print(name,segment,r['status'],r['time_s'],'wall_s',r['runtime_seconds'],'repair_calls',len(r['stage119_repair_calls']),flush=True)
        return 0 if okay else 4
    except Exception as exc:
        if not (out/'failure.json').exists():api.write(out/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()})
        raise


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'manifest.json',{'design_sha256':api.sha(DESIGN),'case_order':[c['id'] for c in d['cases']],'pid':os.getpid(),'command':sys.argv})
    started=time.perf_counter();ledger=[];stopped=False
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    for c in d['cases']:
        if stopped or time.perf_counter()-started>d['budget']['stage_wall_s']:
            ledger.append({'case_id':c['id'],'status':'not_run'});continue
        for segment in range(1,4):
            stem=c['id']+f'_{segment:02d}'
            with (RUN/(stem+'.stdout.txt')).open('x') as stdout,(RUN/(stem+'.stderr.txt')).open('x') as stderr:
                child=subprocess.run([sys.executable,'-B','-u',__file__,'worker',c['id'],str(segment)],stdout=stdout,stderr=stderr,env=env)
            path=RUN/c['id']/f'segment_{segment:02d}/record.json'
            if not path.exists():
                stopped=True;ledger.append({'case_id':c['id'],'status':'worker_failure','returncode':child.returncode});break
            r=api.read(path)['result'];print(c['id'],segment,r['status'],round(r['time_s'],10),round(r['runtime_seconds'],3),flush=True)
            if child.returncode or r['status']!='incomplete_budget' or segment==3:
                ledger.append({'case_id':c['id'],'status':r['status'],'last_record':str(path),'record_sha256':api.sha(path),'segments':segment})
                stopped=child.returncode!=0;break
            if time.perf_counter()-started>d['budget']['stage_wall_s']:
                ledger.append({'case_id':c['id'],'status':r['status'],'last_record':str(path),'record_sha256':api.sha(path),'segments':segment});break
    verify(d)
    api.write(RUN/'completion.json',{'design_sha256':api.sha(DESIGN),'manifest_sha256':api.sha(RUN/'manifest.json'),'ledger':ledger,'wall_s':time.perf_counter()-started,'stopped_on_failure':stopped})
    print('DISPATCH_COMPLETE',not stopped,'wall_s',time.perf_counter()-started,flush=True)
    return 4 if stopped else 0


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':raise SystemExit(run())
    else:raise SystemExit(worker(sys.argv[2],int(sys.argv[3])))
