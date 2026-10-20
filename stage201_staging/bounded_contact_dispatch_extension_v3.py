"""Serial bounded local extension; maximum10,000 accepted steps in10 calls.

This is not a production campaign. Each call has its own immutable launch,
raw, numerical audit, checkpoint and step ledger through the qualified runner.
The driver filename/argv intentionally match the runner's single-worker guard.
"""
from pathlib import Path
import os,sys,time,traceback
import bounded_contact_dispatch_v3 as harness
r=harness.ns;job,api,ROOT=r['job'],r['api'],r['ROOT']
BASE=r['EVALBASE'];OUT=BASE/'bounded_extension_01';DESIGN=r['DESIGNBASE']/'bounded_extension_01.json'
SELF=Path(__file__).resolve()


def prepare():
    w=api.read(r['source'].WORK);api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'trajectory launch window')
    closure=r['sealed_result'](BASE/'local_closure_01/results.json');api.require(closure['passed'] and closure['window_total_accepted_steps']==30277,'independent complete local closure')
    used,pending=r['ledger']();api.require(used==30277 and not pending,'known resolved window budget');r['require_no_diagnostic']()
    p={'stage':'Stage201 bounded local extension beyond repaired failure','maximum_new_accepted_steps':10000,'maximum_calls':10,'maximum_steps_per_call':10000,'initial_seed':'dispatch_full_01',
       'initial_window_steps':30277,'maximum_window_steps_after_extension':40277,'production_authorized':False,'physical_changes':[],
       'inputs':{str(f):api.sha(f) for f in (r['source'].WORK,job.DESIGN,BASE/'local_closure_01/results.json',BASE/'local_closure_01/completion.json',r['RUNBASE']/'dispatch_full_01/results.json',r['RUNBASE']/'dispatch_full_01/completion.json')},
       'sources':{str(f):api.sha(f) for f in SELF.parent.glob('*.py')},'stop_on_any_failed_or_unresolved_call':True,'claim':'Local numerical robustness/cost qualification only; no full-path, release or empirical-validation claim.'}
    job.commit(DESIGN,p);print('EXTENSION_PREPARED',p['maximum_new_accepted_steps'],flush=True)


def run():
    p=api.read(DESIGN);w=api.read(r['source'].WORK);api.require(job.utc()<job.policy.utc(w['no_new_trajectory_after_utc']),'trajectory launch window')
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources']);r['require_no_diagnostic']();used,pending=r['ledger']();api.require(used==p['initial_window_steps'] and not pending,'fresh exclusive extension')
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'protocol_sha256':api.sha(DESIGN),'maximum_accepted_steps':p['maximum_new_accepted_steps'],'maximum_calls':p['maximum_calls']})
    seed=p['initial_seed'];steps=0;calls=[];failure=None;reason='call_cap'
    try:
        for index in range(1,p['maximum_calls']+1):
            if job.utc()>=job.policy.utc(w['no_new_trajectory_after_utc']):reason='work_launch_cutoff';break
            left=p['maximum_new_accepted_steps']-steps
            if left<=0:reason='bounded_target_reached';break
            name='extension_call%02d_01'%index;cap=min(left,p['maximum_steps_per_call'])
            api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
            r['prepare'](name,cap,seed);r['run'](name)
            result=r['sealed_result'](r['RUNBASE']/name/'results.json');steps+=result['steps']
            calls.append({'name':name,'steps':result['steps'],'window_steps':result['window_total_steps'],'time_s':result['time_s'],'compute_seconds':result['compute_seconds'],'transaction_seconds':result['transaction_seconds'],'numerical_audit_passed':result['numerical_audit_passed'],'rejected':result['rejected'],'results_sha256':api.sha(r['RUNBASE']/name/'results.json')})
            job.commit(OUT/('progress_%02d.json'%index),{'calls':calls,'new_extension_steps':steps,'current_seed':name,'utc':job.utc().isoformat()})
            api.require(result['numerical_audit_passed'] and result['rejected']==0 and result['steps']>0,'successful nonempty audited extension call')
            if result['status'] in ('present_at_horizon','full_window_exit'):reason='local_terminal_observation';break
            seed=name
        if steps==p['maximum_new_accepted_steps']:reason='bounded_target_reached'
    except Exception as error:failure={'error':repr(error),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure);reason='failed_or_unresolved_call'
    used,pending=r['ledger']();api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    result={'passed':failure is None and not pending and all(c['numerical_audit_passed'] and c['rejected']==0 for c in calls),'reason':reason,'calls':calls,'extension_steps':steps,'window_total_steps':used,'unresolved_reservations':pending,'failure':failure,'protocol_sha256':api.sha(DESIGN),'claim':p['claim']}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')});print('EXTENSION_TERMINAL',result['passed'],reason,steps,used,flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
