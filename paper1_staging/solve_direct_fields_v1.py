"""Fresh CPD6 low/high forcing solutions; unchanged qualified LBM kernel.

Warm start uses the unchanged accepted population state, followed by the
original one-time parity initializer under the new imposed force. No scaled
velocity is exported or admitted. Original steady/CPU/health tolerances hold.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from contextlib import contextmanager
import os,sys,time,json,hashlib,subprocess,traceback,shutil,gc
import numpy as np
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage130_staging'),str(ROOT/'stage113_staging')]
import cpd6_final_stationarity_v1 as source
import evaluate_parity_correction_v2 as cpu
probe=source.s129.s128.s127.base.s114.probe
legacy=probe.legacy
SELF=Path(__file__).resolve();BASE='direct_cpd6_flows_20261013'
DESIGN=ROOT/'paper1_designs'/BASE/'design_01.json';OUT=ROOT/'paper1_runs'/BASE
PYTHON=Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')
CONTRACT=ROOT/'paper1_designs/mechanism_feasibility_20261013/contract_01.json'
CONTRACT_SHA='e04f863f6297581efe42606e1c3125b4105a17b2af081a685173dc9f1d4f7166'
sha,read,write,require=source.sha,source.read,source.write,source.require

def commit(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def authenticate(mapping):
    for path,expected in mapping.items():require(sha(path)==expected,'Immutable file changed: '+str(path))

def seal(path,result):
    commit(path/'results.json',result);commit(path/'completion.json',dict(results_sha256=sha(path/'results.json'),passed=result['passed']))

def prepare():
    require(not DESIGN.exists() and not OUT.exists(),'Create-only fresh field study')
    require(sha(CONTRACT)==CONTRACT_SHA,'Human-selected twelve-case contract')
    parent=read(source.DESIGN);source.verify(parent);qualified=read(source.EVAL/'completion.json')
    require(qualified['qualified'] and qualified['stationarity_passed'] and not qualified['transport_authorized'],'Original qualified field, no particle admission')
    authenticate(qualified['artifacts'])
    imported={str(Path(m.__file__).resolve()):sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and Path(m.__file__).is_file()
        and (ROOT in Path(m.__file__).resolve().parents or legacy.STUDY_ROOT in Path(m.__file__).resolve().parents)}
    imported[str(SELF)]=sha(SELF);imported[parent['bindings']['cuda_source']['path']]=parent['bindings']['cuda_source']['sha256']
    inputs={str(CONTRACT):CONTRACT_SHA,str(source.DESIGN):sha(source.DESIGN),str(source.EVAL/'completion.json'):sha(source.EVAL/'completion.json'),
        qualified['accepted_state']['path']:qualified['accepted_state']['sha256'],qualified['accepted_field']['path']:qualified['accepted_field']['sha256'],
        parent['bindings']['geometry']['path']:parent['bindings']['geometry']['sha256']}
    authenticate(imported);authenticate(inputs)
    start=datetime.now(timezone.utc);end=start+timedelta(hours=2)
    d=dict(schema='paper1.direct-cpd6-fields.v1',start_utc=start.isoformat(),end_utc=end.isoformat(),
        numerical_cutoff_utc=(end-timedelta(minutes=15)).isoformat(),worker_cutoff_utc=(end-timedelta(minutes=8)).isoformat(),
        human_authorization='Active Paper1 goal, desktop twelve-case mechanism set, direct three-flow qualification before common-exposure/core comparisons.',
        source_files=imported,inputs=inputs,source_state=qualified['accepted_state'],source_field=qualified['accepted_field'],geometry=parent['bindings']['geometry'],
        cuda_source=parent['bindings']['cuda_source'],qualified_ptx_sha256=parent['qualified_ptx_sha256'],
        controls=dict(tau=.8,nu_lu=.1,gpu_threads=256,primary_steps_per_case=2056,parity_initialization_steps_per_case=1,discarded_gpu_diagnostic_steps_per_case=8,
            maximum_total_gpu_updates=4130,workers=1,cpu_threads=1,maximum_output_bytes=4*1024**3,minimum_free_disk_bytes=20*1024**3),
        gates={k:v for k,v in parent['gates'].items() if k!='runtime_seconds_max'},runtime_seconds_max_per_case=4800,
        cases=[dict(id='s2_f0p5_cpd6',flow_factor=.5,acceleration_lu=float(np.float32(parent['acceleration_lu']*.5)),target_mean_velocity_m_s=parent['target_mean_velocity_m_s']*.5),
               dict(id='s2_f2p0_cpd6',flow_factor=2.,acceleration_lu=float(np.float32(parent['acceleration_lu']*2.)),target_mean_velocity_m_s=parent['target_mean_velocity_m_s']*2.)],
        initializer='Unscaled accepted U0 population state; one original arithmetic average with its one new-force GPU step, initialization only; then unchanged fixed-force kernel.',
        equation_changes=[],accuracy_tolerance_changes=[],force_correction_authorized=False,automatic_failed_case_extension=False,
        particle_transport_steps=0,particle_transport_authorized=False,
        budget_note='Fresh field iterations/loading and wall limits only; no old field attempt resumed, no particle timestep/cumulative cap changes.',
        claim='Direct stationary fields conditional on original LBM geometry/boundaries; no spatial convergence, physical validation or particle result claimed.')
    d['binding']=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    commit(DESIGN,d);seal(OUT/'preparation_01',dict(passed=True,design_sha256=sha(DESIGN),source_count=len(imported),input_count=len(inputs),new_gpu_updates=0,utc=start.isoformat()))
    print('DIRECT_FIELDS_PREPARED',sha(DESIGN),d['end_utc'],flush=True)

def verify():
    d=read(DESIGN)
    require(time.time()<datetime.fromisoformat(d['end_utc']).timestamp(),'Absolute new field-study window expired')
    require(d['binding']==hashlib.sha256(json.dumps({k:v for k,v in d.items() if k!='binding'},sort_keys=True,separators=(',',':')).encode()).hexdigest(),'Frozen field design')
    authenticate(d['source_files']);authenticate(d['inputs'])
    require(shutil.disk_usage(ROOT).free>d['controls']['minimum_free_disk_bytes'],'Disk reserve')
    require(sum(p.stat().st_size for z in (OUT,DESIGN.parent) for p in z.rglob('*') if p.is_file())<d['controls']['maximum_output_bytes'],'Field output cap')
    for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):require(os.environ.get(k)=='1','One CPU numerical thread')
    return d

@contextmanager
def bounded_sessions(d,folder):
    original=legacy.stage13.CudaCandidateSession;counter=dict(completed_updates=0,attempted_updates=0,sessions=0)
    limit=datetime.fromisoformat(d['numerical_cutoff_utc']).timestamp()
    class Bounded(original):
        def __init__(self,*args,**kwargs):
            require(time.time()<limit,'No field solve after numerical cutoff')
            super().__init__(*args,**kwargs);counter['sessions']+=1;self.serial=counter['sessions'];self.completed=0
        def step(self,number):
            require(time.time()<limit and counter['attempted_updates']<d['controls']['maximum_total_gpu_updates'],'Frozen field GPU/time budget')
            counter['attempted_updates']+=1;result=super().step(number);counter['completed_updates']+=1;self.completed+=1
            if self.completed%257==0:print('FIELD_GPU_PROGRESS',folder.name,self.completed,counter['completed_updates'],flush=True)
            return result
        def close(self):
            if sys.exc_info()[0] is not None:
                try:
                    partial=self.copy_current();p=folder/f'failed_session_{self.serial:02d}'
                    p.mkdir(parents=True,exist_ok=False);np.savez_compressed(p/'partial_shifted_state.npz',shifted_state=partial)
                    commit(p/'accounting.json',dict(completed_updates=self.completed,partial_state_sha256=sha(p/'partial_shifted_state.npz'),not_qualified=True))
                except Exception as error:print('PARTIAL_STATE_PRESERVATION_ERROR',repr(error),flush=True)
            return super().close()
    legacy.stage13.CudaCandidateSession=Bounded
    try:yield counter
    finally:legacy.stage13.CudaCandidateSession=original

def evaluate(d,case,folder):
    raw=read(folder/'result.json')
    with np.load(folder/'final_shifted_state.npz') as a,np.load(folder/'final_fields.npz') as b,np.load(d['geometry']['path']) as g:
        state,phase=a['shifted_state'],a['phase'];field,density=b['velocity_xyz_lu'],b['density_lu'];dx=float(g['spacing_m'][0])
        require(np.array_equal(phase,b['phase']) and np.array_equal(phase,g['phase']),'Identical phase/geometry')
    native=probe.observe(state,phase,probe.case_for(phase,case['acceleration_lu'],'independent'))
    independent,rho,body,wall=cpu.independent_fields(state,phase,case['acceleration_lu'])
    nodes=cpu.cpu_node_residuals(state,phase,case['acceleration_lu']);fluid=phase==0
    reconstruction=float(np.linalg.norm(independent-field)/np.linalg.norm(independent));balance=float(np.linalg.norm(np.array([body,0,0])-wall)/abs(body))
    mean=float(independent[0,fluid].mean())*((.001002/998.2)/(.1*dx));error=mean/case['target_mean_velocity_m_s']-1;gates=d['gates']
    regular=[r for r in raw['rows'] if r['step']%257==0];adjacent=raw['rows'][-8:]
    checks=dict(exact_export=bool(np.array_equal(native['velocity_xyz_lu'],field) and np.array_equal(native['density_lu'],density)),
        source_temporal_and_dynamic_gates=raw['passed'] and all(raw['checks'].values()),health=raw['numerical_health']['full_sticky_code']==0,
        finite=bool(np.isfinite(state).all()),density=abs(float(rho[fluid].mean())-1)<=gates['density_drift_max'],
        mach=float(native['maximum_speed_lu'])*3**.5<=gates['mach_max'],reconstruction=reconstruction<=2e-6,balance=balance<=gates['balance_relative_max'],
        cpu_fixed_point=max(r['fixed_point_relative_l2'] for r in nodes)<=gates['cpu_node_relative_l2_max'],mean_match=abs(error)<=gates['mean_relative_error_max'],
        long_window_field=len(regular)>=4 and max(r['field_change_relative_l2'] for r in regular[-4:])<=gates['field_relative_change_max'],
        adjacent_field=max(r['field_change_relative_l2'] for r in adjacent[1:])<=gates['field_relative_change_max'],runtime=raw['runtime_seconds']<=d['runtime_seconds_max_per_case'])
    result=dict(passed=bool(all(checks.values())),checks={k:bool(v) for k,v in checks.items()},case=case,mean_interstitial_velocity_m_s=mean,
        mean_relative_error=error,reconstruction_relative_l2=reconstruction,steady_force_balance_relative=balance,cpu_spot_checks=nodes,
        native_runtime_seconds=raw['runtime_seconds'],phase_identical=True,normalization_applied=False,transport_authorized=False,spatial_convergence_established=False,
        artifacts={str(p):sha(p) for p in folder.glob('*') if p.is_file()},design_sha256=sha(DESIGN))
    seal(folder/'independent_evaluation_01',result);return result

def run():
    d=verify();me=psutil.Process();me.cpu_affinity([14]);require(not (OUT/'worker_launch.json').exists(),'No duplicate field worker')
    commit(OUT/'worker_launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=datetime.now(timezone.utc).isoformat()))
    driver=None;updates=0;attempts=0;accepted=[];active=None
    try:
        legacy.install_generic_mask_oracle();driver,build=legacy.create_driver(dict(lineage=dict(cuda_source=d['cuda_source']['path'],qualified_ptx_sha256=d['qualified_ptx_sha256'])),Path('C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.9/bin'),0)
        commit(OUT/'gpu_build.json',build)
        for case in d['cases']:
            verify();active=case['id'];folder=OUT/case['id'];folder.mkdir(parents=True,exist_ok=False)
            with np.load(d['source_state']['path']) as saved,np.load(d['geometry']['path']) as geom:
                state,phase=saved['shifted_state'],saved['phase'];require(np.array_equal(phase,geom['phase']) and np.isfinite(state).all(),'Unmodified finite geometry/state')
                require(all(not np.any(state[q][phase!=0]) for q in range(19)),'Solid populations stay zero')
            native_case=probe.case_for(phase,case['acceleration_lu'],case['id'])
            with bounded_sessions(d,folder) as count:
                count['attempted_updates']=attempts;count['completed_updates']=updates
                following=probe.one_step(driver,state,phase,native_case);initial=probe.average_states(state,following)
                commit(folder/'initializer.json',dict(source_file_sha256=d['source_state']['sha256'],source_state_array_sha256=probe.audit.digest(state),
                    next_state_array_sha256=probe.audit.digest(following),initial_state_array_sha256=probe.audit.digest(initial),one_time_only=True,velocity_export_scaled=False))
                del state,following;gc.collect()
                raw,_,_=probe.relax(driver,initial,phase,native_case,OUT,case['id']+'_solve',d['controls']['primary_steps_per_case'])
                del initial;gc.collect();updates=count['completed_updates'];attempts=count['attempted_updates']
            result=evaluate(d,case,OUT/(case['id']+'_solve'))
            commit(folder/'gpu_accounting.json',dict(completed_updates=updates,attempted_updates=attempts,primary_updates=2056,parity_initialization_updates=1,discarded_diagnostic_updates=8,particle_transport_steps=0))
            require(result['passed'],'Original field scientific/accuracy gate failed; preserve negative and stop dependent dispatch')
            accepted.append(case['id']);active=None;print('DIRECT_FIELD_ACCEPTED',case['id'],result['mean_interstitial_velocity_m_s'],flush=True)
        seal(OUT/'final_disposition_01',dict(passed=True,accepted_fields=accepted,completed_gpu_updates=updates,attempted_gpu_updates=attempts,
            particle_transport_steps=0,particle_transport_authorized=False,source_files_authenticated=True,inputs_authenticated=True,
            artifacts={str(p):sha(p) for p in OUT.rglob('*') if p.is_file() and p.suffix!='.log'},utc=datetime.now(timezone.utc).isoformat()))
    except Exception as error:
        if 'count' in locals():updates=count['completed_updates'];attempts=count['attempted_updates']
        seal(OUT/'final_disposition_01',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),accepted_fields=accepted,active_case=active,
            completed_gpu_updates=updates,attempted_gpu_updates=attempts,unknown_update_reservation_upper_bound=max(0,attempts-updates),
            particle_transport_steps=0,dependent_dispatch_stopped=True,all_failures_preserved=True,utc=datetime.now(timezone.utc).isoformat()))
        raise
    finally:
        if driver is not None:driver.close()

def supervise():
    d=verify();folder=OUT/'controller_01';folder.mkdir(parents=True,exist_ok=False);me=psutil.Process()
    commit(folder/'launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=datetime.now(timezone.utc).isoformat()))
    command=[str(PYTHON),'-B','-u',str(SELF),'run']
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        process=subprocess.Popen(command,cwd=ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        birth=psutil.Process(process.pid).create_time();require(psutil.Process(process.pid).cmdline()==command,'Exact worker launch')
        commit(folder/'worker_launch.json',dict(pid=process.pid,created=birth,command=command))
        while process.poll() is None:
            if time.time()>=datetime.fromisoformat(d['worker_cutoff_utc']).timestamp():
                actual=psutil.Process(process.pid);require(actual.create_time()==birth and actual.cmdline()==command,'Exact identity before stop')
                commit(folder/'stop_identity.json',dict(pid=process.pid,birth=birth,command=command))
                process.terminate()
                try:process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    actual=psutil.Process(process.pid);require(actual.create_time()==birth and actual.cmdline()==command,'Exact identity before final kill')
                    process.kill();process.wait(timeout=20)
                break
            time.sleep(.5)
        code=process.wait(timeout=20)
    retired=not psutil.pid_exists(process.pid) or psutil.Process(process.pid).create_time()!=birth
    require(retired,'Exact numerical worker retired')
    commit(folder/'exit.json',dict(returncode=code,retired=True,closed_logs={str(p):sha(p) for p in folder.glob('*.log')}))
    if not (OUT/'final_disposition_01/results.json').exists():
        seal(OUT/'final_disposition_01',dict(passed=False,reason='worker_ended_without_complete_field_ledger',observed_returncode=code,
            accepted_fields=[],unknown_gpu_update_reservation_upper_bound=d['controls']['maximum_total_gpu_updates'],
            particle_transport_steps=0,particle_transport_authorized=False,dependent_dispatch_stopped=True,all_existing_partial_evidence_preserved=True))
    print('DIRECT_FIELDS_WORKER_RETIRED',code,flush=True)
    if code:raise RuntimeError('Field study failed; retain negative evidence')

if __name__=='__main__':
    {'prepare':prepare,'run':run,'supervise':supervise}[sys.argv[1]]()
