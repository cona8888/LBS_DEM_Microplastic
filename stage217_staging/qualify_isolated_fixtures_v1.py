"""Zero trajectories; actual unchanged auditor in explicitly isolated path namespace."""
from pathlib import Path
from types import FunctionType, ModuleType
import copy, inspect, os, shutil, sys, traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage216_staging'))
import same_policy_stack_preflight_v1 as original
api,real=original.api,original.job
BASE='isolated_drain_fixtures_20261001'
SELF=Path(__file__).resolve()
WORK=ROOT/'stage217_designs'/BASE/'contract_01.json'
BIND=WORK.with_name('binding_01.json')
RUN=ROOT/'stage217_runs'/BASE/'fixture_01'
OUT=ROOT/'stage217_evaluations'/BASE/'qualification_01'
FAILED=real.OUT/'failed_stack_independent_02/results.json'
NAMES=('worker','auditor','supervise','evaluate','root_for','paths','audit_one','binding','stopping')

def forbidden(*args,**kwargs):raise AssertionError('zero-step fixture cannot integrate or launch a child')

def authenticate():
    b=api.read(BIND);w=api.read(WORK);r=original.sealed(FAILED)
    api.require(api.read(BIND.with_name('binding_01.completion.json'))['result_sha256']==api.sha(BIND),'exclusive fixture binding seal')
    api.verify_mapping(b['inputs']);api.verify_mapping(r['inputs'])
    api.require(api.sha(real.DESIGN)==w['stage216_design_sha256'] and not r['preflight_passed']
        and r['failure_accounting_closed'] and r['saved_steps']==r['independently_physical_passing_steps']==17000
        and r['all_owned_processes_retired'] and r['producer_classifier_never_called'],'closed failed-inclusive independent numerical evidence')
    api.require(w['maximum_new_saved_steps']==w['new_trajectory_steps']==0
        and w['prior_saved_policy_qualification_steps']==27600<=w['maximum_combined_policy_qualification_saved_steps']==50000,'zero new step contract')
    api.require(real.utc()<real.policy.utc(w['work_end_utc']) and shutil.disk_usage(ROOT).free>w['minimum_free_disk_bytes'],'work clock and C reserve')
    real.verify(api.read(real.DESIGN))
    return b

def isolated(root):
    root=Path(root).resolve()
    api.require(root in {(RUN/x/'live').resolve() for x in ('cutoff_drain','failure_drain')},'only declared new fixture roots')
    job=ModuleType('_stage217_isolated_original_lifecycle');job.__dict__.update(vars(real))
    for name,fn in list(vars(real).items()):
        if inspect.isfunction(fn) and fn.__globals__ is vars(real):
            setattr(job,name,FunctionType(fn.__code__,vars(job),fn.__name__,fn.__defaults__,fn.__closure__))
    job.PREFLIGHT=root.parent;job.RUN=RUN/'production_forbidden';job.SELF=SELF
    job.execute_segment=job.start_child=forbidden
    def verify(d):
        real.verify(d)
        for name in NAMES:
            f=getattr(job,name)
            api.require(f.__code__ is getattr(real,name).__code__ and f.__globals__ is vars(job),'exact isolated fixture lifecycle '+name)
        api.require(job.root_for('preflight')==root and job.DESIGN==real.DESIGN
            and job.kernel is real.kernel and job.codec is real.codec and job.policy is real.policy
            and job.execute_segment is forbidden and job.start_child is forbidden,'fixture paths/dependencies and executable zero-step guards')
        api.require(real.root_for('preflight')==real.PREFLIGHT/'live','real lifecycle namespace unchanged')
    job.verify=verify;verify(api.read(real.DESIGN));return job

def prepare():
    api.require(not BIND.exists() and not RUN.exists() and not OUT.exists(),'exclusive new fixture binding')
    r=original.sealed(FAILED);api.require(r['failure_accounting_closed'] and not r['preflight_passed'],'failure closure exists')
    paths=[WORK,FAILED,FAILED.parent/'completion.json',real.DESIGN,real.OUT/'preflight_01/failure.json',SELF,SELF.with_name('audit_isolated_fixtures_v1.py')]
    inputs={str(p):api.sha(p) for p in paths};inputs.update(r['inputs'])
    b={'new_trajectory_steps':0,'inputs':inputs,'claim':api.read(WORK)['claim'],'utc':real.utc().isoformat()}
    real.commit(BIND,b);real.commit(BIND.with_name('binding_01.completion.json'),{'result_sha256':api.sha(BIND)})
    authenticate();print('ISOLATED_FIXTURE_BINDING',api.sha(BIND),flush=True)

