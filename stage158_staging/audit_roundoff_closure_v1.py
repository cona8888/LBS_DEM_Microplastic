"""Read-only independent Decimal arithmetic and immutable evidence audit."""
from decimal import Decimal as D, localcontext
import numpy as np
import verify_roundoff_closure_v1 as v


def main():
    api=v.api;d=api.read(v.DESIGN);v.verify(d);r=api.read(v.OUT/'results.json')
    api.require(api.read(v.OUT/'completion.json')['results_sha256']==api.sha(v.OUT/'results.json'),'completion seal')
    api.verify_mapping(r['artifacts']);api.require(not (v.OUT/'failure.json').exists(),'no verification failure')
    unit=api.read(v.OUT/'unit_tests.json');replay=api.read(v.OUT/'replays.json')
    a=v.inputs_from_failure();free,M,J,f=a[:4];delta=M@J.T@f;q=free+delta
    with localcontext() as ctx:
        ctx.prec=100
        dd=lambda x:D.from_float(float(x))
        matrix=[[dd(x) for x in row] for row in M]
        b=[dd(x) for x in delta]
        # Independent forward elimination + back substitution (not Fraction/GJ).
        for k in range(6):
            pivot=max(range(k,6),key=lambda i:abs(matrix[i][k]))
            matrix[k],matrix[pivot]=matrix[pivot],matrix[k];b[k],b[pivot]=b[pivot],b[k]
            for i in range(k+1,6):
                ratio=matrix[i][k]/matrix[k][k]
                for j in range(k,6):matrix[i][j]-=ratio*matrix[k][j]
                b[i]-=ratio*b[k]
        x=[D(0)]*6
        for i in reversed(range(6)):x[i]=(b[i]-sum(matrix[i][j]*x[j] for j in range(i+1,6)))/matrix[i][i]
        force=[sum(dd(J[j,i])*dd(f[j]) for j in range(len(f))) for i in range(6)]
        relative=(sum((xx-ff)**2 for xx,ff in zip(x,force))/sum(ff*ff for ff in force)).sqrt()
        api.require(relative<D('1e-8'),'independent high precision force closure')
        api.require(all(float(dd(vv)+dd(dx))==qq for vv,dx,qq in zip(free,delta,q)),'independent rounded sum')
    recorded=unit['captured_new_health']['force_residual']
    api.require(abs(float(relative)-recorded)<=1e-12*max(recorded,1e-30),'independent arithmetic agreement')
    api.require(len(unit['random_cases'])==96 and all(x['force_residual']<=1e-8 for x in unit['random_cases']),'96 exact certificates')
    api.require(len(unit['negative_tests'])==11 and all(x['rejected'] for x in unit['negative_tests']),'11 negative tests')
    api.require(len(replay['healthy_replays'])==107 and all(x['error_over_U']==0 and x['momentum']<=1e-8 and x['work']<=1e-8 for x in replay['healthy_replays']),'107 identical replays')
    saved=v.old.hot.s50._finish;compiled=v.old.hot.PRIMARY.__globals__['_finish']
    try:
        with v.fix.scope():raise RuntimeError('deliberate scope exit')
    except RuntimeError:pass
    api.require(v.old.hot.s50._finish is saved and v.old.hot.PRIMARY.__globals__['_finish'] is compiled,'scope restoration on exception')
    out=v.OUT.parent/'independent_audit_01';out.mkdir(exist_ok=False)
    result={'audit_integrity_passed':True,'arithmetic_verification_passed':True,
            'independent_decimal_precision':100,'independent_unsummed_force_residual':float(relative),
            'evaluation_sha256':api.sha(v.OUT/'results.json'),'auditor_sha256':api.sha(__file__),
            'scope_restored_after_exception':True,'physics_changed':False,'production_promotion':False}
    api.write(out/'results.json',result);api.write(out/'completion.json',{'results_sha256':api.sha(out/'results.json'),'passed':True})
    print('INDEPENDENT AUDIT PASS',result,flush=True)


if __name__=='__main__':main()
