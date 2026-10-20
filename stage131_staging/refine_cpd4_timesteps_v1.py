"""Stage131: one finer CPD4 time level for sphere and AR4 response budgets."""
from pathlib import Path
import copy,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'stage122_staging'));import refine_spheres_v1 as prior
engine=prior.engine;api=prior.api
BASE='cpd4_timestep_refinement_20260916';DESIGN=ROOT/'stage131_designs'/BASE/'design_01.json';RUN=ROOT/'stage131_runs'/BASE/'sentinels_01';EVAL=ROOT/'stage131_evaluations'/BASE
SEAL130=ROOT/'stage130_evaluations/cpd6_final_stationarity_20260916/completion.json';R121=ROOT/'stage121_evaluations/matched_seed2_resolution_20260916/independent_evaluation_01/results.json';R122=ROOT/'stage122_evaluations/sphere_timestep_refinement_20260916/independent_evaluation_01/results.json'
def expected_cases():
 d121=api.read(prior.previous.DESIGN);d122=api.read(prior.DESIGN);cases=[]
 sphere=next(c['spec'] for c in d122['cases'] if c['spec']['cpd']==4 and c['spec']['shape']==api.SHAPES[0] and c['spec']['refinement']==.0625)
 fibre=next(c['spec'] for c in d121['cases'] if c['spec']['cpd']==4 and c['spec']['shape']==api.SHAPES[1] and c['spec']['refinement']==.125)
 for base,level,label in [(sphere,.03125,'sphere_dt32'),(fibre,.0625,'ar4_dt16')]:
  s=copy.deepcopy(base);ratio=level/base['refinement'];s['refinement']=level
  for k in api.DT_CONTROLS:s['config']['numerics'][k]*=ratio
  s['case_id']=f"s2_{label}_f1p0_cpd4_h0p5";cases.append({'id':'refined_'+s['case_id'],'spec':s,'source_checkpoint':None,'initial_state_sha256':api.digest(s['initial_state'])})
 return cases
def verify(d):
 api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'binding drift');api.verify_mapping(d['source_hashes']);api.verify_mapping(d['inputs']);api.require(d['cases']==expected_cases() and d['physical_changes']==[],'case drift');api.require(d['acceptance']==api.read(prior.DESIGN)['acceptance'],'threshold drift')
def prepare():
 for p in [SEAL130,R121,R122]:
  x=api.read(p);api.verify_mapping(x['artifacts']) if 'artifacts' in x else None
 api.require(api.read(SEAL130)['qualified'],'CPD6 flow not qualified');cases=expected_cases();sources=[Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents]+list(Path(__file__).parent.glob('*.py'));inputs=[SEAL130,R121,R122,prior.DESIGN,prior.previous.DESIGN]
 d={'stage':'Stage131','cases':cases,'groups':[{'name':'CPD4_finer_time_levels','ids':[c['id'] for c in cases]}],'physical_changes':[],'numerical_changes':['Add only sphere dt32 and AR4 dt16 levels; all four timestep controls halved together.'],'acceptance':api.read(prior.DESIGN)['acceptance'],'event_acceptance':api.read(prior.DESIGN)['event_acceptance'],'budget':{'segment_s':45,'max_segments_per_case':3,'stage_wall_s':300,'stop_on_numerical_failure':True},'scope':'Two fresh seed-2 CPD4 0.5-s trajectories; numerical refinement only.','source_hashes':{str(p):api.sha(p) for p in sources},'inputs':{str(p):api.sha(p) for p in inputs}};d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True);api.write(DESIGN,d);verify(d);print('FROZEN',api.sha(DESIGN),'cases',len(cases))
def configure():engine.DESIGN,engine.RUN,engine.EVAL=DESIGN,RUN,EVAL;engine.verify=verify;engine.__file__=str(Path(__file__).resolve())
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 else:
  configure();raise SystemExit(engine.run() if sys.argv[1]=='run' else engine.worker(sys.argv[2],int(sys.argv[3])))