def run():
    authenticate();original.no_competing_trajectory()
    api.require(not RUN.exists() and not OUT.exists(),'single new zero-step fixture run')
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    real.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':real.utc().isoformat(),'new_trajectory_steps':0,'binding_sha256':api.sha(BIND)})
    d=api.read(real.DESIGN);findings=[];controls=[]
    try:
        with original.refs.reference.forbid_producer():
            for label,corrupt in [('cutoff_drain',False),('failure_drain',True)]:
                root=RUN/label/'live';root.mkdir(parents=True,exist_ok=False);job=isolated(root)
                # Negative executable association tests never change the real job.
                saved=job.root_for;job.root_for=lambda mode:root
                try:job.verify(d)
                except RuntimeError:controls.append(label+':changed_root_function_rejected')
                else:raise AssertionError('wrong root function accepted')
                finally:job.root_for=saved
                saved=job.audit_one;job.audit_one=FunctionType(saved.__code__,vars(real),saved.__name__)
                try:job.verify(d)
                except RuntimeError:controls.append(label+':wrong_auditor_globals_rejected')
                else:raise AssertionError('wrong auditor globals accepted')
                finally:job.audit_one=saved
                job.verify(d)
                job.commit(root/'launch.json',{'design_sha256':api.sha(real.DESIGN),'stop_utc':'2000-01-01T00:00:00Z','fixture_only':True,'new_trajectory_steps':0,'administrative_fixture_binding_sha256':api.sha(BIND)})
                job.latch(root,label)
                origins=[]
                for ci,case in enumerate(d['cases'][:2]):
                    prefix=source_prefix=None
                    for index in (1,2):
                        src=real.paths(real.root_for('preflight'),case['id'],index)
                        record,source_prefix=real.codec.read_record(src['raw'],api.sha(real.DESIGN),source_prefix)
                        record=copy.deepcopy(record)
                        if corrupt and ci==0 and index==1:record['result']['checkpoint']['state_sha256']='0'*64
                        p=job.paths(root,case['id'],index);p['raw'].parent.mkdir(exist_ok=True)
                        _,prefix=job.codec.write_record(p['raw'],record,prefix)
                        job.commit(p['ready'],{'case':case['id'],'segment':index,'design_sha256':api.sha(real.DESIGN),'raw_path':str(p['raw']),'raw_sha256':api.sha(p['raw']),'seal_sha256':api.sha(p['raw'].with_suffix('.seal.json')),'input_checkpoint_sha256':record['input_checkpoint_sha256'],'steps':len(record['rows'])})
                        origins.append({'copy':str(p['raw']),'source':str(src['raw']),'source_sha256':api.sha(src['raw']),'injected_checkpoint_hash_failure':corrupt and ci==0 and index==1})
                job.commit(root/'copy_lineage.json',{'copies':origins,'new_trajectory_steps':0})
                job.commit(root/'producers_complete.json',{'fixture_only':True,'all_producers_retired':True})
                job.auditor('preflight')
                r=api.read(root/'auditor_complete.json')
                api.require(len(r['items'])==4 and r['passed'] is (not corrupt),'all sealed records drained after stop')
                if corrupt:api.require(sum(x['passed'] for x in r['items'])==2 and len(r['failures'])==1,'failed chain retained and independent case audited')
                else:api.require(all(x['passed'] for x in r['items']),'cutoff cannot discard sealed evidence')
                findings.append({'fixture':label,'sealed_records':4,'passed_audits':sum(x['passed'] for x in r['items']),'expected_failure_preserved':corrupt,'new_trajectory_steps':0})
        occupied=RUN/'exclusive.json';real.commit(occupied,{'fixture':True})
        try:real.commit(occupied,{'wrong':True})
        except FileExistsError:controls.append('exclusive_marker_rejected')
        else:raise AssertionError('immutable marker overwritten')
        api.require(api.read(occupied)=={'fixture':True},'original marker preserved')
        absent=RUN/'pending_guard.json';real.commit(absent.with_name(absent.name+f'.pending.{os.getpid()}'),{'fixture':True})
        try:real.commit(absent,{'wrong':True})
        except FileExistsError:controls.append('orphan_pending_rejected')
        else:raise AssertionError('orphan pending ignored')
        authenticate()
        r={'passed':True,'new_trajectory_steps':0,'fixture_archives':8,'protocol_fixtures':findings,'negative_controls':controls,'real_job_namespace_unchanged':True,'stage216_remains_failed':True,'production_authorized':False,'binding_sha256':api.sha(BIND),'inputs':{str(p):api.sha(p) for p in RUN.rglob('*') if p.is_file()}}
        real.commit(OUT/'results.json',r);real.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('ISOLATED_FIXTURES_PASS',findings,flush=True)
    except Exception as e:
        real.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run; no trajectory command')
