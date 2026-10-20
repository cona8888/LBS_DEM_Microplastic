"""Unchanged repaired solver; fresh seed-2 CPD2/CPD4 paired sentinels."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage120_staging'))
import repair_regression_v1 as engine
api,local,runtime,prior=engine.api,engine.local,engine.runtime,engine.prior
BASE='matched_seed2_resolution_20260916'
DESIGN=ROOT/'stage121_designs'/BASE/'design_01.json'
RUN=ROOT/'stage121_runs'/BASE/'sentinels_01'
EVAL=ROOT/'stage121_evaluations'/BASE
SEAL=engine.EVAL/'completion.json'


def prepare():
    seal=api.read(SEAL);api.verify_mapping(seal['artifacts'])
    api.require(seal['trajectory_regression_passed'],'repair trajectory qualification missing')
    old=api.read(prior.DESIGN)
    specs=[s for s in old['cases'] if s['seed']==2]
    cases=[{'id':'fresh_'+s['case_id'],'spec':s,'source_checkpoint':None,'initial_state_sha256':api.digest(s['initial_state'])} for s in specs]
    groups=[]
    for cpd in [2,4]:
        for shape in api.SHAPES:
            groups.append({'name':f'CPD{cpd}_{shape}','ids':[c['id'] for c in cases if c['spec']['cpd']==cpd and c['spec']['shape']==shape]})
    paths=[Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents]
    paths+=list(Path(__file__).parent.glob('*.py'))
    d={'stage':'Stage121','cases':cases,'groups':groups,'physical_changes':[],'numerical_changes':[],
       'acceptance':old['acceptance'],'event_acceptance':old['event_acceptance'],
       'budget':{'segment_s':45,'max_segments_per_case':3,'stage_wall_s':1800,'stop_on_numerical_failure':True},
       'scope':'Twelve fresh seed-2 CPD2/CPD4 sphere/AR4 sentinels at 0.5 seconds; three timestep levels each. Numerical verification only.',
       'spatial_policy':'Report finest-level matched-nominal-flow CPD2/CPD4 differences separately, retaining each achieved SI speed. Two spatial levels are sensitivity evidence, not asymptotic spatial convergence. No population or empirical validation follows automatically.',
       'source_hashes':{str(p):api.sha(p) for p in paths},'inputs':{str(SEAL):api.sha(SEAL),str(prior.DESIGN):api.sha(prior.DESIGN)}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    verify(d);print('FROZEN',api.sha(DESIGN),'cases',len(cases),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design self-binding drift')
    api.verify_mapping(d['source_hashes']);api.verify_mapping(d['inputs']);api.verify_mapping(api.read(SEAL)['artifacts'])
    local.verify(api.read(local.DESIGN));old=api.read(prior.DESIGN)
    expected=[s for s in old['cases'] if s['seed']==2]
    api.require([c['spec'] for c in d['cases']]==expected and len(expected)==12,'frozen case set drift')
    api.require(d['physical_changes']==[] and d['numerical_changes']==[],'model changed')
    for c in d['cases']:
        api.require(c['source_checkpoint'] is None and c['initial_state_sha256']==api.digest(c['spec']['initial_state']),'fresh initial state drift')
    for shape in api.SHAPES:
        states=[s['initial_state'] for s in expected if s['shape']==shape]
        api.require(all(s==states[0] for s in states),'unpaired CPD starts')


binding=engine.binding


def configure():
    engine.DESIGN,engine.RUN,engine.EVAL=DESIGN,RUN,EVAL
    engine.verify=verify


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    else:
        configure()
        # Old dispatch uses its own __file__ for worker commands; the current
        # wrapper is the explicit executable entry point for this new design.
        engine.__file__=str(Path(__file__).resolve())
        if sys.argv[1]=='run':raise SystemExit(engine.run())
        else:raise SystemExit(engine.worker(sys.argv[2],int(sys.argv[3])))
