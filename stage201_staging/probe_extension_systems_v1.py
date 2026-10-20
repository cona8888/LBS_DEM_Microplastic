"""Zero-step diagnosis of five independently authenticated new failures."""
from pathlib import Path
import os,time,traceback
import numpy as np
import probe_two_contact_scalar_v1 as scalar
import probe_two_contact_elimination_v1 as eliminated
import diagnose_two_contact_v1 as generic
job,api,ROOT=scalar.job,scalar.api,scalar.ROOT
BASE=ROOT/'stage201_evaluations/contact_repair_20260928'
OUT=BASE/'extension_system_diagnosis_01'


def run():
    w=api.read(scalar.source.WORK);end=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<end,'work cutoff');d=api.read(job.DESIGN);job.verify(d)
    fp=BASE/'extension_failure_audit_01/failed_systems.json';fr=api.read(fp.parent/'results.json')
    api.require(api.sha(fp)==fr['failed_systems_sha256'] and fr['evidence_audit_passed'] and not fr['numerical_gate_passed'],'authenticated failed systems only')
    inputs={str(p):api.sha(p) for p in (fp,fp.parent/'results.json',scalar.source.WORK,job.DESIGN,Path(__file__),Path(scalar.__file__),Path(eliminated.__file__))}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'inputs':inputs,'maximum_systems':5,'maximum_modes_per_system':9,'maximum_elimination_seeds_per_mode':6,'maximum_nfev_per_elimination_solve':2000})
    reports=[]
    try:
        with job.parent.fix.scope():
            for index,item in enumerate(api.read(fp)['failed_inner_systems']):
                s=item['system'];start=time.perf_counter();modes=scalar.solve_modes(s,end)
                flat=[c for m in modes for c in m['candidates']];near=[np.array(c['force']) for c in sorted(flat,key=lambda c:c['residual'])[:3]]
                alternative=eliminated.candidates(s,near,end)
                accepted=[c for m in alternative for c in m.get('candidates',[]) if c['accepted']]
                report={'index':index,'system_sha256':item['system_sha256'],'original_scalar_modes':modes,'eliminated_modes':alternative,'passed_alternative':bool(accepted),'seconds':time.perf_counter()-start}
                reports.append(report);job.commit(OUT/('system_%02d.json'%index),report)
                print('EXTENSION_HELD',index,bool(accepted),'best_scalar',min(c['residual'] for c in flat),'modes',[m['mode'] for m in alternative if any(c['accepted'] for c in m.get('candidates',[]))],flush=True)
        api.verify_mapping(inputs);job.verify(d)
        result={'new_trajectory_steps':0,'inputs':inputs,'systems':reports,'accepted_alternatives':sum(r['passed_alternative'] for r in reports),'claim':'Held equation probes only. Failed extension not promoted and no new trajectory.'}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    except Exception as error:job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise


if __name__=='__main__':run()
