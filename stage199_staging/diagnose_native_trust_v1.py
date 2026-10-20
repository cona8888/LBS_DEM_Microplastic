"""Zero-step primitive attribution of the rejected native arithmetic mismatch."""
from pathlib import Path
import numpy as np
import native_trust_candidate_v1 as c
import qualify_native_trust_v1 as q

@c.compiled.numba.njit(cache=True,fastmath=False,parallel=False,error_model='numpy')
def parts(uf,s,V,alpha):
    suf=s*uf;s2=s*s;suf2=suf*suf;denom=s2+alpha;ratio=suf/denom;cubes=denom**3;terms=suf2/cubes
    return suf,s2,suf2,denom,ratio,cubes,terms,ratio.dot(ratio),c.sum9(terms),V.dot(ratio)

if __name__=='__main__':
    q.api.require(q.job.utc()<q.job.policy.utc(q.api.read(q.WORK)['work_end_utc']),'work cutoff')
    fixture=q.OUT.parent/'native_trust_mismatch_01.json';r=q.api.read(fixture)
    uf,s,V=[np.asarray(r[k]) for k in ('uf','s','V')];suf=s*uf;upper=np.sqrt(suf.dot(suf))/r['radius'];rows=[]
    names=['suf','s2','suf2','denom','ratio','cubes','terms','norm_dot','sum','matrix_vector']
    for alpha in (0.,.001*upper,upper,r['expected'][1]):
        denom=s**2+alpha;ratio=suf/denom;terms=suf**2/denom**3
        ref=(suf,s**2,suf**2,denom,ratio,denom**3,terms,ratio.dot(ratio),np.sum(terms),V.dot(ratio));actual=parts(uf,s,V,alpha)
        checks=[]
        for name,x,y in zip(names,ref,actual):
            a,b=np.asarray(x),np.asarray(y);exact=a.tobytes()==b.tobytes()
            checks.append({'operation':name,'exact':exact,'maximum_absolute_difference':float(np.max(np.abs(a-b)))})
        rows.append({'alpha':alpha,'checks':checks})
    out=q.OUT.parent/'native_trust_diagnosis_01.json'
    q.job.commit(out,{'new_trajectory_steps':0,'rejected_candidate_remains_rejected':True,'inputs':{str(x):q.api.sha(x) for x in (Path(__file__),Path(c.__file__),fixture)},'primitive_comparisons':rows})
    for row in rows:print('PRIMITIVE_MISMATCHES',row['alpha'],[x['operation'] for x in row['checks'] if not x['exact']],flush=True)
