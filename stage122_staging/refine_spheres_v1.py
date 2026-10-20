"""Prospective smaller timestep caps for the two failed sphere triplets."""
from pathlib import Path
import copy
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage121_staging'))
import matched_resolution_v1 as previous
engine=previous.engine
api,local,runtime,prior=previous.api,previous.local,previous.runtime,previous.prior
BASE='sphere_timestep_refinement_20260916'
DESIGN=ROOT/'stage122_designs'/BASE/'design_01.json'
RUN=ROOT/'stage122_runs'/BASE/'sentinels_01'
EVAL=ROOT/'stage122_evaluations'/BASE
PRESULT=previous.EVAL/'independent_evaluation_01/results.json'

def expected_cases():
    old=api.read(previous.DESIGN);cases=[]
    for cpd in [2,4]:
        base=next(c['spec'] for c in old['cases'] if c['spec']['cpd']==cpd and c['spec']['shape']==api.SHAPES[0] and c['spec']['refinement']==1.)
        for level in [.25,.125,.0625]:
            s=copy.deepcopy(base)
            s['refinement']=level;s['case_id']=f's2_sphere_f1p0_cpd{cpd}_dt{round(1/level)}_h0p5'
            for key in api.DT_CONTROLS:s['config']['numerics'][key]*=level
            cases.append({'id':'refined_'+s['case_id'],'spec':s,'source_checkpoint':None,'initial_state_sha256':api.digest(s['initial_state'])})
    return cases

def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'binding drift')
    api.verify_mapping(d['source_hashes']);api.verify_mapping(d['inputs'])
    previous.verify(api.read(previous.DESIGN));api.verify_mapping(api.read(PRESULT)['artifacts'])
    api.require(d['cases']==expected_cases() and d['physical_changes']==[],'physics or case drift')
    api.require(d['acceptance']==api.read(previous.DESIGN)['acceptance'],'threshold drift')

def prepare():
    previous.verify(api.read(previous.DESIGN));r=api.read(PRESULT)
    api.verify_mapping(r['artifacts']);api.require(r['no_failure_or_stderr'] and all(v['qualified'] for v in r['ledger']),'unhealthy predecessor')
    cases=expected_cases();old=api.read(previous.DESIGN)
    sources=[Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents]
    sources+=list(Path(__file__).parent.glob('*.py'))
    inputs=[previous.DESIGN,PRESULT,previous.EVAL/'independent_evaluation_01/completion.json',previous.RUN/'completion.json']
    d={'stage':'Stage122','cases':cases,'groups':[{'name':f'CPD{cpd}_{api.SHAPES[0]}','ids':[c['id'] for c in cases if c['spec']['cpd']==cpd]} for cpd in [2,4]],
       'physical_changes':[],'numerical_changes':['Refine all four timestep controls together to 1/4, 1/8 and 1/16 of the Stage121 sphere base caps; fresh starts.'],
       'acceptance':old['acceptance'],'event_acceptance':old['event_acceptance'],
       'budget':{'segment_s':45,'max_segments_per_case':3,'stage_wall_s':600,'stop_on_numerical_failure':True},
       'scope':'Six fresh seed-2 sphere trajectories to 0.5 s; only timestep caps change. Stage121 failed convergence evidence retained.',
       'source_hashes':{str(p):api.sha(p) for p in sources},'inputs':{str(p):api.sha(p) for p in inputs}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);verify(d)
    print('FROZEN',api.sha(DESIGN),flush=True)

binding=engine.binding
def configure():
    engine.DESIGN,engine.RUN,engine.EVAL=DESIGN,RUN,EVAL
    engine.verify=verify;engine.__file__=str(Path(__file__).resolve())

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    else:
        configure()
        if sys.argv[1]=='run':raise SystemExit(engine.run())
        else:raise SystemExit(engine.worker(sys.argv[2],int(sys.argv[3])))
