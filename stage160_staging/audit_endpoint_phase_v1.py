"""Independent rational toy evaluation; no application dynamics."""
from fractions import Fraction as F
import diagnose_endpoint_phase_v1 as v


def main():
    api=v.api;d=api.read(v.DESIGN);v.verify(d);r=api.read(v.OUT/'results.json')
    api.require(api.read(v.OUT/'completion.json')['results_sha256']==api.sha(v.OUT/'results.json'),'result seal')
    maximum=0.;violations=0
    for case in r['toy_cases']:
        t=F(case['impact_s']);endpoints=[]
        for observed in case['levels']:
            n=observed['n'];h=F(1,n);x=t-t*t/2;q=F(-1);imp=F(0)
            for _ in range(n):
                free=q+h;new=max(free,-x/h);imp+=new-free;x+=h*new;q=new
                api.require(x>=0,'exact toy nonpenetration')
            api.require(q==imp,'exact toy terminal momentum')
            maximum=max(maximum,abs(float(q)-observed['v']),abs(float(x)-observed['x']),abs(float(imp)-observed['impulse']))
            endpoints.append({'x':x,'v':q,'impulse':imp})
        for k in ['x','v','impulse']:
            differences=[abs(b[k]-a[k]) for a,b in zip(endpoints,endpoints[1:])]
            violations+=sum(b>F(4,5)*a and max(a,b)>F(1e-10) for a,b in zip(differences,differences[1:]))
    api.require(maximum<=1e-11 and violations==r['toy_nonmonotone_count'],'independent exact toy agreement')
    out=v.OUT.parent/'independent_audit_01';out.mkdir(exist_ok=False)
    result={'audit_integrity_passed':True,'exact_rational_toy_cases':len(r['toy_cases']),
            'exact_nonmonotone_comparisons':violations,'maximum_float_vs_rational_difference':maximum,
            'evaluation_sha256':api.sha(v.OUT/'results.json'),'auditor_sha256':api.sha(__file__),
            'application_qualification':False,'production_promotion':False}
    api.write(out/'results.json',result);api.write(out/'completion.json',{'results_sha256':api.sha(out/'results.json'),'passed':True})
    print('EXACT TOY AUDIT PASS',result,flush=True)


if __name__=='__main__':main()
