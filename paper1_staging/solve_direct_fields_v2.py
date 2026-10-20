"""Fresh fixed-force convergence attempt; original failure is immutable.

Per-case initial state and iteration budget are configuration, not new physics.
Low flow resumes its authenticated unqualified transient at the identical force;
high flow uses the reference population state and original parity initializer.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import FunctionType
import sys,os,json,hashlib,time,subprocess,traceback,shutil,gc
import numpy as np
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parent))
import solve_direct_fields_v1 as previous
ROOT=previous.ROOT;SELF=Path(__file__).resolve();BASE='direct_cpd6_flows_20261013_attempt02'
DESIGN=ROOT/'paper1_designs'/BASE/'design_01.json';OUT=ROOT/'paper1_runs'/BASE
PYTHON=previous.PYTHON;CONTRACT=previous.CONTRACT;CONTRACT_SHA=previous.CONTRACT_SHA
source,probe,legacy,cpu=previous.source,previous.probe,previous.legacy,previous.cpu
sha,read,write,require,commit,authenticate,seal=previous.sha,previous.read,previous.write,previous.require,previous.commit,previous.authenticate,previous.seal

def clone(fn,ns):return FunctionType(fn.__code__,ns,fn.__name__,fn.__defaults__,fn.__closure__)

def prepare():
    require(not DESIGN.exists() and not OUT.exists(),'Create-only separately frozen attempt')
    old=read(previous.DESIGN);authenticate(old['source_files']);authenticate(old['inputs'])
    retired=read(previous.OUT/'retirement_01/results.json')
    require(retired['accounting_authenticated'] and retired['all_exact_owned_identities_retired'] and retired['unknown_gpu_updates']==0 and retired['high_flow_zero_dispatch_verified'],'Closed failed attempt with no unresolved or high-flow work')
    authenticate(retired['failure_evidence']);authenticate(retired['closed_logs'])
    for identity in retired['identities']:
        launch=read(identity['path']);require(sha(identity['path'])==identity['sha256'],'Retired launch seal')
        try:
            p=psutil.Process(launch['pid']);birth=p.create_time()
            if birth==launch['created']:
                require(p.cmdline()==launch['command'],'Exact accessible old command');raise RuntimeError('Old task still live')
        except psutil.NoSuchProcess:pass
    folder=previous.OUT/'s2_f0p5_cpd6_solve';raw=read(folder/'result.json');evaluation=read(folder/'independent_evaluation_01/results.json')
    require(not evaluation['passed'] and all(v for k,v in evaluation['checks'].items() if k not in ('source_temporal_and_dynamic_gates','long_window_field','mean_match')),
        'Failure is transient stationarity/mean only; no health, physical or reconstruction failure excused')
    require(raw['steps']==2056 and raw['numerical_health']['full_sticky_code']==0,'Authenticated healthy unqualified transient')
    low_state=folder/'final_shifted_state.npz';low_case={**old['cases'][0],'source_state':dict(path=str(low_state),sha256=sha(low_state)),
        'primary_steps':2827,'parity_initializer':False,'initial_state_role':'Unqualified transient warm state; same fixed force, no transport/promotion'}
    high_case={**old['cases'][1],'source_state':old['source_state'],'primary_steps':5140,'parity_initializer':True,
        'initial_state_role':'Unscaled qualified U0 populations; one original new-force parity initialization'}
    sources={**old['source_files'],str(SELF):sha(SELF)}
    inputs={**old['inputs'],str(previous.DESIGN):sha(previous.DESIGN),str(previous.OUT/'retirement_01/results.json'):sha(previous.OUT/'retirement_01/results.json'),
        str(previous.OUT/'retirement_01/completion.json'):sha(previous.OUT/'retirement_01/completion.json'),str(folder/'result.json'):sha(folder/'result.json'),
        str(folder/'independent_evaluation_01/results.json'):sha(folder/'independent_evaluation_01/results.json'),str(low_state):sha(low_state)}
    authenticate(sources);authenticate(inputs)
    start=datetime.now(timezone.utc);end=start+timedelta(hours=2)
    d={**old,'schema':'paper1.direct-cpd6-fields.attempt02.v1','start_utc':start.isoformat(),'end_utc':end.isoformat(),
        'numerical_cutoff_utc':(end-timedelta(minutes=15)).isoformat(),'worker_cutoff_utc':(end-timedelta(minutes=8)).isoformat(),
        'source_files':sources,'inputs':inputs,'cases':[low_case,high_case],
        'controls':{**old['controls'],'primary_steps_per_case':None,'parity_initialization_steps_per_case':None,'maximum_total_gpu_updates':7984},
        'initializer':'Per-case: low flow exact saved transient at unchanged force with no repeated initializer; high flow unscaled U0 and one original parity initializer.',
        'prior_failed_attempt_preserved':True,'prior_attempt_gpu_updates':2065,'same_low_force':low_case['acceleration_lu']==old['cases'][0]['acceleration_lu'],
        'iteration_budget_rationale':'Observed257-step tail drift shrank roughly by half each interval but remained~2.3e-3; budget reserves additional decay plus four original long-window tests. High case starts farther from its own steady state. Prediction is planning only; original independent gates decide.',
        'resource_revision_only':True,'no_force_correction':True,'automatic_failed_case_extension':False}
    d.pop('binding',None);d['binding']=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    commit(DESIGN,d);seal(OUT/'preparation_01',dict(passed=True,design_sha256=sha(DESIGN),prior_failure_sha256=sha(previous.OUT/'final_disposition_01/results.json'),new_gpu_updates=0,
        original_kernel_and_probe_unchanged=True,accuracy_tolerances_unchanged=d['gates']==old['gates'],same_low_force=d['same_low_force'],utc=start.isoformat()))
    print('DIRECT_FIELDS_ATTEMPT02_PREPARED',sha(DESIGN),d['end_utc'],flush=True)

def run():
    d=verify();me=psutil.Process();me.cpu_affinity([14]);require(not (OUT/'worker_launch.json').exists(),'No duplicate continuation worker')
    commit(OUT/'worker_launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=datetime.now(timezone.utc).isoformat()))
    driver=None;updates=attempts=0;accepted=[];active=None
    try:
        legacy.install_generic_mask_oracle();driver,build=legacy.create_driver(dict(lineage=dict(cuda_source=d['cuda_source']['path'],qualified_ptx_sha256=d['qualified_ptx_sha256'])),Path('C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.9/bin'),0)
        commit(OUT/'gpu_build.json',build)
        for case in d['cases']:
            verify();active=case['id'];folder=OUT/case['id'];folder.mkdir(parents=True,exist_ok=False)
            with np.load(case['source_state']['path']) as saved,np.load(d['geometry']['path']) as geom:
                state,phase=saved['shifted_state'],saved['phase'];require(np.array_equal(phase,geom['phase']) and state.shape==(19,279,279,279) and np.isfinite(state).all(),'Exact healthy transient/geometry')
                require(all(not np.any(state[q][phase!=0]) for q in range(19)),'Original solids remain zero')
            native_case=probe.case_for(phase,case['acceleration_lu'],case['id'])
            with bounded_sessions(d,folder) as count:
                count['attempted_updates']=attempts;count['completed_updates']=updates
                if case['parity_initializer']:
                    following=probe.one_step(driver,state,phase,native_case);initial=probe.average_states(state,following);del following
                else:initial=state
                commit(folder/'initializer.json',dict(source_file_sha256=case['source_state']['sha256'],source_state_array_sha256=probe.audit.digest(state),
                    initial_state_array_sha256=probe.audit.digest(initial),parity_initializer_applied=case['parity_initializer'],no_velocity_export_scaling=True))
                del state;gc.collect();raw,_,_=probe.relax(driver,initial,phase,native_case,OUT,case['id']+'_solve',case['primary_steps'])
                del initial;gc.collect();updates=count['completed_updates'];attempts=count['attempted_updates']
            result=evaluate(d,case,OUT/(case['id']+'_solve'));verify()
            commit(folder/'gpu_accounting.json',dict(completed_updates=updates,attempted_updates=attempts,primary_updates=case['primary_steps'],
                parity_initialization_updates=int(case['parity_initializer']),discarded_diagnostic_updates=8,particle_transport_steps=0))
            require(result['passed'],'Unchanged scientific/accuracy gate failed; stop dependent field dispatch')
            accepted.append(case['id']);active=None;print('DIRECT_FIELD_ACCEPTED',case['id'],result['mean_interstitial_velocity_m_s'],flush=True)
        verify();seal(OUT/'final_disposition_01',dict(passed=True,accepted_fields=accepted,completed_gpu_updates=updates,attempted_gpu_updates=attempts,
            prior_attempt_gpu_updates=2065,particle_transport_steps=0,particle_transport_authorized=False,source_files_authenticated=True,inputs_authenticated=True,
            artifacts={str(p):sha(p) for p in OUT.rglob('*') if p.is_file() and p.suffix!='.log'},utc=datetime.now(timezone.utc).isoformat()))
    except Exception as error:
        if 'count' in locals():updates=count['completed_updates'];attempts=count['attempted_updates']
        seal(OUT/'final_disposition_01',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),accepted_fields=accepted,active_case=active,
            completed_gpu_updates=updates,attempted_gpu_updates=attempts,prior_attempt_gpu_updates=2065,unknown_update_reservation_upper_bound=max(0,attempts-updates),
            particle_transport_steps=0,dependent_dispatch_stopped=True,all_failures_preserved=True,utc=datetime.now(timezone.utc).isoformat()))
        raise
    finally:
        if driver is not None:driver.close()

ns={**vars(previous),**globals()}
verify=clone(previous.verify,ns);bounded_sessions=previous.bounded_sessions;evaluate=clone(previous.evaluate,ns);supervise=clone(previous.supervise,ns)
ns.update(globals())
if __name__=='__main__':{'prepare':prepare,'run':run,'supervise':supervise}[sys.argv[1]]()
