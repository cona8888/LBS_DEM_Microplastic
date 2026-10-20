"""Independent full-six-equation determinant check of mixed eliminands."""
from pathlib import Path
from fractions import Fraction as F
import os,sys,time,traceback
import authenticate_failed_system_v1 as source
job,api,ROOT=source.job,source.api,source.ROOT
BASE=ROOT/'stage210_evaluations/three_contact_failure_20261001'
POLY=BASE/'mixed_mode_polynomials_02/results.json'
OUT=BASE/'mixed_force_determinant_independent_01'


def invert(matrix):
    n=len(matrix);a=[[F(x) for x in row]+[F(i==j) for j in range(n)] for i,row in enumerate(matrix)]
    for col in range(n):
        pivot=max(range(col,n),key=lambda i:abs(a[i][col]));a[col],a[pivot]=a[pivot],a[col]
        factor=a[col][col];assert factor
        a[col]=[x/factor for x in a[col]]
        for row in range(n):
            if row!=col:
                factor=a[row][col];a[row]=[x-factor*y for x,y in zip(a[row],a[col])]
    answer=[row[n:] for row in a]
    assert all(sum((matrix[i][k]*answer[k][j] for k in range(n)),F(0))==int(i==j) for i in range(n) for j in range(n))
    return answer


def determinant(columns):
    n=len(columns);a=[[columns[j][i] for j in range(n)] for i in range(n)];det=F(1)
    for col in range(n):
        pivot=max(range(col,n),key=lambda i:abs(a[i][col]))
        if not a[pivot][col]:return F(0)
        if pivot!=col:a[col],a[pivot]=a[pivot],a[col];det=-det
        diagonal=a[col][col];det*=diagonal
        for row in range(col+1,n):
            factor=a[row][col]/diagonal
            for j in range(col+1,n):a[row][j]-=factor*a[col][j]
    return det


def dot(a,b):return sum((x*y for x,y in zip(a,b)),F(0))
def poly(p,y):return sum((F(x)*y**i for i,x in enumerate(p)),F(0))


def run():
    sys.set_int_max_str_digits(100000)
    d=api.read(job.DESIGN);job.verify(d);r=api.read(POLY)
    assert api.read(POLY.parent/'completion.json')['results_sha256']==api.sha(POLY)
    prior=BASE/'mixed_polynomial_independent_01/results.json'
    assert api.read(prior.parent/'completion.json')['results_sha256']==api.sha(prior)
    assert api.read(prior)['independent_eliminand_sturm_kinematic_audit_passed']
    fp=source.OUT/'failed_systems.json';item=api.read(fp)['failed_inner_systems'][0];s=item['system']
    assert api.digest(s)==item['system_sha256']==r['system_sha256']
    J=[[F.from_float(float(x)) for x in row] for row in s['jacobian']]
    M=[[F.from_float(float(x)) for x in row] for row in s['mobility']];B=invert(M)
    v=[F.from_float(float(x)) for x in s['vfree']];mu=F.from_float(s['friction'])
    inputs={str(p):api.sha(p) for p in (Path(__file__),job.DESIGN,source.WORK,POLY,prior,fp)}
    OUT.mkdir(parents=True,exist_ok=False);end=time.time()+600
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,inputs=inputs,maximum_determinant_checks=156,maximum_wall_seconds=600))
    checks=[]
    try:
        for m in r['modes']:
            q0=[F(x) for x in m['exact_velocity_particular']];N=[F(x) for x in m['exact_velocity_direction']];qs=F(m['velocity_scale'])
            stick=m['sticking_contact'];slide=[k for k in range(3) if k!=stick];ratio=None;count=0
            for y in range(-6,7):
                assert time.time()<end
                normalized=[a+b*y for a,b in zip(q0,N)];q=[qs*x for x in normalized]
                load=[dot(row,[a-b for a,b in zip(q,v)]) for row in B]
                pairs=[]
                for k in slide:
                    tangents=[dot(J[3*k+j],normalized) for j in (1,2)]
                    tangent=[-mu*(J[3*k+1][i]*tangents[0]+J[3*k+2][i]*tangents[1]) for i in range(6)]
                    pairs.append((J[3*k],tangent))
                    assert sum(x*x for x in tangents)==poly(m['radical_polynomials']['Q%d'%(len(pairs))],F(y))
                fixed=J[3*stick:3*stick+3]
                for name,choices in (('A',(1,1)),('B',(0,1)),('C',(1,0)),('D',(0,0))):
                    physical=determinant([*fixed,pairs[0][choices[0]],pairs[1][choices[1]],load])
                    projected=poly(m['radical_polynomials'][name],F(y));count+=1
                    if not projected:assert not physical
                    elif ratio is None:ratio=physical/projected;assert ratio
                    else:assert physical==ratio*projected
            assert ratio
            checks.append(dict(sticking_contact=stick,full_six_equation_coefficients_checked=count,normalization=str(ratio),polynomial_degree_bound=3))
            print('INDEPENDENT_FORCE_DETERMINANT',stick,count,flush=True)
        api.verify_mapping(inputs)
        result=dict(independent_full_force_determinant_audit_passed=True,new_trajectory_steps=0,checks=checks,inputs=inputs,
          claim='Exact full-six-equation determinant coefficients equal projected eliminands up to a nonzero constant;13 rational points suffice for degree<=3 coefficients. Combined with separate Sturm proof this certifies necessary ideal-mode polynomial census, not physical root classification, all frictional modes, or tolerance-global infeasibility.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json')))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0,checks=checks));raise


if __name__=='__main__':run()
