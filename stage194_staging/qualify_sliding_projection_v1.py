"""Frozen zero-trajectory gate for the opt-in all-sliding numerical fallback."""
from pathlib import Path
from types import SimpleNamespace
import copy,itertools,os,sys,time,traceback
import numpy as np
import qualify_failure_codec_v1 as q
import sliding_projection_repair_v1 as repair
sys.path[:0]=[str(q.ROOT/'stage183_staging'),str(q.ROOT/'stage119_staging')]
import audit_fallback_systems_v1 as independent
import verify_repair_v3 as analytical

job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924'
OUT=BASE/'sliding_qualification_01';DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/sliding_qualification_01.json'


def args(s):return (*[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps_m')],s['dt_s'],s['friction'],1e-10,25000)


def audit(a,answer):
    v,M,J,g,dt,mu,_,_=a;velocity,h=answer
    row={'accepted':True,'vfree':v.tolist(),'mobility':M.tolist(),'jacobian':J.tolist(),'gaps_m':g.tolist(),'dt_s':dt,'friction':mu,'velocity':velocity.tolist(),'health':h}
    out=independent.physical(row)
    f=np.asarray(h['reactions']);out['decimal_unsummed_force_residual']=independent.decimal_closure(v,M,J,f,M@J.T@f,velocity)
    return out,row


def run():
    work=api.read(q.WORK);end=job.policy.utc(work['work_end_utc']).timestamp();api.require(time.time()<end,'work clock')
    oldd=api.read(job.DESIGN);job.verify(oldd)
    inputs=[q.WORK,Path(__file__),Path(repair.__file__),BASE/'contact_diagnosis_01/results.json',BASE/'sliding_projection_01/results.json',Path(independent.__file__),Path(analytical.__file__)]
    matrix_design=q.ROOT/'stage172_designs/four_hour_work_20260923/solver_design_01.json'
    matrices=api.read(matrix_design)['matrices'];inputs+=[matrix_design]+[Path(p) for p in matrices]
    protocol={'stage':'Stage194 all-sliding fallback zero-step qualification','new_trajectory_steps':0,'physics_changes':[],
              'original_limits':{'contact_residual':1e-10,'cone_excess_relative':1e-12,'force_residual':1e-8},
              'invariance_velocity_difference_free_scale_max':1e-10,'existing_successes_must_remain_exact':True,
              'scope':'Captured inputs are development data, not independent physical validation; no production authority.',
              'inputs':{str(p):api.sha(p) for p in inputs},'sources':oldd['sources'],'maximum_matrix_calls':250}
    job.commit(DESIGN,protocol);OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'protocol_sha256':api.sha(DESIGN),'new_trajectory_steps':0})
    systems=api.read(BASE/'contact_diagnosis_01/results.json')['captured_systems'];tests=[];captured=[];invariance=[];controls=[]
    runtime=job.parent.engine.runtime;job.parent.b.old.parent.configure();started=time.perf_counter()
    with job.prior.p.hot.scope(),job.parent.fix.scope():
        for i,s in enumerate(systems):
            a=args(s)
            try:
                result=repair.solve(*a,stop_epoch=end);check,row=audit(a,result)
                captured.append({'index':i,'passed':True,'audit':check,'saved_system':row})
            except Exception as e:captured.append({'index':i,'passed':False,'error':repr(e)});continue
            v,M,J,g,dt,mu,tol,maxiter=a;base=result[0]
            transforms=[]
            for perm in itertools.permutations(range(3)):
                idx=[3*k+j for k in perm for j in range(3)]
                transforms.append((f'permutation_{perm}',v,M,J[idx],g[list(perm)],np.eye(6),1.))
            for scale in [.1,10.]:transforms.append((f'scale_{scale}',v*scale,M,J,g*scale,np.eye(6),scale))
            R,_=np.linalg.qr(np.random.default_rng(194+i).normal(size=(3,3)))
            if np.linalg.det(R)<0:R[:,0]*=-1
            Q=np.zeros((6,6));Q[:3,:3]=R;Q[3:,3:]=R
            transforms.append(('rotated_frame',Q@v,Q@M@Q.T,J@Q.T,g,Q,1.))
            for name,vi,Mi,Ji,gi,Q,scale in transforms:
                api.require(time.time()<end,'work clock');aa=(vi,Mi,Ji,gi,dt,mu,tol,maxiter)
                try:
                    result=repair.solve(*aa,stop_epoch=end);check,_=audit(aa,result)
                    error=float(np.linalg.norm(Q.T@result[0]/scale-base)/max(np.linalg.norm(v),1e-15))
                    invariance.append({'index':i,'test':name,'passed':error<=1e-10,'velocity_difference_free_scale':error,'audit':check})
                except Exception as e:invariance.append({'index':i,'test':name,'passed':False,'error':repr(e)})
            print('CAPTURED_QUALIFIED',i,'invariance failures',sum(not x['passed'] for x in invariance if x['index']==i),flush=True)
        # Successful old reduced/general return is preserved, not substituted.
        for path in matrices:
            api.require(time.time()<end,'work clock');s=api.read(path)
            aa=(*[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps')],s['dt'],s['friction'],1e-10,25000)
            try:
                with job.fast.old.scope(runtime,True):expected=runtime.mixed.solve(*aa)
            except (RuntimeError,ValueError,np.linalg.LinAlgError):
                controls.append({'path':path,'reference_passed':False,'not_promoted':True});continue
            try:
                with repair.scope(runtime,True,end),job.fast.old.scope(runtime,True):got=runtime.mixed.solve(*aa)
                trim=lambda h:{k:v for k,v in h.items() if k!='certificate_seconds'}
                same=np.array_equal(expected[0],got[0]) and trim(expected[1])==trim(got[1]);check,_=audit(aa,got)
                controls.append({'path':path,'reference_passed':True,'passed':bool(same),'audit':check})
            except Exception as e:controls.append({'path':path,'reference_passed':True,'passed':False,'error':repr(e)})
        with repair.scope(runtime,True,end):toys=analytical.toys()
        # The wrapper must preserve unrelated exceptions and success identity.
        sentinel=(object(),object());mock=SimpleNamespace(mixed=SimpleNamespace(solve=lambda *a:sentinel));prior=mock.mixed.solve
        with repair.scope(mock,True,end):tests.append({'test':'success_object_identity','passed':mock.mixed.solve(*args(systems[0])) is sentinel})
        tests.append({'test':'success_scope_restored','passed':mock.mixed.solve is prior})
        error=RuntimeError('unrelated_failure')
        def fail(*a):raise error
        mock.mixed.solve=fail
        try:
            with repair.scope(mock,True,end):mock.mixed.solve(*args(systems[0]))
        except RuntimeError as e:tests.append({'test':'unrelated_error_identity','passed':e is error})
        tests.append({'test':'failure_scope_restored','passed':mock.mixed.solve is fail})
        aa=list(args(systems[0]))
        for name,index,value in [('negative_mobility',1,-aa[1]),('zero_dt',4,0.),('nan_gap',3,aa[3]*float('nan')),('changed_tolerance',6,1e-8)]:
            bad=list(aa);bad[index]=value
            try:repair.solve(*bad,stop_epoch=end)
            except (RuntimeError,ValueError,np.linalg.LinAlgError):tests.append({'test':name,'passed':True})
            else:tests.append({'test':name,'passed':False})
    for name,value in [('captured',captured),('invariance',invariance),('controls',controls),('analytical',toys),('guards',tests)]:job.commit(OUT/(name+'.json'),value)
    checked=captured+invariance+toys+tests+[x for x in controls if x['reference_passed']]
    passed=all(x['passed'] for x in checked)
    api.verify_mapping(protocol['inputs']);api.verify_mapping(protocol['sources']);job.verify(oldd)
    result={'passed':passed,'new_trajectory_steps':0,'captured_systems':len(captured),'invariance_checks':len(invariance),
            'old_successes_exact':sum(x.get('passed',False) for x in controls),'old_reference_failures_preserved':sum(not x['reference_passed'] for x in controls),
            'analytical_checks':len(toys),'guards':len(tests),'failed':[x for x in checked if not x['passed']],
            'protocol_sha256':api.sha(DESIGN),'wall_s':time.perf_counter()-started,'artifacts':{str(p):api.sha(p) for p in OUT.glob('*.json')}}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')})
    print('SLIDING_QUALIFICATION',passed,'failed',len(result['failed']),flush=True)


if __name__=='__main__':run()
