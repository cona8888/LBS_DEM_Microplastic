"""Source-bound, eight-step CPU profiles; never replace accepted checkpoints."""
from pathlib import Path
import copy
import cProfile
import os
import pstats
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage136_staging'))
import qualify_and_continue_v1 as prior
api, engine, hot = prior.api, prior.engine, prior.hot
BASE = 'remaining_cost_diagnosis_20260918'
DESIGN = ROOT/'stage137_designs'/BASE/'design_01.json'
OUT = ROOT/'stage137_evaluations'/BASE/'profile_01'


def verify(d):
    api.require(d['binding'] == api.digest({k:v for k,v in d.items() if k!='binding'}), 'design hash')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    prior.verify(api.read(prior.DESIGN))


def prepare():
    pd=api.read(prior.DESIGN); prior.verify(pd)
    evidence=prior.EVAL/'independent_evaluation_01/results.json'
    seal=evidence.parent/'completion.json'
    ev=api.read(evidence)
    api.require(api.read(seal)['results_sha256']==api.sha(evidence), 'prior seal')
    api.require(ev['source_checkpoint_artifact_audit_passed'] and ev['all_health_passed'] and ev['no_failure_or_stderr'], 'prior audit')
    api.verify_mapping(ev['artifacts'])
    inputs={str(p):api.sha(p) for p in [prior.DESIGN,evidence,seal]}
    cases=[]
    for name,segment in [('sphere_12',4),('fibre_11',3)]:
        c=next(c for c in pd['cases'] if c['id']==name)
        p=prior.RUN/'continuation_01'/name/f'segment_{segment:02d}/record.json'
        r=api.read(p)
        api.require(api.read(p.parent/'completion.json')['record_sha256']==api.sha(p), 'source record seal')
        cases.append({'id':name, 'source':str(p), 'spec':c['spec'], 'source_state_sha256':r['result']['checkpoint']['state_sha256']})
        inputs[str(p)]=api.sha(p)
    d={'stage':'Stage137','physical_changes':[], 'question':'Where is the remaining cost after compiled contact sweeps?',
       'cases':cases,'accepted_steps_per_profile':8,
       'acceptance':{'required_status':'paused_checkpoint','inherited_health':True,'checkpoint_and_artifact_hashes':True},
       'scope':'Observational eight-step replays only. No equilibrium holds, no skipped time, no promoted trajectory or retention/release claims.',
       'budget':'Two sequential 45-second cooperative integration budgets; inner solve may overshoot. No other simulation or GPU job.',
       'sources':{str(Path(__file__).resolve()):api.sha(__file__)},'inputs':inputs}
    d['binding']=api.digest(d); DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def run():
    d=api.read(DESIGN);verify(d);prior.prior.configure()
    OUT.mkdir(parents=True,exist_ok=False)
    api.write(OUT/'launch.json',{'pid':os.getpid(),'command':sys.argv,'design_sha256':api.sha(DESIGN)})
    hot.warmup();ledger=[]
    for c in d['cases']:
        cp=copy.deepcopy(api.read(c['source'])['result']['checkpoint'])
        api.require(cp['state_sha256']==c['source_state_sha256']==api.digest(cp['state']),'source state')
        bound=api.digest([d['binding'],c['id']])
        cp['contract']=engine.prior.contracts.expected_contract(c['spec'],bound)
        trace=[];profile=cProfile.Profile()
        with hot.scope(),prior.capture(trace):
            profile.enable()
            try:r,intervals=engine.runtime.execute(c['spec'],bound,checkpoint=cp,pause=cp['state']['steps']+d['accepted_steps_per_profile'])
            finally:profile.disable()
        stats=pstats.Stats(profile)
        rows=[{'file':key[0],'line':key[1],'function':key[2], 'primitive_calls':v[0],'total_calls':v[1],'self_s':v[2],'cumulative_s':v[3]} for key,v in stats.stats.items()]
        rows.sort(key=lambda row:row['cumulative_s'],reverse=True)
        health=engine.prior.reference.independent_health(r,c['spec'])
        passed=health['passed'] and r['status']=='paused_checkpoint' and len(intervals)==d['accepted_steps_per_profile']
        api.write(OUT/(c['id']+'_trace.json'),trace,raw=True)
        api.write(OUT/(c['id']+'_profile.json'),rows)
        record={'case_id':c['id'],'design_sha256':api.sha(DESIGN),'source_record_sha256':api.sha(c['source']),
                'checkpoint_input_sha256':api.digest(cp),'result':r,'intervals':intervals,'health':health,'passed':passed,
                'profile_sha256':api.sha(OUT/(c['id']+'_profile.json')),'trace_sha256':api.sha(OUT/(c['id']+'_trace.json'))}
        api.write(OUT/(c['id']+'_record.json'),record,raw=True)
        ledger.append({'case':c['id'],'passed':passed,'integration_s':r['runtime_seconds'],'trace_calls':len(trace),'top_profile':rows[:15]})
        print(c['id'],passed,r['runtime_seconds'],flush=True)
        if not passed:break
    verify(d)
    artifacts={str(p):api.sha(p) for p in OUT.iterdir() if p.is_file()}
    result={'passed':len(ledger)==2 and all(x['passed'] for x in ledger),'rows':ledger,'artifacts':artifacts,
            'claim':'Timing diagnosis on saved states only; profiling overhead included, no trajectory promotion.'}
    api.write(OUT/'results.json',result)
    api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'design_sha256':api.sha(DESIGN)})


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
    else:raise ValueError(sys.argv[1])
