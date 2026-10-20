"""Independent original-law audit for saved one-to-three contact systems."""
from decimal import Decimal as D,localcontext
from collections import Counter
import math
import numpy as np


def require(value,message):
    if not value:raise RuntimeError(message)


def decimal_closure(v,M,J,f,increment,q):
    with localcontext() as ctx:
        ctx.prec=100;dd=lambda x:D.from_float(float(x));mat=[[dd(x) for x in row] for row in M];rhs=[dd(x) for x in increment]
        for k in range(6):
            p=max(range(k,6),key=lambda i:abs(mat[i][k]));require(mat[p][k]!=0,'nonsingular independent mobility')
            mat[k],mat[p]=mat[p],mat[k];rhs[k],rhs[p]=rhs[p],rhs[k]
            for i in range(k+1,6):
                ratio=mat[i][k]/mat[k][k]
                for j in range(k,6):mat[i][j]-=ratio*mat[k][j]
                rhs[i]-=ratio*rhs[k]
        solved=[D(0)]*6
        for i in reversed(range(6)):solved[i]=(rhs[i]-sum(mat[i][j]*solved[j] for j in range(i+1,6)))/mat[i][i]
        load=[sum(dd(J[j,i])*dd(f[j]) for j in range(len(f))) for i in range(6)]
        error2=sum((a-b)**2 for a,b in zip(solved,load));den=max(sum(x*x for x in load),dd(1e-30)**2)
        require(error2<=dd(1e-8)**2*den,'independent unsummed force closure')
        require(all(float(dd(a)+dd(b))==c for a,b,c in zip(v,increment,q)),'independent correctly rounded velocity sum')
        return float((error2/den).sqrt())


def physical(row):
    require(row['accepted'] is True,'no rejected fallback solve')
    v,M,J,g,q=[np.asarray(row[k],float) for k in ['vfree','mobility','jacobian','gaps_m','velocity']]
    dt,mu=row['dt_s'],row['friction'];h=row['health'];f=np.asarray(h['reactions'],float);m=len(g)
    require(1<=m<=3 and v.shape==q.shape==(6,) and M.shape==(6,6) and J.shape==(3*m,6) and f.shape==(3*m,),'saved system dimensions')
    require(all(np.isfinite(x).all() for x in [v,M,J,g,q,f]) and np.isfinite([dt,mu]).all() and dt>0 and mu>0,'finite physical inputs')
    require(np.allclose(M,M.T,rtol=0,atol=1e-12*np.linalg.norm(M)),'symmetric mobility');np.linalg.cholesky(M)
    scale=max(np.linalg.norm(v),1e-15);force_scale=max(np.linalg.norm(f),1e-30);A=J@M@J.T;w=J@q;load=J.T@f
    balance=float(np.linalg.norm(np.linalg.solve(M,q-v)-load)/max(np.linalg.norm(load),1e-30));roundoff=False
    if balance>1e-8:
        require(h.get('roundoff_certificate_used') is True and h.get('exact_rational_inputs') is True and h.get('correctly_rounded_velocity_sum') is True,'explicit qualified arithmetic certificate')
        require(np.linalg.cond(M)<=1e8,'bounded certificate conditioning')
        balance=decimal_closure(v,M,J,f,M@J.T@f,q);roundoff=True
    require(np.isfinite(balance) and balance<=1e-8,'original force balance tolerance')
    terms=[];work=0.
    for k in range(m):
        i=3*k;eig=float(np.linalg.eigvalsh(A[i+1:i+3,i+1:i+3])[-1]);require(eig>0 and A[i,i]>0,'positive contact mobility')
        require(f[i]>=0 and np.linalg.norm(f[i+1:i+3])<=mu*f[i]+1e-12*force_scale,'independent Coulomb cone')
        trial=f[i+1:i+3]-w[i+1:i+3]/eig;projected=trial*min(1.,mu*f[i]/max(np.linalg.norm(trial),1e-300))
        terms.extend([abs(min(A[i,i]*f[i],w[i]+g[k]/dt)),np.linalg.norm(f[i+1:i+3]-projected)*eig]);work+=f[i+1:i+3]@w[i+1:i+3]
    residual=max(terms)/scale;require(residual<=1e-10,'original complementarity tolerance')
    require(work<=1e-8*max(np.linalg.norm(f)*scale,1e-30),'nonpositive frictional work tolerance')
    return {'passed':True,'contacts':m,'contact_residual':float(residual),'force_residual':balance,'decimal_roundoff_audit_used':roundoff}


def record_coverage(record,qualified_solver_name):
    calls=record['result']['stage119_repair_calls'];repairs=record['repairs'];systems=record.get('fallback_systems',[])
    require(len(calls)==len(repairs)==len(systems),'complete fallback input/output coverage')
    allowed=Counter((proof['dt_s'],*row['velocity_generalized']) for row,proof in zip(record['rows'],record['sweep_certificates']))
    for attempt in record['early_attempts']:
        if attempt['accepted']:
            key=(attempt['dt_s'],*attempt['velocity']);require(allowed[key]>0,'early solve belongs to accepted trial');allowed[key]-=1
    summaries=[]
    for call,repair,system in zip(calls,repairs,systems):
        require(call['accepted'] is True and repair['reduced_accepted'] is True and system['accepted'] is True,'only qualified successful fallback')
        require(call['health']==system['health'] and call['dt_s']==system['dt_s']==repair['dt_s'] and call['gaps_m']==system['gaps_m'],'runtime/fallback observer identity')
        require(system['health']['solver']==repair['solver']==qualified_solver_name and system['health']['original_gaps_preserved'] is True,'qualified unchanged original-gap fallback')
        key=(system['dt_s'],*system['velocity']);require(allowed[key]>0,'fallback force belongs to a distinct accepted trial');allowed[key]-=1
        summaries.append(physical(system))
    return summaries
