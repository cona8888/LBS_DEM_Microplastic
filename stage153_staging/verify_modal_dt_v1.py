"""Bounded local cost/accuracy test of the derived rotational-mode timestep."""
from pathlib import Path
import copy
import datetime
import os
import sys
import traceback
import numpy as np
from scipy.linalg import eigh
import modal_rotation_dt_v1 as candidate

s=candidate.previous
w,api,engine,hot,model=s.w,s.api,s.engine,s.hot,s.model
ROOT=s.ROOT
BASE='modal_rotation_timestep_20260922'
DESIGN=ROOT/'stage153_designs'/BASE/'design_01.json'
RUN=ROOT/'stage153_runs'/BASE/'run_01'
OUT=ROOT/'stage153_evaluations'/BASE/'evaluation_01'


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);s.verify(api.read(s.DESIGN))
    api.require(d['generated_source_sha256']==api.digest(candidate.GENERATED_SOURCE),'generated source hash')


def prepare():
    ev=api.read(s.OUT/'results.json')
    api.require(ev['passed'] and api.read(s.OUT/'completion.json')['results_sha256']==api.sha(s.OUT/'results.json'),'Stage152 sealed pass')
    api.verify_mapping(ev['artifacts']);old=api.read(w.DESIGN);w.verify(old)
    inputs={str(p):api.sha(p) for p in [s.DESIGN,s.OUT/'results.json',s.OUT/'completion.json',w.DESIGN,Path(old['case']['source']),w.OUT/'rigid_1.0.json',w.OUT/'rigid_0.25.json']}
    inputs.update(ev['artifacts'])
    d={'stage':'Stage153','question':'Can the derived paired-mode rotational timestep reduce cost while meeting the existing local accuracy budget?',
       'physical_changes':[],'numerical_change':'Replace min(eigen(Mrot))/max(eigen(Rrot)) by min generalized eigenvalue(Mrot,Rrot). Keep relaxation fractions, all other timestep caps, gyro, inertia, contact and fluid models unchanged.',
       'reference':'Stage152 completed finest conservative-controller trajectory over the same inherited 0.002-s moving-fibre window.',
       'acceptance':old['moving'],'factors':[1.,.5,.25],
       'additional_checks':'All levels complete with exact clocks, numerical health and no unqualified fallback; same finite-dwell/outlet verdict. Each candidate common-clock full trace must satisfy the inherited position/b, axis and q/U limits against the conservative finest reference. Coarsest split/restart must be exact.',
       'cost_gate':'Coarsest modal controller must use no more than half the accepted steps of the existing conservative coarse controller. Wall time is measured, not used as a machine-independent correctness criterion.',
       'canonical':'Known diagonal modes, rotated and noncommuting SPD matrices against scipy.linalg.eigh; invalid matrices rejected. Scope disabled/restoration preserves original function object.',
       'budget':{'cooperative_seconds_per_call':45.,'max_calls':5,'step_cap_per_call':6000,'workers':1,'threads':1},
       'claim':'Local timestep/cost qualification at one saved moving-fibre state. Not contact-onset/release, full trajectory, sphere-fibre trend, population release or experimental validation.',
       'stop':'Any failed physics, accuracy, provenance or bounded-completion gate stops promotion. No adaptive tolerance loosening or added retries.',
       'sources':{str(Path(m.__file__).resolve()):api.sha(m.__file__) for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents},
       'inputs':inputs,'generated_source_sha256':api.digest(candidate.GENERATED_SOURCE)}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def toys():
    rng=np.random.default_rng(153);rows=[]
    for i in range(20):
        A=rng.normal(size=(3,3));B=rng.normal(size=(3,3))
        M=A@A.T+np.eye(3);R=B@B.T+np.eye(3)
        value=candidate.shortest_mode(M,R);expected=float(eigh(M,R,eigvals_only=True)[0])
        rows.append(abs(value-expected)/expected<1e-12)
    rows.append(abs(candidate.shortest_mode(np.diag([2.,30.,40.]),np.diag([1.,3.,4.]))-2.)<1e-14)
    negative=[]
    for M,R in [(np.diag([-1.,1.,1.]),np.eye(3)),(np.eye(3),np.zeros((3,3))),
                (np.ones((2,2)),np.eye(3)),(np.eye(3)*np.nan,np.eye(3)),(np.array([[1.,1.,0.],[0.,1.,0.],[0.,0.,1.]]),np.eye(3))]:
        try:candidate.shortest_mode(M,R)
        except (ValueError,np.linalg.LinAlgError):negative.append(True)
        else:negative.append(False)
    original=model.original.INTEGRATE
    with candidate.scope(False):disabled=model.original.INTEGRATE is original
    with candidate.scope(True):enabled=model.original.INTEGRATE is candidate.CANDIDATE
    restored=model.original.INTEGRATE is original
    return {'passed':all(rows+negative+[disabled,enabled,restored]),'positive_checks':rows,'invalid_controls':negative,'disabled_exact_dispatch':disabled,'scope_restored':restored}


