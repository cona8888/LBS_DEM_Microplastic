"""Zero-step exact helper and full outer/optimizer regression qualification."""
from pathlib import Path
from types import FunctionType
import inspect,sys,traceback
import numpy as np
import exact_solver_dispatch_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage198_staging'))
import qualify_direct_trf_v1 as tests
import qualify_direct_trf_v2 as previous
api,job=tests.api,tests.job
WORK=ROOT/'stage199_designs/eight_hour_optimization_20260926/contract_01.json'
DESIGN=WORK.with_name('solver_dispatch_01.json')
OUT=ROOT/'stage199_evaluations/eight_hour_optimization_20260926/solver_dispatch_01'
ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(candidate.__file__),Path(candidate.batch.__file__),Path(candidate.batch.original.__file__),Path(inspect.getmodule(candidate.get_lapack_funcs).__file__),Path(inspect.getmodule(candidate.original_svd).__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (WORK,previous.DESIGN,previous.OUT/'results.json',ROOT/'stage199_evaluations/eight_hour_optimization_20260926/profile_01/results.json'):
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 exact array and LAPACK dispatch optimization',helper_random_seed=199,helper_batch_arrays=100,helper_svd_matrices=60,recovery_steps_before=53086,
        modes=['baseline','direct','compiled_direct'],mode_meanings={'baseline':'constant arithmetic and original SciPy wrapper','direct':'qualified Stage198 compiled/direct implementation','compiled_direct':'Stage199 exact E-array assembly and cached fixed-dimension LAPACK workspace dispatch'},
        helper_criteria='Exact E/valid bits, exact SVD outputs, matching invalid-input rejections; unchanged TRF and trust-region code objects and all tolerances.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('SOLVER_DISPATCH_PROTOCOL',api.sha(DESIGN),flush=True)

def helpers():
    p=api.read(DESIGN);ns['verify'](p);work=api.read(WORK);api.require(job.utc()<job.policy.utc(work['work_end_utc']),'agent work cutoff')
    rng=np.random.default_rng(p['helper_random_seed']);batch_tests=0;svd_tests=0
    for i in range(p['helper_batch_arrays']):
        n=(1,3,17,257)[i%4];w=rng.normal(size=(n,9))*(1.,1e-160,1e150,1e-20)[i%4]
        if i%5==0:w[:1,:]=0.;w[0,1]=-0.
        for stick in range(3):
            mu=.3;E=np.zeros((n,9,5));col=0;valid=np.ones(n,dtype=bool)
            for k in range(3):
                if k==stick:
                    for j in range(3):E[:,3*k+j,col]=1.;col+=1
                else:
                    vt=w[:,3*k+1:3*k+3];speed=np.linalg.norm(vt,axis=1);valid &= speed>0;E[:,3*k,col]=1.
                    E[:,3*k+1:3*k+3,col]=-mu*vt/np.where(speed>0,speed,1.)[:,None];col+=1
            actual,flags=candidate.batch.equation_arrays(w,stick,mu)
            api.require(E.tobytes()==actual.tobytes() and valid.tobytes()==flags.tobytes(),'bit-exact batch array and validity');batch_tests+=1
    for i in range(p['helper_svd_matrices']):
        m=rng.normal(size=(9,9))
        if i%4==0:m[:,3]=m[:,2]
        if i%9==0:m[:]=0.
        for matrix in (m.copy(),np.asfortranarray(m),np.tile(m,(2,2))[::2,::2]):
            before=matrix.tobytes();ref=candidate.original_svd(matrix,full_matrices=False);actual=candidate.svd(matrix,full_matrices=False)
            api.require(all(x.tobytes()==y.tobytes() for x,y in zip(ref,actual)) and matrix.tobytes()==before,'bit-exact original LAPACK and no input mutation');svd_tests+=1
    for value in (float('nan'),float('inf'),-float('inf')):
        m=np.eye(9);m[0,0]=value;outcomes=[]
        for fn in (candidate.original_svd,candidate.svd):
            try:fn(m,full_matrices=False);outcomes.append(None)
            except Exception as e:outcomes.append(type(e).__name__)
        api.require(outcomes==['ValueError','ValueError'],'finite input checks preserved')
    api.require(candidate.trf_no_bounds.__code__ is candidate.prior.trf_no_bounds.__code__,'original TRF algorithm bytecode')
    result={'passed':True,'new_trajectory_steps':0,'batch_array_tests':batch_tests,'svd_tests':svd_tests,'nonfinite_rejections':3,'protocol_sha256':api.sha(DESIGN)}
    job.commit(OUT.parent/'solver_helper_edges_01.json',result);print('HELPERS_EXACT',batch_tests,svd_tests,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:helpers();ns['run']()
        except Exception as e:
            path=OUT.parent/'solver_helper_failure_01.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
