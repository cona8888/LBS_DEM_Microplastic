"""Change only the first step fraction; identical initial state/physical clock.

The shifted time grid is a diagnostic perturbation, not a production controller.
Stage159's three phase-zero traces remain failed under their original contract.
"""
import ast
from contextlib import contextmanager
import copy
from pathlib import Path
import sys
import os
import datetime
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage160_staging'))
import diagnose_endpoint_phase_v1 as diagnosis
v=diagnosis.prior;api=v.api;old=v.old;model=v.model;fix=v.fix;engine=v.engine;diag=v.diag
BASE='contact_grid_phase_probe_20260922'
DESIGN=ROOT/'stage161_designs'/BASE/'design_01.json'
RUN=ROOT/'stage161_runs'/BASE/'run_01'
OUT=ROOT/'stage161_evaluations'/BASE/'evaluation_01'
PHASES=[1/3,2/3]


def compile_phase(entry_steps,fraction):
    if not 0<fraction<=1 or type(entry_steps) is not int:raise ValueError('valid first-step phase required')
    tree=ast.parse(old.parent.prior.candidate.GENERATED_SOURCE);count=0
    class Inject(ast.NodeTransformer):
        def visit_Assign(self,node):
            nonlocal count
            if ast.unparse(node)=='dt = min(dt, relaxation_fraction * tau_rot)':
                count+=1
                return [node,*ast.parse('if steps == phase_entry_steps:\n    dt *= first_step_fraction').body]
            return self.generic_visit(node)
    Inject().visit(tree);api.require(count==1,'unique phase injection')
    ast.fix_missing_locations(tree)
    ns=dict(old.parent.prior.candidate.CANDIDATE.__globals__)
    ns.update(phase_entry_steps=entry_steps,first_step_fraction=fraction)
    exec(compile(tree,'<Stage161:first_step_phase_only>','exec'),ns)
    return ns['integrate'],ast.unparse(tree)


@contextmanager
def phase_scope(entry_steps,fraction):
    fn,_=compile_phase(entry_steps,fraction)
    saved=model.original.INTEGRATE;model.original.INTEGRATE=fn
    try:
        with model.scope(True):yield
    finally:model.original.INTEGRATE=saved


def prepare():
    diagnosis.verify(api.read(diagnosis.DESIGN));d0=api.read(v.DESIGN);v.verify(d0)
    ev=api.read(diagnosis.OUT/'results.json')
    api.require(ev['diagnostic_integrity_passed'] and ev['toy_nonmonotone_count']>0,'diagnostic prerequisite')
    fail=v.OUT.parent/'failure_audit_01';inputs=dict(api.read(fail/'results.json')['artifacts'])
    for p in [v.DESIGN,diagnosis.DESIGN,diagnosis.OUT/'results.json',diagnosis.OUT/'completion.json',fail/'results.json',fail/'completion.json']:
        inputs[str(p)]=api.sha(p)
    seed=v.read(v.RUN/'engagement'/'seed.json')['result']['checkpoint']
    _,source=compile_phase(seed['state']['steps'],1.)
    d={'stage':'Stage161','question':'Does changing only timestep placement explain the nonmonotone local endpoint differences?',
       'window':d0['windows'][0],'base_spec':d0['base_spec'],'factors':v.FACTORS,'new_first_step_fractions':PHASES,
       'reused_phase':'First step fraction 1.0: exact three Stage159 local engagement traces.',
       'method':'Identical complete entry checkpoint and physical clock. First accepted nominal step multiplied by 1/3 or 2/3, then original modal dt caps restored. End time unchanged. No time alignment, state projection or contact-law change.',
       'accuracy':d0['accuracy'],'velocity_L1_and_impulse_limit_over_U':.005,
       'primary_checks':['Provenance, health, no new rejections, exact clocks, identical entry state.',
                         'Fraction 1.0 reproduces 100 archived steps bitwise. Fraction 1/3 passes 100 versus 37+63 restart; first-step perturbation applies once.',
                         'All new local traces meet unchanged pose, L1 and impulse budgets against fixed finest phase-zero trace, with endpoint errors below unchanged caps.',
                         'All impulse replays match accepted q and close momentum/work within 1e-8.'],
       'diagnostic_not_acceptance':'Report all endpoint vectors, within-level diameters, and maximum cross-phase endpoint differences between adjacent levels. Test the original 0.8 reduction on these cross-phase envelopes, without using a favorable phase or changing Stage159 verdict. Even positive evidence does not qualify full-window integration or a production controller.',
       'budget':{'new_cases':6,'max_calls_per_case':3,'step_cap':2500,'preflight_calls':4,'max_replays_per_new_case':1500,
                 'workers':1,'threads':1,'cooperative_seconds_per_call':45.,'estimated_integration_minutes':[3,6]},
       'stop':'Stop on a primary runtime/accuracy/integrity failure; do not add levels or phases. No release trajectory or new physics.',
       'seed_source':str(v.RUN/'engagement'/'seed.json'),'phase_generated_source_digest':api.digest(source),
       'inputs':inputs,'sources':{str(Path(m.__file__).resolve()):api.sha(m.__file__) for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents},
       'production_promotion':False,'physical_changes':[]}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:x for k,x in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['inputs']);api.verify_mapping(d['sources']);diagnosis.verify(api.read(diagnosis.DESIGN))
    seed=api.read(d['seed_source'])['result']['checkpoint']
    api.require(api.digest(compile_phase(seed['state']['steps'],1.)[1])==d['phase_generated_source_digest'],'phase generated source')


