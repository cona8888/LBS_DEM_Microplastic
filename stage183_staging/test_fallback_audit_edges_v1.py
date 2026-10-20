"""Zero-step independent-audit edge tests, including real roundoff evidence."""
from pathlib import Path
import copy,sys,time
import numpy as np
import qualify_fallback_evidence_v1 as job
physical=job.physical;api=job.api
sys.path.insert(0,str(job.ROOT/'stage158_staging'))
import verify_roundoff_closure_v1 as arithmetic
DESIGN=job.DESIGN.with_name('edge_design_01.json')
OUT=job.OUT.parent/'audit_edge_units_01'


def prepare():
    job.verify(api.read(job.DESIGN));api.require(api.read(job.OUT/'results.json')['passed'],'fallback recording prerequisite')
    arithmetic.verify(api.read(arithmetic.DESIGN))
    paths=[job.DESIGN,job.OUT/'results.json',job.OUT/'completion.json',arithmetic.DESIGN,arithmetic.FAILED,
        arithmetic.OUT/'unit_tests.json',arithmetic.OUT.parent/'independent_audit_01/results.json',job.RUN/'legacy_active_fallback.json.xz',
        (job.RUN/'legacy_active_fallback.json.xz').with_suffix('.seal.json')]
    d={'stage':'Stage183 independent audit edge units','new_trajectory_steps':0,'physical_changes':[],
        'sources':{str(Path(p).resolve()):api.sha(p) for p in [__file__,physical.__file__,job.kernel.__file__]},'inputs':{str(p):api.sha(p) for p in paths},
        'tests':['18 analytical one-contact systems','three analytical two-contact systems','actual saved roundoff system','96 independent Decimal arithmetic systems','corrupted record coverage guards'],
        'claim':'Audit arithmetic and coverage only; no integrator, force law or returned state changed.'}
    d['binding']=api.digest(d);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);job.verify(api.read(job.DESIGN))


def run():
    d=api.read(DESIGN);verify(d);OUT.mkdir(exist_ok=False);checks=[];guards=[];start=time.perf_counter()
    cases=[('stick',[-1,.1,0,0,0,0],0,[1,-.1,0],[0,0,0,0,0,0]),
           ('slip',[-1,1,0,0,0,0],0,[1,-.3,0],[0,.7,0,0,0,0]),
           ('open',[1,.2,0,0,0,0],0,[0,0,0],[1,.2,0,0,0,0]),
           ('no_premature_contact',[-1,.1,0,0,0,0],2,[0,0,0],[-1,.1,0,0,0,0]),
           ('gap_closure',[-1,1,0,0,0,0],.2,[.8,-.24,0],[-.2,.76,0,0,0,0]),
           ('penetration_recovery',[-1,1,0,0,0,0],-.2,[1.2,-.36,0],[.2,.64,0,0,0,0])]
    for scale in [1.,1e-7,1e3]:
        for name,v,g,f,q in cases:
            row={'accepted':True,'vfree':(np.array(v)*scale).tolist(),'mobility':np.eye(6).tolist(),'jacobian':np.eye(6)[:3].tolist(),
                'gaps_m':[g*scale],'dt_s':1.,'friction':.3,'velocity':(np.array(q)*scale).tolist(),'health':{'reactions':(np.array(f)*scale).tolist()}}
            checks.append({'case':name,'scale':scale,'audit':physical.physical(row)})
        row={'accepted':True,'vfree':(np.array([-1,.1,0,-.5,.1,0])*scale).tolist(),'mobility':np.eye(6).tolist(),'jacobian':np.eye(6).tolist(),
            'gaps_m':[0.,0.],'dt_s':1.,'friction':.3,'velocity':[0.]*6,'health':{'reactions':(np.array([1,-.1,0,.5,-.1,0])*scale).tolist()}}
        checks.append({'case':'two_independent_sticking_contacts','scale':scale,'audit':physical.physical(row)})
    args=arithmetic.inputs_from_failure();v,M,J,f=args[:4];increment=M@J.T@f;q=v+increment;health=api.read(arithmetic.OUT/'unit_tests.json')['captured_new_health']
    captured={'accepted':True,'vfree':v.tolist(),'mobility':M.tolist(),'jacobian':J.tolist(),'gaps_m':args[6].tolist(),
        'dt_s':args[7],'friction':args[8],'velocity':q.tolist(),'health':health}
    actual=physical.physical(captured);api.require(actual['decimal_roundoff_audit_used'],'captured certificate audited independently')
    expected=api.read(arithmetic.OUT.parent/'independent_audit_01/results.json')['independent_unsummed_force_residual']
    api.require(abs(actual['force_residual']-expected)<=1e-12*max(expected,1e-30),'prior independent 100-digit oracle')
    rng=np.random.default_rng(158);decimal=[]
    for condition in [1,100,10000]:
        for scale in [1e-4,1e-8,1e-12,1e-16]:
            for _ in range(8):
                Q=np.linalg.qr(rng.normal(size=(6,6)))[0];M=(Q*np.geomspace(1.,condition,6))@Q.T
                J=rng.normal(size=(3,6));f=rng.normal(size=3)*scale/condition;v=rng.normal(size=6);inc=M@J.T@f;q=v+inc
                decimal.append(physical.decimal_closure(v,M,J,f,inc,q))
    def reject(label,fn):
        try:fn()
        except (RuntimeError,ValueError,np.linalg.LinAlgError):guards.append(label);return
        raise AssertionError('audit accepted '+label)
    reject('bad_roundoff_velocity',lambda:physical.decimal_closure(v,M,J,f,inc,q+np.eye(6)[0]*1e-10))
    reject('bad_roundoff_increment',lambda:physical.decimal_closure(v,M,J,f,inc*1.1,v+inc*1.1))
    rec,_=job.codec.read_record(job.RUN/'legacy_active_fallback.json.xz',api.sha(job.DESIGN))
    physical.record_coverage(rec,job.fast.old.NAME)
    for label,edit in [('missing_system',lambda r:r['fallback_systems'].pop()),('false_runtime_accept',lambda r:r['result']['stage119_repair_calls'][0].update(accepted=False)),
        ('wrong_runtime_dt',lambda r:r['result']['stage119_repair_calls'][0].update(dt_s=123)),('wrong_solver',lambda r:r['repairs'][0].update(solver='not-qualified')),
        ('wrong_gap',lambda r:r['fallback_systems'][0]['gaps_m'].__setitem__(0,-1.)),('wrong_trial_output',lambda r:r['fallback_systems'][0]['velocity'].__setitem__(0,1.))]:
        bad=copy.deepcopy(rec);edit(bad);reject(label,lambda bad=bad:physical.record_coverage(bad,job.fast.old.NAME))
    report={'passed':True,'analytical_contacts':checks,'captured_roundoff_audit':actual,'independent_decimal_systems':len(decimal),'maximum_decimal_force_residual':max(decimal),
        'negative_guards':guards,'new_trajectory_steps':0,'wall_seconds':time.perf_counter()-start,'design_sha256':api.sha(DESIGN),'claim':d['claim']}
    verify(d);api.write(OUT/'results.json',report);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('AUDIT_EDGES_PASS',len(checks),len(decimal),len(guards),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
