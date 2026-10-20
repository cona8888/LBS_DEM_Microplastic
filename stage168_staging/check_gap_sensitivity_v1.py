"""Frozen-matrix counterfactual gap sensitivity; not a model repair.

Changing the algebraic gap input below is a diagnostic intervention only.
No altered input is used in any trajectory or promoted to production.
"""
import sys,time,copy
import numpy as np
import diagnose_frozen_contact_v3 as frozen
c=frozen.capture;api=c.api;hot=c.parent.b.old.hot
OUT=c.OUT.with_name('gap_sensitivity_01')


def main():
    d=api.read(c.DESIGN);c.verify(d)
    raw=api.read(c.OUT/'results.json')
    api.require(raw['diagnostic_integrity_passed'],'exact failure reproduction required')
    api.require(api.read(c.OUT/'completion.json')['results_sha256']==api.sha(c.OUT/'results.json'),'capture seal')
    api.verify_mapping({x['path']:x['sha256'] for x in raw['systems']})
    p=api.read(c.OUT/'system_002.json')
    v,M,J,g=[np.asarray(p[k],float) for k in ['vfree','mobility','jacobian','gaps']]
    modes=[('original',g),('one_thousandth_counterfactual',g*.001),('zero_counterfactual',g*0.)]
    OUT.mkdir(exist_ok=False)
    api.write(OUT/'protocol.json',{'source_sha256':api.sha(__file__),'matrix_sha256':api.sha(c.OUT/'system_002.json'),
        'tests':[name for name,_ in modes],'maximum_contact_solves':3,'max_pgs_each':25000,'max_lm_each':50000,
        'no_trajectory_integration':True,'original_gaps_preserved':True,
        'claim':'Gap sensitivity only. Altered-gap passes are NOT passes of the frozen contract or a qualified repair.'})
    c.parent.b.old.parent.configure()
    saved=(hot.s50._project,hot.s50._residual)
    tests=[]
    with hot.scope(),c.parent.fix.scope():
        hot.s50._project=hot.scalar.project;hot.s50._residual=hot.scalar.residual
        try:
            for name,gap in modes:
                started=time.perf_counter();entry={'id':name,'gaps':gap}
                try:
                    q,h=c.diag.backend.portfolio.s53._solve(v,M,J,gap,p['dt'],p['friction'],1e-10,25000)
                except (AttributeError,) as err:
                    raise RuntimeError('solver namespace mismatch') from err
                except RuntimeError as err:entry.update(passed=False,error=str(err))
                else:
                    force=np.asarray(h['reactions']);entry.update(passed=True,q=q,health=h,
                        residual_under_original_gaps=hot.scalar.residual(force,np.asarray(p['z']),np.asarray(p['A']),g,p['dt'],p['friction'],np.asarray(p['steps']))/np.linalg.norm(v))
                entry['wall_s']=time.perf_counter()-started;tests.append(entry)
        finally:hot.s50._project,hot.s50._residual=saved
    target=np.zeros(9);target[::3]=-g/p['dt']
    qstick=np.linalg.lstsq(J,target,rcond=1e-12)[0]
    result={'tests':tests,'all_stick_kinematic_least_squares':{'q':qstick,'residual':J@qstick-target,
            'max_error_m_s':max(abs(J@qstick-target)),'norm_error_m_s':np.linalg.norm(J@qstick-target)},
        'trajectory_steps_advanced':0,'production_changed':False,'counterfactual_only':True,
        'claim':'Does not establish non-existence of a sliding/open solution of the original system.',
        'protocol_sha256':api.sha(OUT/'protocol.json')}
    c.verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print('GAP',[(r['id'],r['passed'],r.get('residual_under_original_gaps')) for r in tests],flush=True)


if __name__=='__main__':main()
