"""Seal passes, preserved failures and validation limitations without conflation."""
from pathlib import Path
import sys
import json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage122_staging'))
import refine_spheres_v1 as current
api=current.api;old=current.previous
def files(roots):return {str(p.resolve()):api.sha(p) for root in roots for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
def check_eval(job):
    job.verify(api.read(job.DESIGN));r=api.read(job.EVAL/'independent_evaluation_01/results.json')
    comp=api.read(job.EVAL/'independent_evaluation_01/completion.json')
    api.require(comp['results_sha256']==api.sha(job.EVAL/'independent_evaluation_01/results.json'),'evaluation digest drift')
    api.verify_mapping(r['artifacts']);return r
def check_figure(folder,name):
    qa=api.read(folder/'visual_qa.json');api.require(qa['passed'] and qa['figure_sha256']==api.sha(folder/name),'visual QA drift')
    api.verify_mapping(api.read(folder/'manifest.json')['artifacts'])
def main():
    a=check_eval(old);b=check_eval(current)
    api.require(not a['passed'] and b['passed'],'historical/refined distinction lost')
    api.require(all(v['qualified'] for v in a['ledger']+b['ledger']),'unhealthy trajectory')
    groups=[b['groups'][0],a['groups'][1],b['groups'][1],a['groups'][3]]
    api.require(all(g['passed'] for g in groups),'latest groups failed')
    repeats=[]
    for cpd in [2,4]:
        def record(job,prefix):return api.read(job.RUN/f'{prefix}_s2_sphere_f1p0_cpd{cpd}_dt4_h0p5'/'segment_01/record.json')['result']
        x,y=record(old,'fresh'),record(current,'refined')
        state_keys=['time_s','position_m','velocity_generalized','status']
        same={k:x[k]==y[k] for k in state_keys}
        same['complete_checkpoint_state']=x['checkpoint']['state']==y['checkpoint']['state']
        api.require(all(same.values()),'repeated quarter-cap physical state changed');repeats.append({'cpd':cpd,'checks':same})
    check_figure(current.EVAL/'render_03','matched_resolution.png')
    first={'status':'completed_healthy_but_two_coarse_sphere_triplets_failed','passed':False,'qualified_cases':12,'passed_triplets':2,
       'artifacts':files([ROOT/'stage121_staging',old.DESIGN.parent,old.RUN,old.EVAL])}
    api.write(old.EVAL/'completion.json',first)
    second={'status':'updated_seed2_timestep_groups_verified_spatial_open','passed':True,'qualified_new_cases':6,'latest_passing_triplets':4,
      'repeat_state_checks':repeats,'stage121_failure_seal_sha256':api.sha(old.EVAL/'completion.json'),
      'spatial_convergence_established':False,'full_horizon_convergence_established':False,'physical_validation_claimed':False,
      'artifacts':files([ROOT/'stage122_staging',current.DESIGN.parent,current.RUN,current.EVAL])}
    api.write(current.EVAL/'completion.json',second)
    base=ROOT/'stage123_evaluations/literature_validation_20260916';audit=api.read(base/'audit_01/results.json')
    acomp=api.read(base/'audit_01/completion.json');api.verify_mapping(acomp['artifacts']);api.verify_mapping(audit['members'])
    api.require(api.sha(ROOT/'stage123_literature/fouty_2024_20260916/MPF_Plots.tar.gz')==audit['source']['archive_sha256'],'archive drift')
    api.require(audit['data_extraction_passed'] and not audit['empirical_model_validation_passed'] and not audit['calibration_performed'],'invalid validation claim')
    check_figure(base/'render_01','experimental_fibre_curves.png')
    final={'status':'validation_assessed_but_not_established','data_extraction_passed':True,'empirical_validation_passed':False,
       'matched_validation_score':None,'calibration_performed':False,'physical_parameters_changed':False,'large_population_launched':False,
       'numerical_seal_sha256':api.sha(current.EVAL/'completion.json'),
       'blockers':['Spatial and full-path response qualification incomplete','Experimental geometry/forcing/initialization/event definitions do not match the present matrix-release model','Recovered archive and article median contrast disagree'],
       'artifacts':files([ROOT/'stage123_staging',ROOT/'stage123_literature',base])}
    api.write(base/'completion.json',final)
    print('SEALED: Stage121 failure retained; Stage122 latest timestep pass; Stage123 validation NOT established')
    print('repeat checks',repeats)
if __name__=='__main__':main()
