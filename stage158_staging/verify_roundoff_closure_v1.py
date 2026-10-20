"""Frozen arithmetic falsification tests plus bounded exact application replays."""
from pathlib import Path
import copy
import datetime
import os
import sys
import time
import traceback
import numpy as np
import roundoff_closure_v1 as fix

job=fix.prior;api,old,diag=job.api,job.old,job.diag
ROOT=fix.ROOT;BASE='roundoff_force_certificate_20260922'
DESIGN=ROOT/'stage158_designs'/BASE/'design_01.json'
OUT=ROOT/'stage158_evaluations'/BASE/'verification_01'
FAILED=job.OUT.parent/'failure_audit_01'/'results.json'


def prepare():
    job.verify(api.read(job.DESIGN))
    api.require(api.read(FAILED.parent/'completion.json')['results_sha256']==api.sha(FAILED),'failed audit seal')
    files=[FAILED,FAILED.parent/'completion.json',job.DESIGN,diag.OUT/'results.json',diag.OUT/'completion.json',
           job.RUN/'release'/'segment_03.json',job.RUN/'release'/'segment_03.seal.json']
    d={'stage':'Stage158','question':'Can roundoff be certified without weakening the 1e-8 contact-force closure or changing a computed state?',
       'physical_changes':[],'arithmetic_change':'Only when old rounded-velocity closure fails: exact rational six-dimensional solve using binary64 inputs. Same 1e-8 limit on unsummed correction; independently correctly rounded velocity sum; exact decomposition into incremental closure plus addition roundoff.',
       'scope':'Opt-in research verification only, no production default, no failed-run restart and no time advancement.',
       'test_plan':{'random_seed':158,'random_systems':96,'condition_numbers':[1,100,10000],
                    'correction_scales':[1e-4,1e-8,1e-12,1e-16],
                    'negative_tests':['corrupt velocity','corrupt unsummed correction','corrupt force','corrupt mobility','NaN','singular matrix','ill-conditioned matrix','negative normal force','Coulomb cone violation','complementarity violation','energy-generating contact'],
                    'application':'Replay all 107 frozen Stage156 sampled states with exact output identity, plus the one captured Stage157 failing pose under the new opt-in certificate. Do not advance or accept the old failed run.'},
       'gates':{'all_negative_tests_reject':True,'legacy_healthy_replay_error_over_U':0.,'momentum_max':1e-8,'work_max':1e-8,
                'force_residual_limit_unchanged':1e-8,'fallback_condition_max':1e8,'maximum_distinct_frozen_poses':108,'maximum_frozen_pose_solver_calls':215,
                'maximum_certificate_mean_seconds':.1},
       'inputs':{str(p):api.sha(p) for p in files},
       'sources':{str(Path(m.__file__).resolve()):api.sha(m.__file__) for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);job.verify(api.read(job.DESIGN))


def inputs_from_failure():
    a=api.read(FAILED)['captured_failures'][0]['frozen_system']
    v,M,J,f,g,steps=[np.array(a[k],float) for k in ['free_velocity','mobility','jacobian','reaction','gaps','tangential_steps']]
    return v,M,J,f,J@v,J@M@J.T,g,a['dt_s'],a['friction'],steps,1,'captured_standard_pgs',{}


def unit_tests(d):
    args=inputs_from_failure();v,M,J,f=args[:4];inc=M@J.T@f;q=v+inc
    old_failure=None
    try:old.hot.s50._finish(*args)
    except RuntimeError as e:old_failure=str(e)
    api.require(old_failure=='direct contact force closure failed','legacy captured failure')
    new,health=fix.finish(*args)
    api.require(np.array_equal(new,q) and health['roundoff_certificate_used'],'unchanged returned velocity')
    cases=[];negative=[];rng=np.random.default_rng(d['test_plan']['random_seed'])
    for condition in d['test_plan']['condition_numbers']:
        for scale in d['test_plan']['correction_scales']:
            for replicate in range(8):
                Q=np.linalg.qr(rng.normal(size=(6,6)))[0]
                mob=(Q*np.geomspace(1.,condition,6))@Q.T
                jac=rng.normal(size=(3,6));force=rng.normal(size=3)*scale/condition
                free=rng.normal(size=6);delta=mob@jac.T@force;vel=free+delta
                r=fix.certificate(free,mob,jac,force,delta,vel,exact=True)
                cases.append(r)
    def reject(name,call):
        try:call()
        except (RuntimeError,ValueError,np.linalg.LinAlgError) as e:
            negative.append({'name':name,'rejected':True,'reason':str(e)});return
        raise RuntimeError('negative test incorrectly accepted: '+name)
    cert=lambda vv=v,mm=M,jj=J,ff=f,dd=inc,qq=q:fix.certificate(vv,mm,jj,ff,dd,qq,exact=True)
    reject('corrupt velocity',lambda:cert(qq=q+np.eye(6)[0]*1e-12))
    bad=inc*1.01
    reject('corrupt unsummed correction',lambda:cert(dd=bad,qq=v+bad))
    reject('corrupt force',lambda:cert(ff=f*1.01))
    reject('corrupt mobility',lambda:cert(mm=M*1.01))
    reject('NaN',lambda:cert(qq=q*np.nan))
    reject('singular matrix',lambda:cert(mm=np.zeros((6,6))))
    reject('ill-conditioned matrix',lambda:cert(mm=np.diag([1.,1.,1.,1.,1.,1e-12])))
    # Hand-built valid frictionless normal contact: q_n=0, unit reaction.
    j=np.eye(6)[:3];free=np.array([-1.,0.,0.,0.,0.,0.]);mob=np.eye(6);force=np.array([1.,0.,0.])
    base=[free,mob,j,force,j@free,j@mob@j.T,np.zeros(1),1.,.3,np.ones(1),1,'toy',{}]
    good,h=fix.finish(*base);api.require(np.array_equal(good,np.zeros(6)),'canonical normal contact')
    for name,fnew in [('negative normal force',[-1.,0.,0.]),('Coulomb cone violation',[1.,1.,0.]),('complementarity violation',[.9,0.,0.])]:
        altered=copy.deepcopy(base);altered[3]=np.array(fnew)
        reject(name,lambda a=altered:fix.finish(*a))
    # Isolate the original energy check by injecting a falsely converged residual.
    altered=copy.deepcopy(base);altered[3]=np.array([1.,.1,0.]);altered[0][1]=1.;altered[4]=j@altered[0]
    original=old.hot.s50._residual
    try:
        old.hot.s50._residual=lambda *a:0.
        reject('energy-generating contact',lambda:fix.finish(*altered))
    finally:old.hot.s50._residual=original
    api.require(len(cases)==96 and len(negative)==11,'frozen test count')
    mean=float(np.mean([r['certificate_seconds'] for r in cases]))
    api.require(mean<=d['gates']['maximum_certificate_mean_seconds'],'bounded arithmetic cost')
    return {'passed':True,'captured_old_failure':old_failure,'captured_new_health':health,
            'returned_velocity_identical':True,'random_cases':cases,'negative_tests':negative,'certificate_mean_seconds':mean}


def application(d):
    old.parent.configure();spec=api.read(job.DESIGN)['base_spec']
    field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    source=api.read(diag.OUT/'results.json');rows=[];U=spec['config']['target_mean_interstitial_velocity_m_s']
    with old.hot.scope(),old.engine.runtime.repair_scope():
        for window in source['windows']:
            for level in window['levels']:
                for sample in level['samples']:
                    q0,h0=diag.replay(field,geometry,spec,sample['state'],sample['dt_s'])
                    with fix.scope():q1,h1=diag.replay(field,geometry,spec,sample['state'],sample['dt_s'])
                    error=float(np.linalg.norm(q1-q0)/U)
                    api.require(error==0. and h1['momentum_residual']<=1e-8 and h1['work_balance_relative']<=1e-8,'healthy replay changed')
                    rows.append({'window':window['id'],'factor':level['factor'],'time_s':sample['time_s'],
                                 'error_over_U':error,'momentum':h1['momentum_residual'],'work':h1['work_balance_relative']})
        failed=api.read(job.RUN/'release'/'segment_03.json')
        with fix.scope():q,h=diag.replay(field,geometry,failed['spec'],failed['result']['checkpoint']['state'],failed['rows'][-1]['dt_s'])
    api.require(len(rows)==107 and h['momentum_residual']<=1e-8 and h['work_balance_relative']<=1e-8,'bounded failed-pose replay')
    return {'healthy_replays':rows,'failed_pose_new_replay':h,'new_velocity':q.tolist(),'time_advanced':False,
            'fallback_telemetry':list(fix.telemetry),'passed':True}


def run():
    d=api.read(DESIGN);verify(d);OUT.mkdir(parents=True,exist_ok=False)
    api.write(OUT/'launch.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'design_sha256':api.sha(DESIGN),'python':sys.version})
    unit=unit_tests(d);api.write(OUT/'unit_tests.json',unit,raw=True)
    print('UNIT PASS',len(unit['random_cases']),len(unit['negative_tests']),unit['certificate_mean_seconds'],flush=True)
    app=application(d);api.write(OUT/'replays.json',app,raw=True);verify(d)
    result={'stage':'Stage158','passed':True,'design_sha256':api.sha(DESIGN),
            'random_systems':96,'negative_tests_rejected':11,'healthy_replays_bitwise_identical':107,
            'failed_pose_certified_without_advancement':True,'new_failed_pose_momentum':app['failed_pose_new_replay']['momentum_residual'],
            'new_failed_pose_work':app['failed_pose_new_replay']['work_balance_relative'],
            'certificate_mean_seconds':unit['certificate_mean_seconds'],
            'artifacts':{str(OUT/n):api.sha(OUT/n) for n in ['unit_tests.json','replays.json','launch.json']},
            'prior_failures_unchanged':True,'impact_impulse_error_resolved':False,'production_promotion':False}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'passed':True})
    print('STAGE158 PASS',result,flush=True)


if __name__=='__main__':
    owned=False
    try:
        if sys.argv[1:]==['prepare']:prepare()
        elif sys.argv[1:]==['run']:
            api.require(not OUT.exists(),'immutable verification exists');owned=True;run()
        else:raise ValueError('Use prepare or run')
    except Exception as e:
        if owned and OUT.exists() and not (OUT/'failure.json').exists():api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc()})
        raise
