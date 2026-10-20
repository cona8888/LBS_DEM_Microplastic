"""Independent Decimal closest-surface calculation on exact binary64 inputs."""
import json
import sys
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage89_staging'))
import verify_short_seed_local_v1 as h
OUT=ROOT/'stage100_evaluations/high_precision_gaps_01'
CAP=ROOT/'stage99_evaluations/first_failure_01/capture.json'
CASE=ROOT/'stage96_runs/population_prefix_01/s2_i0_prolate_ar4.json'
def D(x): return Decimal.from_float(float(x))
def dot(a,b): return sum((x*y for x,y in zip(a,b)),Decimal(0))

def gap(x,p,a,b,c,r,L,precision):
    with localcontext() as ctx:
        ctx.prec=precision
        x=list(map(D,x));p=list(map(D,p));c=list(map(D,c))
        a,b,r,L=map(D,(a,b,r,L))
        n=dot(p,p).sqrt();p=[q/n for q in p]
        d=[q-y for q,y in zip(c,x)]
        d=[q-L*(q/L).to_integral_value(rounding=ROUND_HALF_EVEN) for q in d]
        v=[q/a for q in d];s=dot(v,p)
        para=[s*q for q in p];trans=[q-z for q,z in zip(v,para)]
        rp=(b/a)**2;vp=dot(para,para);vt=dot(trans,trans)
        def f(t):return vp/(1+t)**2+rp*vt/(rp+t)**2-1
        if f(Decimal(0))<=0:raise ValueError('grain centre inside ellipsoid')
        lo=Decimal(0);hi=max(Decimal(1),dot(v,v).sqrt())
        while f(hi)>0:hi*=2
        for _ in range(4*precision):
            mid=(lo+hi)/2
            if f(mid)>0:lo=mid
            else:hi=mid
        t=(lo+hi)/2
        lever=[a*(q/(1+t)+rp*z/(rp+t)) for q,z in zip(para,trans)]
        delta=[q-z for q,z in zip(d,lever)]
        return dot(delta,delta).sqrt()-r

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(h.DESIGN.read_text());state=json.loads(CASE.read_text())['result']
    capture=json.loads(CAP.read_text())
    _,geom,_,_,_=h.matrix_case_v1.load(2)
    a,b,_=cfg['prolate_semiaxes_m']
    protocol=dict(precisions=[60,90],input_conversion='exact float via Decimal.from_float',
                  source_hashes={str(Path(__file__)):h.sha(__file__)},
                  input_hashes={str(p):h.sha(p) for p in (CAP,CASE,h.DESIGN)},
                  scope='Independent fixed-pose geometry audit, no transport or state correction.')
    h.dump(OUT/'protocol.json',protocol)
    sphere=[]
    for prec in [60,90]:
        val=gap([0,0,0],[1,0,0],.125,.125,[.5,0,0],.125,2.,prec)
        sphere.append(abs(val-Decimal('.25'))<Decimal('1e-50'))
    rows=[]
    for contact in capture['step_args'][6]:
        k=int(contact[0]);old=contact[1]
        values=[gap(state['position_m'],state['orientation'],a,b,geom.c[k],geom.r[k],geom.L,prec) for prec in [60,90]]
        row=dict(grain_id=k,original_gap_m=old,high_precision_gap_m=[str(v) for v in values],
                 precision_agreement_m=str(abs(values[0]-values[1])),
                 double_error_m=float(D(old)-values[1]),negative_at_both=all(v<0 for v in values),
                 centre_m=geom.c[k].tolist(),radius_m=float(geom.r[k]))
        rows.append(row)
    result=dict(sphere_tests_passed=all(sphere),precision_agreement_passed=all(Decimal(r['precision_agreement_m'])<Decimal('1e-50') for r in rows),
                rows=rows,protocol_sha256=h.sha(OUT/'protocol.json'),cell_length_m=float(geom.L),
                position_m=state['position_m'],orientation=state['orientation'],axes_m=[a,b,b])
    h.dump(OUT/'results.json',result)
    h.dump(OUT/'completion.json',dict(status='complete_audited',results_sha256=h.sha(OUT/'results.json')))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
