"""Explicit counterfactual amplitude diagnostic; not a new physical flow solution."""
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
import copy
import hashlib
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage122_staging'))
import refine_spheres_v1 as previous
api,prior,local=previous.api,previous.prior,previous.local
engine=previous.engine
repaired=previous.runtime
BASE='mean_offset_attribution_20260916'
DESIGN=ROOT/'stage124_designs'/BASE/'design_01.json'
RUN=ROOT/'stage124_runs'/BASE/'diagnostic_01'
EVAL=ROOT/'stage124_evaluations'/BASE
PREFLIGHT=EVAL/'preflight_01/results.json'
ORIGINAL_LOAD=api.fields.load

def inherited_cases():
    sphere=api.read(previous.DESIGN)['cases']
    fibre=api.read(previous.previous.DESIGN)['cases']
    return [c for c in sphere if c['spec']['cpd']==2]+[c for c in fibre if c['spec']['cpd']==2 and c['spec']['shape']==api.SHAPES[1]]

def diagnostic_load(seed,factor=1.,cpd=2,**kwargs):
    api.require((seed,factor,cpd)==(2,1.,2) and not kwargs,'only frozen seed-2 CPD2 diagnostic supported')
    field,g,m=ORIGINAL_LOAD(seed,factor,cpd)
    _,_,m4=ORIGINAL_LOAD(2,1.,4)
    scale=m4['achieved_mean_interstitial_velocity_m_s']/m['achieved_mean_interstitial_velocity_m_s']
    api.require(.99<scale<1.01,'amplitude diagnostic outside one-percent domain')
    before=hashlib.sha256(field.u.tobytes()).hexdigest()
    normalized_field=api.fields.wall_field_v1.WallCellField(field.u.copy()*scale,field.dx,field.fluid.copy())
    api.require(hashlib.sha256(field.u.tobytes()).hexdigest()==before,'source field changed')
    meta=copy.deepcopy(m)
    meta.update(achieved_mean_interstitial_velocity_m_s=m4['achieved_mean_interstitial_velocity_m_s'],
                pv_per_second=m4['achieved_mean_interstitial_velocity_m_s']/m['cell_length_m'],
                two_pore_volume_horizon_s=2*m['cell_length_m']/m4['achieved_mean_interstitial_velocity_m_s'],
                normalization_to_target_applied=True,particle_transport_authorized=False,
                limitation='Counterfactual prescribed-field amplitude sensitivity only. No new Navier-Stokes/LBM solution, flow-scaling validation, grid convergence or population authorization.')
    meta['stage124_diagnostic']={'scale':scale,'unscaled_metadata_sha256':api.digest(m),'reference_metadata_sha256':api.digest(m4),
        'unscaled_velocity_array_sha256':before,'scaled_velocity_array_sha256':hashlib.sha256(normalized_field.u.tobytes()).hexdigest(),
        'adapter_sha256':api.sha(__file__),'reference_field':m4['field'],'role':'mean_speed_offset_attribution_only'}
    return normalized_field,g,meta

@contextmanager
def loader_scope(loader=diagnostic_load):
    old=api.fields.load
    api.require(old is ORIGINAL_LOAD,'unexpected nested loader patch')
    api.fields.load=loader
    try:yield
    finally:api.fields.load=old

def execute(spec,binding,checkpoint=None,pause=None,observe=True):
    api.require(spec.get('diagnostic_role')=='mean_speed_offset_attribution_only','diagnostic opt-in missing')
    with loader_scope():
        return repaired.execute(spec,binding,checkpoint=checkpoint,pause=pause,observe=observe)

def expected_cases():
    _,_,meta=diagnostic_load(2,1.,2);cases=[]
    for original in inherited_cases():
        s=copy.deepcopy(original['spec']);s['case_id']='amplitude_'+s['case_id']
        s['diagnostic_role']='mean_speed_offset_attribution_only'
        s['field_metadata']=meta
        s['config']['target_mean_interstitial_velocity_m_s']=meta['achieved_mean_interstitial_velocity_m_s']
        s['horizon_pv']=s['horizon_s']*meta['pv_per_second']
        cases.append({'id':s['case_id'],'spec':s,'source_checkpoint':None,'initial_state_sha256':api.digest(s['initial_state'])})
    return cases

