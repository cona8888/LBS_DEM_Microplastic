"""Zero-step kernel identity and complete held contact regression."""
from pathlib import Path
from types import FunctionType
import sys,traceback
import numpy as np
import exact_dense_dispatch_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage198_staging'))
import qualify_direct_trf_v1 as tests
import qualify_trf_helpers_v1 as previous
api,job=tests.api,tests.job
WORK=previous.WORK;DESIGN=WORK.with_name('dense_dispatch_01.json');OUT=previous.OUT.with_name('dense_dispatch_01')
ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(candidate.__file__),Path(np.linalg._linalg.__file__),Path(candidate._umath_linalg.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (previous.DESIGN,previous.OUT/'results.json',previous.OUT.parent/'trf_helper_edges_01.json'):
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 same-kernel internal dense dispatch',dense_seed=19905,dense_arrays=1000,
        mode_meanings={'baseline':'constant arithmetic and original SciPy wrapper','direct':'Stage199 TRF helpers','compiled_direct':'same plus dense vector dispatch, original determinant gufunc and native finite SVD check'},
        helper_criteria='Identical determinant, SVD and internal norm bits and nonfinite rejection. Full optimizer results, health/velocity and original numerical gates exact. No change to BLAS/LAPACK drivers, algorithm decisions or controls.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('DENSE_DISPATCH_PROTOCOL',api.sha(DESIGN),flush=True)

def helpers():
    p=api.read(DESIGN);ns['verify'](p);api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    rng=np.random.default_rng(p['dense_seed']);dets=0;svds=0
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        for i in range(p['dense_arrays']):
            x=rng.normal(size=9)*(1.,1e-200,1e200)[i%3]
            for order in (None,np.inf):
                a,b=candidate.dense_norm(x,order),candidate.prior.norm(x,order)
                api.require(np.asarray(a).tobytes()==np.asarray(b).tobytes(),'exact internal dense norm')
            a=rng.normal(size=(i%17+1,6,6))
            if i%7==0:a[:,:,2]=a[:,:,1]
            for v in (a,np.asfortranarray(a),a[::-1]):
                before=v.tobytes();api.require(candidate.determinant(v).tobytes()==candidate.original_det(v).tobytes() and v.tobytes()==before,'original determinant gufunc, no mutation');dets+=1
            if i<100:
                m=rng.normal(size=(9,9))
                for v in (m,np.asfortranarray(m)):
                    a=candidate.svd_prior.original_svd(v,full_matrices=False);b=candidate.svd(v,full_matrices=False)
                    api.require(all(x.tobytes()==y.tobytes() for x,y in zip(a,b)),'identical finite-checked SVD');svds+=1
    for z in (np.nan,np.inf,-np.inf):
        m=np.eye(9);m[0,0]=z
        try:candidate.svd(m,full_matrices=False)
        except ValueError:pass
        else:raise AssertionError('nonfinite SVD accepted')
    candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1))
    candidate.prior.column_norms(np.eye(9));candidate.prior.max_abs(np.zeros(9));candidate.prior.all_finite(np.zeros(9))
    job.commit(OUT.parent/'dense_helper_edges_01.json',{'passed':True,'new_trajectory_steps':0,'determinant_checks':dets,'svd_checks':svds,'norm_checks':2*p['dense_arrays'],'nonfinite_rejections':3,'protocol_sha256':api.sha(DESIGN)})
    print('DENSE_HELPERS_EXACT',dets,svds,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:helpers();ns['run']()
        except Exception as e:
            path=OUT.parent/'dense_dispatch_failure_01.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
