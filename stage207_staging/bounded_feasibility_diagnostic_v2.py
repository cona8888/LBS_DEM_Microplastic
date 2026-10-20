"""Administrative exact-endpoint split plan; unchanged v1 trajectory execution."""
from pathlib import Path
import os, sys, psutil
import bounded_feasibility_diagnostic_v1 as base

SELF=Path(__file__).resolve()
ORIGINAL=SELF.with_name('bounded_feasibility_diagnostic_v1.py')
OLD_WORK=base.WORK
NEW_WORK=OLD_WORK.with_name('exact_endpoint_amendment_01.json')
SERIAL=base.RUNBASE/'serial_01/results.json'
original_prerequisites=base.prerequisites
original_no_worker=base.no_worker

def create_amendment():
    w,d=original_prerequisites(); r=base.sealed(SERIAL)
    base.api.require(r['numerical_audit_passed'] and r['rejected']==0 and r['status']=='incomplete_budget','healthy original wall-budget pause')
    base.api.require(r['steps']==3645 and base.api.read(SERIAL.parent/'checkpoint.json')['state']['pending_trial'] is None,'authenticated exact serial endpoint')
    value=dict(w)
    value['planned_calls']=dict(w['planned_calls'],split_b_01=r['steps']-w['planned_calls']['split_a_01'])
    value['administrative_amendment']=dict(original_contract_sha256=base.api.sha(OLD_WORK),original_driver_sha256=base.api.sha(ORIGINAL),serial_results_sha256=base.api.sha(SERIAL),serial_target_new_steps=r['steps'],reason='Original wall budget stopped serial below reservation. Compare split at the actual identical step/time endpoint; no wall budget, physics, horizon, timestep or gate change.')
    base.job.commit(NEW_WORK,value)
    print('EXACT_ENDPOINT_AMENDMENT',r['steps'],value['planned_calls']['split_a_01'],value['planned_calls']['split_b_01'],flush=True)

def prerequisites():
    w,d=original_prerequisites()
    a=w['administrative_amendment']; old=base.api.read(OLD_WORK)
    base.api.require(a['original_contract_sha256']==base.api.sha(OLD_WORK) and a['original_driver_sha256']==base.api.sha(ORIGINAL) and a['serial_results_sha256']==base.api.sha(SERIAL),'sealed original protocol and actual endpoint')
    base.api.require(base.sealed(SERIAL)['steps']==a['serial_target_new_steps']==3645,'fixed actual endpoint')
    base.api.require({k:v for k,v in w.items() if k not in ('planned_calls','administrative_amendment')}=={k:v for k,v in old.items() if k!='planned_calls'},'all original limits and scientific criteria retained')
    expected=dict(old['planned_calls'],split_b_01=1145)
    base.api.require(w['planned_calls']==expected,'only bounded split remainder changed')
    return w,d

def no_worker():
    for p in psutil.process_iter(['name','cmdline']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        argv=p.info['cmdline'] or []
        base.api.require(not ('run' in argv and any(str(x) in argv for x in (SELF,ORIGINAL))),'one diagnostic worker across driver versions')

if __name__=='__main__':
    if sys.argv[1:]==['amend']:
        create_amendment()
    else:
        base.WORK=NEW_WORK; base.__file__=str(SELF)
        base.prerequisites=prerequisites; base.no_worker=no_worker
        if len(sys.argv)>=3 and sys.argv[1]=='prepare':base.prepare(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None)
        elif len(sys.argv)==3 and sys.argv[1]=='run':base.run(sys.argv[2])
        else:raise ValueError('amend | prepare NAME [SEED] | run NAME')
