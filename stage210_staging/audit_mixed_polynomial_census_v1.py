"""Independent rational validation of eliminand identity and Sturm census.

Does not promote floating root classification to an interval mechanics proof.
"""
from pathlib import Path
from fractions import Fraction as F
import copy,os,sys,traceback
import authenticate_failed_system_v1 as source
job,api,ROOT=source.job,source.api,source.ROOT
BASE=ROOT/'stage210_evaluations/three_contact_failure_20261001'
POLY=BASE/'mixed_mode_polynomials_02/results.json'
OUT=BASE/'mixed_polynomial_independent_01'


def evaluate(p,x):
    return sum((F(c)*x**i for i,c in enumerate(p)),F(0))


def polynomial_remainder(a,b):
    a=[F(x) for x in a];b=[F(x) for x in b]
    while len(a)>=len(b):
        coefficient=a[-1]/b[-1];power=len(a)-len(b)
        for i,x in enumerate(b):a[power+i]-=coefficient*x
        while a and not a[-1]:a.pop()
    return a or [F(0)]


def variations(chain,x):
    signs=[1 if y>0 else -1 for y in (evaluate(p,x) for p in chain) if y]
    return sum(signs[i]!=signs[i+1] for i in range(len(signs)-1))


def check(mode,s):
    p=[int(x) for x in mode['integer_polynomial_coefficients']];chain=[[int(x) for x in row] for row in mode['sturm_chain']]
    assert len(p)-1==mode['polynomial_degree'] and p==chain[0] and p[-1]
    derivative=[i*p[i] for i in range(1,len(p))]
    ratio=F(derivative[-1],chain[1][-1]);assert ratio>0
    assert [ratio*x for x in chain[1]]==derivative
    for a,b,c in zip(chain,chain[1:],chain[2:]):
        rem=polynomial_remainder(a,b);ratio=-rem[-1]/c[-1]
        assert ratio>0 and [-ratio*x for x in c]==rem
    assert polynomial_remainder(chain[-2],chain[-1])==[0]
    C={k:[F(x) for x in v] for k,v in mode['radical_polynomials'].items()}
    # At 15 distinct rational points verify the necessary squared polynomial
    # identity up to its constant rational normalization (degree at most12).
    normalization=None
    for y in range(-7,8):
        A,B,Cc,D,Q1,Q2=[evaluate(C[k],F(y)) for k in ('A','B','C','D','Q1','Q2')]
        E=A*A+B*B*Q1-Q2*(Cc*Cc+D*D*Q1);G=2*(A*B-Q2*Cc*D)
        exact=E*E-G*G*Q1;pv=evaluate(p,F(y))
        if not pv:assert not exact
        elif normalization is None:normalization=exact/pv
        else:assert exact==normalization*pv
    assert normalization and max(len(x)-1 for x in C.values())<=3 and len(C['Q1'])<=3 and len(C['Q2'])<=3
    q0=[F(x) for x in mode['exact_velocity_particular']];N=[F(x) for x in mode['exact_velocity_direction']];qs=F(mode['velocity_scale'])
    J=[[F.from_float(float(x)) for x in row] for row in s['jacobian']]
    for k in range(3):
        target=F.from_float(float(-s['gaps_m'][k]/s['dt_s']))
        assert sum((a*b for a,b in zip(J[3*k],q0)),F(0))*qs==target
        assert sum((a*b for a,b in zip(J[3*k],N)),F(0))==0
        if k==mode['sticking_contact']:
            for row in J[3*k+1:3*k+3]:
                assert sum((a*b for a,b in zip(row,q0)),F(0))==0
                assert sum((a*b for a,b in zip(row,N)),F(0))==0
    bound=F(2)+max(abs(F(c,p[-1])) for c in p[:-1])
    count=variations(chain,-bound)-variations(chain,bound)
    intervals=[(F(z['left']),F(z['right'])) for z in mode['root_intervals']]
    assert count==mode['exact_real_polynomial_roots']==len(intervals)
    for a,b in intervals:
        assert -bound<a<b<bound and variations(chain,a)-variations(chain,b)==1
    assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:]))
    return count


def run():
    sys.set_int_max_str_digits(100000)
    d=api.read(job.DESIGN);job.verify(d);r=api.read(POLY);bridge=api.read(POLY.parent/'serialization_bridge.json')
    assert api.read(POLY.parent/'completion.json')['results_sha256']==api.sha(POLY)==bridge['results_sha256']
    api.verify_mapping(r['inputs']);api.verify_mapping(bridge['inputs'])
    fp=source.OUT/'failed_systems.json';item=api.read(fp)['failed_inner_systems'][0]
    assert api.digest(item['system'])==item['system_sha256']==r['system_sha256']
    inputs={str(p):api.sha(p) for p in (Path(__file__),POLY,POLY.parent/'serialization_bridge.json',fp,job.DESIGN,source.WORK)}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0))
    try:
        counts=[check(m,item['system']) for m in r['modes']];rejected=[]
        for label in ('polynomial','derivative','root_count','velocity_constraint'):
            bad=copy.deepcopy(r['modes'][0])
            if label=='polynomial':bad['integer_polynomial_coefficients'][0]=str(int(bad['integer_polynomial_coefficients'][0])+1)
            elif label=='derivative':bad['sturm_chain'][1][0]=str(int(bad['sturm_chain'][1][0])+1)
            elif label=='root_count':bad['exact_real_polynomial_roots']+=1
            else:bad['exact_velocity_particular'][0]=str(F(bad['exact_velocity_particular'][0])+1)
            try:check(bad,item['system'])
            except AssertionError:rejected.append(label)
            else:raise AssertionError('corruption accepted '+label)
        api.verify_mapping(inputs)
        result=dict(independent_eliminand_sturm_kinematic_audit_passed=True,new_trajectory_steps=0,ideal_mode_root_counts=counts,
          corrupt_controls_rejected=rejected,inputs=inputs,
          claim='Independent exact rational squared-eliminand identity, original kinematic constraints, Sturm chain and complete real-polynomial root count. Does not independently derive force determinant coefficients or certify physical admissibility/sign intervals; no all-mode/tolerance-global infeasibility claim.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json')));print(result,flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