def case_id(f,phase):return f'factor_{f}_phase_{round(phase*3)}of3'


def setup(d,f,phase,purpose='campaign'):
    seed=api.read(d['seed_source'])['result']['checkpoint'];spec=copy.deepcopy(d['base_spec'])
    spec['horizon_s']=d['window']['horizon_s'];spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
    for k in api.DT_CONTROLS:spec['config']['numerics'][k]*=f
    binding=api.digest([d['binding'],f,phase,purpose])
    return spec,binding,model.checkpoint(spec,binding,seed,True)


def execute(d,spec,binding,cp,path,steps,phase):
    before=copy.deepcopy(cp);ncalls=len(model.calls);ncert=len(fix.telemetry)
    entry=api.read(d['seed_source'])['result']['checkpoint']['state']['steps']
    with old.hot.scope(),phase_scope(entry,phase),fix.scope():
        result,rows=engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+steps)
    r={'result':result,'rows':rows,'spec':spec,'input_checkpoint_sha256':api.digest(before),'step_cap':steps,
       'effective_binding':model.binding_for(binding,True),'design_sha256':api.sha(DESIGN),
       'backend_calls':copy.deepcopy(model.calls[ncalls:]),'certificates':copy.deepcopy(fix.telemetry[ncert:]),'first_step_fraction':phase}
    r['checks']=old.parent.prior.s.check_record(r,before,spec,r['effective_binding'])
    api.write(path,r,raw=True);api.write(path.with_suffix('.seal.json'),{'record_sha256':api.sha(path),'design_sha256':api.sha(DESIGN)})
    v.check(r,before,spec,binding)
    print(path.relative_to(RUN),result['status'],len(rows),'t=',result['time_s'],flush=True)
    return r


def read(p):
    api.require(api.read(p.with_suffix('.seal.json'))=={'record_sha256':api.sha(p),'design_sha256':api.sha(DESIGN)},'record seal')
    return api.read(p)


