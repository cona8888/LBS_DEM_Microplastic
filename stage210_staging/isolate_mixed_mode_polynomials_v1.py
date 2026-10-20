"""Exact-rational necessary polynomial census for one-stick/two-slip modes.

Squaring introduces extraneous roots. This does NOT prove all friction modes
or tolerance-admitted candidates infeasible. Uses one saved system, zero steps.
"""
from pathlib import Path
from fractions import Fraction as F
from functools import reduce
from math import gcd,lcm
import itertools,os,time,traceback
import numpy as np
import authenticate_failed_system_v1 as source
import certify_sticking_kinematics_v1 as null
job,api,ROOT=source.job,source.api,source.ROOT
OUT=ROOT/'stage210_evaluations/three_contact_failure_20261001/mixed_mode_polynomials_01'
END=None


def clock():
    if time.time()>END:raise RuntimeError('bounded polynomial diagnosis clock')


def trim(p):
    p=list(p)
    while len(p)>1 and not p[-1]:p.pop()
    return p


def add(p,q):return trim([(p[i] if i<len(p) else 0)+(q[i] if i<len(q) else 0) for i in range(max(len(p),len(q)))])
def neg(p):return [-x for x in p]
def mul(p,q):
    r=[F(0)]*(len(p)+len(q)-1)
    for i,a in enumerate(p):
        for j,b in enumerate(q):r[i+j]+=a*b
    return trim(r)