def call(d,factor,name,cp=None,pause=None):
    old=api.read(w.DESIGN);spec=copy.deepcopy(old['case']['spec']);source=api.read(old['case']['source'])['result']['checkpoint']
    spec['horizon_s']=source['state']['t']+old['moving']['window_s'];spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
    for key in api.DT_CONTROLS:spec['config']['numerics'][key]*=factor
    binding=api.digest([d['binding'],'paired_rotational_modes',factor])
    if cp is None:cp=model.checkpoint(spec,binding,source,True)
    before=copy.deepcopy(cp)
    with hot.scope(),candidate.scope(True):
        r,rows=engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+(pause or d['budget']['step_cap_per_call']))
    record={'result':r,'rows':rows,'spec':spec,'factor':factor,'input_checkpoint_sha256':api.digest(before),'design_sha256':api.sha(DESIGN),'effective_binding':model.binding_for(binding,True)}
    record['checks']=s.check_record(record,before,spec,record['effective_binding'])
    path=RUN/(name+'.json');api.write(path,record,raw=True)
    print(name,r['status'],len(rows),'HEALTH',record['checks']['passed'],flush=True)
    api.require(record['checks']['passed'],'independent health')
    api.require(r['status']==('paused_checkpoint' if pause else 'present_at_horizon'),'bounded completion')
    return record


def common_trace(reference,record,source):
    def arrays(rows):
        history=[{'time_s':source['state']['t'],'position_m':source['state']['x'],'orientation':source['state']['p'],'velocity_generalized':source['state']['q']}]+rows
        return {k:np.array([x[k] for x in history],float) for k in ['time_s','position_m','orientation','velocity_generalized']}
    a,b=arrays(reference),arrays(record['rows']);times=np.unique(np.r_[a['time_s'],b['time_s']]);spec=record['spec'];answer={}
    for key,label,scale in [('position_m','position_over_b',spec['config']['prolate_semiaxes_m'][1]),('orientation','axis_vector_norm',1.),('velocity_generalized','generalized_velocity_relative',spec['config']['target_mean_interstitial_velocity_m_s'])]:
        interp=lambda v:np.column_stack([np.interp(times,v['time_s'],v[key][:,j]) for j in range(v[key].shape[1])])
        answer[label]=float(np.max(np.linalg.norm(interp(a)-interp(b),axis=1))/scale)
    return answer


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'launch.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'argv':sys.argv,'python':sys.version,'numpy':np.__version__,'design_sha256':api.sha(DESIGN),'threads':{k:os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']}})
    primitive=toys();api.write(RUN/'canonical.json',primitive);api.require(primitive['passed'],'canonical mode tests')
    w.prior.parent.old.prior.prior.configure();hot.warmup()
    records=[call(d,f,f'factor_{f}') for f in d['factors']]
    errors=[w.compare(a['result'],b['result'],b['spec']) for a,b in zip(records,records[1:])]
    limits=d['acceptance']['limits'];moving=d['acceptance']
    trend=all(errors[1][k]<=limit and (errors[1][k]<=moving['error_reduction_ratio_max']*errors[0][k] or max(errors[0][k],errors[1][k])<moving['noise_floor']) for k,limit in limits.items())
    archived=api.read(w.OUT/'rigid_0.25.json');completed=api.read(s.RUN/'completion'/'record.json')
    reference=archived['rows']+completed['rows'];source=api.read(api.read(w.DESIGN)['case']['source'])['result']['checkpoint']
    whole=[common_trace(reference,r,source) for r in records]
    accurate=all(all(row[k]<=limit for k,limit in limits.items()) for row in whole)
    verdict=all(all(r['result'][k]==completed['result'][k] for k in ['status','persistent_contact_observed','dwell_is_absorbing']) for r in records)
    coarse=api.read(w.OUT/'rigid_1.0.json');cost_ok=len(records[0]['rows'])<=len(coarse['rows'])/2
    preliminary={'passed':bool(trend and accurate and verdict and cost_ok),'three_level_errors':errors,'whole_trace_errors':whole,'trend_passed':trend,'common_trace_passed':accurate,'same_verdict':verdict,'cost_passed':cost_ok}
    api.write(RUN/'precheck.json',preliminary)
    api.require(preliminary['passed'],'accuracy/cost gate; no restart dispatch')
    first=call(d,1.,'restart_first',pause=len(records[0]['rows'])//2)
    last=call(d,1.,'restart_second',cp=first['result']['checkpoint'])
    exact=(last['result']['checkpoint']['state']==records[0]['result']['checkpoint']['state'] and first['rows']+last['rows']==records[0]['rows'])
    verify(d)
    result={'stage':'Stage153','passed':bool(preliminary['passed'] and exact),'canonical_passed':primitive['passed'],'comparison':preliminary,'exact_restart':exact,
            'coarse_steps_old_new':[len(coarse['rows']),len(records[0]['rows'])],'coarse_runtime_s_old_new':[coarse['result']['runtime_seconds'],records[0]['result']['runtime_seconds']],
            'step_reduction_factor':len(coarse['rows'])/len(records[0]['rows']),'runtime_ratio_old_over_new':coarse['result']['runtime_seconds']/records[0]['result']['runtime_seconds'],
            'claim':d['claim'],'production_promotion':False,'design_sha256':api.sha(DESIGN),'artifacts':{str(p):api.sha(p) for p in RUN.iterdir() if p.is_file()}}
    OUT.mkdir(parents=True,exist_ok=False);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('STAGE153_PASS',result['passed'],'STEPS',result['coarse_steps_old_new'],'RUNTIME',result['coarse_runtime_s_old_new'],flush=True)
    return 0 if result['passed'] else 4


if __name__=='__main__':
    try:
        if sys.argv[1]=='prepare':prepare()
        elif sys.argv[1]=='run':raise SystemExit(run())
        else:raise ValueError('unknown command')
    except Exception as exc:
        if RUN.exists() and not (RUN/'failure.json').exists():api.write(RUN/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()})
        raise