def preflight(d):
    f=d['factors'][0];spec,binding,cp=setup(d,f,1.,'identity')
    r=execute(d,spec,binding,cp,RUN/'identity.json',100,1.)
    original=v.joined(api.read(v.DESIGN),0,f)
    api.require(r['rows']==original['rows'][:100],'fraction-one exact identity')
    phase=PHASES[0];spec,binding,cp=setup(d,f,phase,'restart')
    full=execute(d,spec,binding,cp,RUN/'restart_full.json',100,phase)
    first=execute(d,spec,binding,cp,RUN/'restart_first.json',37,phase)
    last=execute(d,spec,binding,first['result']['checkpoint'],RUN/'restart_last.json',63,phase)
    api.require(full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state'],'exact phase restart')
    api.require(full['rows'][0]['dt_s']==original['rows'][0]['dt_s']*phase,'first step fraction')


def joined(d,f,phase):
    spec,binding,cp=setup(d,f,phase);paths=sorted((RUN/case_id(f,phase)).glob('segment_[0-9][0-9].json'))
    api.require(0<len(paths)<=d['budget']['max_calls_per_case'],'case count');rows=[];cost=0.
    for n,p in enumerate(paths,1):
        api.require(p.name==f'segment_{n:02d}.json','case order');r=read(p);v.check(r,cp,spec,binding)
        api.require(r['first_step_fraction']==phase,'phase binding')
        api.require(n==len(paths) or r['result']['status'] in ['paused_checkpoint','incomplete_budget'],'no post-completion execution')
        rows+=r['rows'];cost+=r['result']['runtime_seconds'];cp=r['result']['checkpoint']
    api.require(r['result']['status']=='present_at_horizon','completed case')
    baseline=v.joined(api.read(v.DESIGN),0,f)['rows'][0]['dt_s']
    api.require(rows[0]['dt_s']==phase*baseline,'first accepted step phase')
    return {'result':r['result'],'rows':rows,'spec':spec,'cost_s':cost,'factor':f,'phase':phase}


def impulse(d,r,field,geometry):
    seed=api.read(d['seed_source'])['result']['checkpoint']['state'];start,stop=d['window']['impulse_window_s']
    U=d['base_spec']['config']['target_mean_interstitial_velocity_m_s'];total=np.zeros(6);samples=[]
    with old.hot.scope(),engine.runtime.repair_scope(),fix.scope():
        for i,row in enumerate(r['rows']):
            left=seed['t'] if i==0 else r['rows'][i-1]['time_s'];right=row['time_s']
            overlap=max(0.,min(right,stop)-max(left,start))
            if not overlap:continue
            p=r['rows'][i-1] if i else None
            prev=seed if i==0 else {'x':p['position_m'],'p':p['orientation'],'q':p['velocity_generalized'],'t':left,'recovery':seed['recovery']}
            q,h=diag.replay(field,geometry,r['spec'],prev,row['dt_s'])
            err=float(np.linalg.norm(q-row['velocity_generalized'])/U)
            api.require(err<=1e-8 and h['momentum_residual']<=1e-8 and h['work_balance_relative']<=1e-8,'replay/balance')
            total+=np.array(h['impulse_generalized'])*overlap/row['dt_s']
            samples.append({'time_s':right,'dt_s':row['dt_s'],'overlap_s':overlap,'replay_error_over_U':err,
                            **{k:h[k] for k in ['impulse_generalized','momentum_residual','work_balance_relative']}})
            api.require(len(samples)<=d['budget']['max_replays_per_new_case'],'replay budget')
    api.require(abs(sum(s['overlap_s'] for s in samples)-(stop-start))<=1e-13,'complete impulse coverage')
    return {'total_impulse':total.tolist(),'samples':samples}


def case_metrics(d,r,reference,imp,reference_imp):
    seed=api.read(d['seed_source'])['result']['checkpoint'];cfg=d['base_spec']['config'];U=cfg['target_mean_interstitial_velocity_m_s']
    limits=d['accuracy']['limits'];trace=old.parent.prior.common_trace(reference['rows'],r,seed)
    l1=diag.piecewise_l1(r['rows'],reference['rows'],seed['state']['t'],d['window']['horizon_s'],U)['mean_norm_over_scale']
    ep=old.parent.prior.w.compare(r['result'],reference['result'],reference['spec'])
    error=float(np.linalg.norm(np.linalg.solve(np.array(reference_imp['mass_at_entry']),np.array(imp['total_impulse'])-reference_imp['levels'][-1]['total_impulse']))/U)
    checks={'endpoint_budgets':all(ep[k]<=lim for k,lim in limits.items()),'whole_pose':all(trace[k]<=limits[k] for k in ['position_over_b','axis_vector_norm']),
            'whole_L1':l1<=.005,'impulse':error<=.005}
    return {'passed':all(checks.values()),'checks':checks,'endpoint_to_fixed_finest_phase_zero':ep,
            'whole_pose_and_peak_diagnostic':trace,'whole_L1_over_U':l1,'impulse_error_over_U':error,
            'steps':len(r['rows']),'runtime_s':r['cost_s'],'factor':r['factor'],'first_step_fraction':r['phase']}


def envelopes(d,all_cases):
    cfg=d['base_spec']['config'];keys=[('position_m','position_over_b',cfg['prolate_semiaxes_m'][1]),
                                    ('orientation','axis_vector_norm',1.),('velocity_generalized','generalized_velocity_relative',cfg['target_mean_interstitial_velocity_m_s'])]
    result={}
    for key,label,scale in keys:
        groups=[np.array([r['rows'][-1][key] for r in all_cases if r['factor']==f])/scale for f in d['factors']]
        within=[float(np.linalg.norm(g[:,None]-g[None,:],axis=2).max()) for g in groups]
        cross=[float(np.linalg.norm(a[:,None]-b[None,:],axis=2).max()) for a,b in zip(groups,groups[1:])]
        result[label]={'within_level_diameters':within,'adjacent_cross_phase_envelopes':cross,
                       'envelope_ratio':cross[1]/cross[0],'envelope_reduction_0p8':cross[1]<=.8*cross[0],
                       'all_adjacent_envelopes_within_original_limit':max(cross)<=d['accuracy']['limits'][label]}
    return result


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'launch.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'design_sha256':api.sha(DESIGN),'python':sys.version})
    old.parent.configure();preflight(d);spec=d['base_spec'];field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    originals=[{**v.joined(api.read(v.DESIGN),0,f),'factor':f,'phase':1.} for f in d['factors']]
    reference=originals[-1];reference_imp=api.read(v.OUT/'engagement_impulses.json');all_cases=list(originals);reports=[]
    for f in d['factors']:
        for phase in PHASES:
            folder=RUN/case_id(f,phase);folder.mkdir(exist_ok=False);spec,binding,cp=setup(d,f,phase)
            for n in range(1,d['budget']['max_calls_per_case']+1):
                r=execute(d,spec,binding,cp,folder/f'segment_{n:02d}.json',2500,phase)
                if r['result']['status']=='present_at_horizon':break
                cp=r['result']['checkpoint']
            api.require(r['result']['status']=='present_at_horizon','case budget exhausted')
            rec=joined(d,f,phase);imp=impulse(d,rec,field,geometry);report=case_metrics(d,rec,reference,imp,reference_imp)
            api.write(OUT/(case_id(f,phase)+'_impulses.json'),imp,raw=True);api.write(OUT/(case_id(f,phase)+'_summary.json'),report,raw=True)
            api.require(report['passed'],'unchanged absolute accuracy budget failed')
            reports.append(report);all_cases.append(rec)
            print('CASE PASS',f,phase,'impulse',report['impulse_error_over_U'],flush=True)
    env=envelopes(d,all_cases);verify(d)
    result={'stage':'Stage161','diagnostic_integrity_passed':True,'new_cases':reports,'endpoint_phase_envelopes':env,
            'all_endpoint_envelopes_contract':all(x['envelope_reduction_0p8'] for x in env.values()),
            'all_original_absolute_budgets_passed':True,'prior_stage159_passed':False,
            'production_promotion':False,'full_window_accuracy':False,
            'claim':'Six new time-grid phase perturbations in one conditional engagement window; fixed physics and entry state. No adaptive controller or release trajectory tested.',
            'design_sha256':api.sha(DESIGN),'artifacts':{str(p):api.sha(p) for folder in [RUN,OUT] for p in folder.rglob('*') if p.is_file()}}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'diagnostic_integrity_passed':True})
    print('PHASE DIAGNOSTIC COMPLETE',env,flush=True)


if __name__=='__main__':
    owned=False
    try:
        if sys.argv[1:]==['prepare']:prepare()
        elif sys.argv[1:]==['run']:
            api.require(not RUN.exists() and not OUT.exists(),'immutable output exists');owned=True;run()
        else:raise ValueError('Use prepare or run')
    except Exception as e:
        if owned and RUN.exists() and not (RUN/'failure.json').exists():api.write(RUN/'failure.json',{'error':repr(e),'traceback':traceback.format_exc()})
        raise