def primitive(p):
    p=trim([F(x) for x in p]);den=lcm(*(x.denominator for x in p));ints=[x.numerator*(den//x.denominator) for x in p]
    common=reduce(gcd,(abs(x) for x in ints));return [x//common for x in ints] if common else [0]


def rem(a,b):
    r=[F(x) for x in a];b=[F(x) for x in b]
    while len(r)>=len(b) and any(r):
        clock();factor=r[-1]/b[-1];offset=len(r)-len(b)
        for i,x in enumerate(b):r[offset+i]-=factor*x
        r=trim(r)
    return primitive(r)


def value(p,x):
    v=F(0)
    for a in reversed(p):v=v*x+a
    return v


def sturm(p):
    rows=[primitive(p),primitive([i*p[i] for i in range(1,len(p))])]
    while any(rows[-1]):
        r=neg(rem(rows[-2],rows[-1]))
        if not any(r):break
        rows.append(r)
    return rows


def variations(rows,x):
    values=[value(p,x) for p in rows];signs=[1 if x>0 else -1 for x in values if x]
    return sum(a!=b for a,b in zip(signs,signs[1:]))


def isolate(p):
    rows=sturm(p);bound=1+max((abs(F(x,p[-1])) for x in p[:-1]),default=F(0))
    bound=F(bound.numerator//bound.denominator+2);total=variations(rows,-bound)-variations(rows,bound)
    queue=[(-bound,bound,total)];intervals=[];iterations=0
    while queue:
        clock();a,b,n=queue.pop();iterations+=1
        if iterations>50000:raise RuntimeError('bounded isolation subdivisions')
        if not n:continue
        if n==1 and b-a<=F(1,10**13)*max(F(1),abs(a),abs(b)):
            intervals.append((a,b));continue
        mid=(a+b)/2
        # Avoid an exact rational root at an interval boundary.
        if value(p,mid)==0:
            for divisor in range(3,20):
                mid=a+(b-a)/divisor
                if value(p,mid)!=0:break
            else:raise RuntimeError('rational-root boundary unresolved')
        left=variations(rows,a)-variations(rows,mid)
        queue.extend([(a,mid,left),(mid,b,n-left)])
    assert len(intervals)==total
    return rows,sorted(intervals),total,iterations


def rref(matrix):
    a=[[F(x) for x in row] for row in matrix];r=0;piv=[]
    for c in range(len(a[0])-1):
        pivot=next((i for i in range(r,len(a)) if a[i][c]),None)
        if pivot is None:continue
        a[r],a[pivot]=a[pivot],a[r];v=a[r][c];a[r]=[x/v for x in a[r]]
        for i in range(len(a)):
            if i!=r:
                v=a[i][c];a[i]=[x-v*y for x,y in zip(a[i],a[r])]
        piv.append(c);r+=1
        if r==len(a):break
    return a,piv


def inverse(m):
    n=len(m);a=[[F(x) for x in row]+[F(i==j) for j in range(n)] for i,row in enumerate(m)]
    for c in range(n):
        pivot=next(i for i in range(c,n) if a[i][c]);a[c],a[pivot]=a[pivot],a[c]
        v=a[c][c];a[c]=[x/v for x in a[c]]
        for i in range(n):
            if i!=c:
                v=a[i][c];a[i]=[x-v*y for x,y in zip(a[i],a[c])]
    return [row[n:] for row in a]


def dot(a,b):return sum((x*y for x,y in zip(a,b)),F(0))


def determinant(columns):
    result=[F(0)]
    for perm in itertools.permutations(range(3)):
        sign=(-1)**sum(perm[i]>perm[j] for i in range(3) for j in range(i+1,3))
        term=[F(sign)]
        for col,row in enumerate(perm):term=mul(term,columns[col][row])
        result=add(result,term)
    return result


def mode(s,sticking):
    J=[[F.from_float(float(x)) for x in row] for row in s['jacobian']]
    M=[[F.from_float(float(x)) for x in row] for row in s['mobility']];B=inverse(M)
    v=[F.from_float(float(x)) for x in s['vfree']];mu=F.from_float(s['friction'])
    target=[F.from_float(float(-x/s['dt_s'])) for x in s['gaps_m']]
    qs=F.from_float(max(abs(float(x)) for x in target))
    C=[]
    for k in range(3):
        C.append(J[3*k]+[target[k]/qs])
        if k==sticking:C.extend([J[3*k+1]+[F(0)],J[3*k+2]+[F(0)]])
    reduced,piv=rref(C);assert len(piv)==5
    free=next(c for c in range(6) if c not in piv)
    q0=[F(0)]*6;direction=[F(0)]*6;direction[free]=F(1)
    for row,c in zip(reduced,piv):q0[c]=row[-1];direction[c]=-row[free]
    assert all(dot(row[:6],q0)==row[-1] and dot(row[:6],direction)==0 for row in C)
    _,left=null.exact_nullspace(np.asarray(s['jacobian'])[3*sticking:3*sticking+3])
    assert len(left)==3
    load=[[dot(row,[qs*x-y for x,y in zip(q0,v)]),dot(row,direction)*qs] for row in B]
    projected_load=[[sum((w[i]*load[i][j] for i in range(6)),F(0)) for j in range(2)] for w in left]
    slide=[k for k in range(3) if k!=sticking];parts=[];quadratics=[]
    for k in slide:
        tangents=[[dot(J[3*k+j],q0),dot(J[3*k+j],direction)] for j in (1,2)]
        quadratics.append(add(mul(tangents[0],tangents[0]),mul(tangents[1],tangents[1])))
        normal=[[dot(w,J[3*k])] for w in left]
        tangent=[]
        for w in left:
            tangent.append(neg([mu*sum((dot(w,J[3*k+j+1])*tangents[j][degree] for j in range(2)),F(0)) for degree in range(2)]))
        parts.append((normal,tangent))
    # D = A + B*sqrt(Q1) + C*sqrt(Q2) + D*sqrt(Q1*Q2).
    A=determinant([parts[0][1],parts[1][1],projected_load])
    bb=determinant([parts[0][0],parts[1][1],projected_load])
    cc=determinant([parts[0][1],parts[1][0],projected_load])
    dd=determinant([parts[0][0],parts[1][0],projected_load])
    Q1,Q2=quadratics
    E=add(add(mul(A,A),mul(mul(bb,bb),Q1)),neg(mul(Q2,add(mul(cc,cc),mul(mul(dd,dd),Q1)))))
    FF=add([2*x for x in mul(A,bb)],neg([2*x for x in mul(mul(cc,dd),Q2)]))
    P=primitive(add(mul(E,E),neg(mul(mul(FF,FF),Q1))))
    assert any(P) and len(P)<=17
    seq,intervals,total,subdivisions=isolate(P)
    return dict(sticking_contact=sticking,polynomial_degree=len(P)-1,integer_polynomial_coefficients=[str(x) for x in P],
      maximum_coefficient_bits=max(abs(x).bit_length() for x in P),sturm_chain=[[str(x) for x in row] for row in seq],
      exact_real_polynomial_roots=total,subdivisions=subdivisions,
      root_intervals=[dict(left=str(a),right=str(b),approximate=float((a+b)/2)) for a,b in intervals],
      exact_velocity_particular=[str(x) for x in q0],exact_velocity_direction=[str(x) for x in direction],velocity_scale=str(qs),
      radical_polynomials={name:[str(x) for x in p] for name,p in zip(('A','B','C','D','Q1','Q2'),(A,bb,cc,dd,Q1,Q2))},
      claim='Complete real-root count of necessary squared polynomial for this exact ideal mode only. Roots may be extraneous; no physical/tolerance-global infeasibility claim.')


def run():
    global END
    d=api.read(job.DESIGN);job.verify(d);w=api.read(source.WORK);assert w['maximum_new_trajectory_steps']==0
    fp=source.OUT/'failed_systems.json';proof=api.read(source.OUT/'results.json');assert api.sha(fp)==proof['failed_systems_sha256']
    item=api.read(fp)['failed_inner_systems'][0];assert api.digest(item['system'])==item['system_sha256']
    inputs={str(p):api.sha(p) for p in (Path(__file__),source.WORK,job.DESIGN,fp,Path(null.__file__))}
    OUT.mkdir(parents=True,exist_ok=False);END=time.time()+900
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),inputs=inputs,new_trajectory_steps=0,maximum_systems=1,maximum_modes=3,maximum_wall_seconds=900))
    modes=[]
    try:
        for k in range(3):
            r=mode(item['system'],k);modes.append(r);job.commit(OUT/('mode_%d.json'%k),r)
            print('POLYNOMIAL_MODE',k,r['polynomial_degree'],r['exact_real_polynomial_roots'],r['subdivisions'],flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result=dict(new_trajectory_steps=0,system_sha256=item['system_sha256'],inputs=inputs,modes=modes,no_repair_installed=True,
          claim='Exact necessary-polynomial/Sturm root census for three ideal one-stick/two-slip modes at the first saved timestep. Squaring adds extraneous roots and classification remains required. Not an admissible-step or global frictional infeasibility proof.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json')))
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0,modes_completed=len(modes)));raise


if __name__=='__main__':run()