def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding drift')
    api.verify_mapping(d['source_hashes']);api.verify_mapping(d['inputs'])
    previous.verify(api.read(previous.DESIGN))
    for seal in [previous.EVAL/'completion.json',previous.previous.EVAL/'completion.json']:
        api.verify_mapping(api.read(seal)['artifacts'])
    api.require(d['cases']==expected_cases() and len(d['cases'])==6,'case or physical drift')
    api.require(d['acceptance']==api.read(previous.DESIGN)['acceptance'],'temporal gate drift')

def execution_verify(d):
    verify(d);p=api.read(PREFLIGHT)
    api.require(p['passed'] and p['design_sha256']==api.sha(DESIGN),'missing bound preflight')
    api.require(api.read(PREFLIGHT.parent/'completion.json')['results_sha256']==api.sha(PREFLIGHT),'preflight digest drift')

def prepare():
    previous.verify(api.read(previous.DESIGN));old=api.read(previous.DESIGN);cases=expected_cases()
    sources=[Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents]
    sources+=list(Path(__file__).parent.glob('*.py'))
    inputs=[previous.DESIGN,previous.EVAL/'completion.json',previous.previous.DESIGN,previous.previous.EVAL/'completion.json']
    d={'stage':'Stage124','question':'Can the achieved mean-speed mismatch alone explain the CPD2/CPD4 short-time response discrepancy?',
       'cases':cases,'groups':[{'name':f'CPD2_{shape}','ids':[c['id'] for c in cases if c['spec']['shape']==shape]} for shape in api.SHAPES],
       'acceptance':old['acceptance'],'event_acceptance':old['event_acceptance'],
       'physical_model_changes':[],'prescribed_forcing_change':'Multiply the entire CPD2 field, including all components/gradients, by U4/U2. Preserve mask, interpolation, geometry, fluid and particle laws. This is a counterfactual sensitivity, not a verified new physical flow.',
       'budget':{'segment_s':45,'max_segments_per_case':3,'stage_wall_s':900,'stop_on_numerical_failure':True},
       'attribution':{'query_s':.5,'fixed_scale':'Position/minor radius; velocity/max(norm(CPD4 finest velocity), achieved U4); apolar axis in radians.',
           'noise_proxy_multiplier':2.,'decision':'Remainder lower proxy > amplitude upper proxy. Each proxy uses twice adjacent medium/fine differences on the involved trajectories. Diagnostic resolution screening, not rigorous uncertainty bounds.',
           'vector_identity':'A-B = (A-C)+(C-B), A=original CPD2, C=mean-matched counterfactual CPD2, B=CPD4; vector closure tolerance 1e-12 normalized.',
           'closure_max':1e-12,'no_spatial_pass_from_this_test':True},
       'field_probe':{'samples_per_original_finest_path':21,'paths':['CPD2 fibre','CPD4 fibre'],'selection':'Nearest indices on uniformly spaced accepted-row index; descriptive path-conditioned sampling, not population statistics.',
                      'near_wall_centre_clearance_threshold':'two CPD2 cells','mean_scaling_rtol':1e-12},
       'claim_boundary':'Single seed, original common-admissible sentinel, 0.5 s. No experimental validation, release fraction, new CFD solution or asymptotic grid convergence.',
       'source_hashes':{str(p):api.sha(p) for p in sources},'inputs':{str(p):api.sha(p) for p in inputs}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);verify(d)
    print('FROZEN',api.sha(DESIGN),'six counterfactual diagnostic cases',flush=True)

binding=engine.binding
def configure():
    engine.DESIGN,engine.RUN,engine.EVAL=DESIGN,RUN,EVAL
    engine.verify=execution_verify;engine.runtime=SimpleNamespace(execute=execute);engine.__file__=str(Path(__file__).resolve())

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    else:
        configure()
        if sys.argv[1]=='run':raise SystemExit(engine.run())
        else:raise SystemExit(engine.worker(sys.argv[2],int(sys.argv[3])))
