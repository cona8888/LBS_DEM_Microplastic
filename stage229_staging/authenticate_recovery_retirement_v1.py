"""Read-only final retirement receipt; no launches, signals or numerical imports.

Invoke ``prepare`` only for fake controls. Invoke ``authenticate`` only after the
frozen recovery controller and both children retire. All original failures and
accounting claims remain unchanged; a retirement pass is not a science pass.
"""
from pathlib import Path
from datetime import datetime
import ast, hashlib, math, sys
import psutil
import campaign_common_v1 as c

HERE = Path(__file__).resolve().parent
SUP = c.RUN/'supervisor_02'
LAUNCHER = c.RUN/'launcher_02'
WORK = c.RUN/'run_02'
PREP = c.OUT/'recovery_retirement_preparation_01'
DEST = c.OUT/'recovery_retirement_01'
SD = c.DESIGNS/'supervisor_design_02.json'
TD = c.DESIGNS/'transport_design_03.json'
FINAL = c.OUT/'final_disposition_02/results.json'
PYTHON = str(Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe'))
EXPECTED = {
    str(c.AUTH): '6bee3ee5737d4cd3440d6e4ca13bb03b8fc6ef0f910302aebfc14d9b59b44863',
    str(SD): 'f87db7a7034e9f0641b092da0bd3adc4d3ffea070f50d75c6186296db28f4da0',
    str(TD): 'ad7ef2ba4400f62f928f8c440e93db1169a75a0324dfba2117f04ce01ac82736',
    str(HERE/'finalize_recovery_v2.py'): 'c0b43c51bf58c9efa9ae24cd1d15acf8bd23cdfdc7920a4d05665be6948ab45d',
    str(HERE/'monitor_recovery_v3.py'): '91bbe3a0ddce9a66ab1b51a5f2feef5f4c2a3ba6a5b69c7e1ed9066e244e6cb6',
    str(c.OUT/'launch_authentication_02/results.json'): '356c66ef804d50d596efef55f3bed214a2b2ecb8026f4fe2e4a37995b1384f5b',
}
PROOFS = ('launch_authentication_02', 'initial_retirement_01',
    'failure_diagnosis_01', 'dispatch_decision_02', 'monitor_identity_repair_01',
    'monitor_identity_repair_provenance_01', 'monitor_identity_diagnosis_01',
    'monitor_identity_validation_01')


def need(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    """Bound each streaming hash chunk; no full raw reconstruction is repeated."""
    c.bound(); value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            c.bound(); chunk = stream.read(1024*1024)
            if not chunk:
                break
            value.update(chunk)
    c.bound(); return value.hexdigest()


def read(path):
    c.bound(); row = c.read(path); c.bound(); return row


def mapping(values):
    for path, wanted in values.items():
        need(sha(path) == wanted, 'Changed frozen evidence: '+str(path))


def sealed(path):
    path = Path(path); row = read(path)
    need(read(path.parent/'completion.json')['results_sha256'] == sha(path),
         'Unsealed final evidence: '+str(path))
    return row


def identity(row):
    command = row.get('command', row.get('argv'))
    need(type(row.get('pid')) is int and row['pid'] > 0
         and type(row.get('created')) in (int, float) and math.isfinite(row['created'])
         and type(command) is list and command and all(type(x) is str for x in command),
         'Complete exact birth and full-command identity required')
    if 'command' in row and 'argv' in row:
        need(row['command'] == row['argv'], 'Conflicting command and argv')
    return (row['pid'], row['created'], command)


def retired(row, factory=psutil.Process):
    """A proven different birth excludes reuse without reading its command.

    Access denial, including an unreadable birth, is never retirement evidence.
    A matching birth requires the complete recorded command to be inspected.
    """
    pid, birth, command = identity(row)
    try:
        process = factory(pid)
        actual_birth = process.create_time()
        if actual_birth != birth:
            need(type(actual_birth) in (int, float) and math.isfinite(actual_birth),
                 'Actual birth must be readable and finite')
            return dict(pid=pid, recorded_created=birth, actual_created=actual_birth,
                        retired=True, reason='proven_different_birth', command_inspected=False)
        actual_command = process.cmdline()
        need(type(actual_command) is list and all(type(x) is str for x in actual_command),
             'Complete actual command inspection required')
        need(actual_command != command, 'Exact task-owned process is still running')
        return dict(pid=pid, recorded_created=birth, actual_created=actual_birth,
                    retired=True, reason='proven_different_command', command_inspected=True,
                    actual_command=actual_command)
    except psutil.NoSuchProcess:
        return dict(pid=pid, recorded_created=birth, retired=True, reason='recorded_pid_absent')


def timestamp(value):
    result = datetime.fromisoformat(value)
    need(result.tzinfo is not None, 'Aware exact phase clock required')
    return result.timestamp()


def associated(row, command, design_kind, design_sha, authority):
    need(row.get('authorization_sha256') == authority
         and row.get(design_kind) == design_sha
         and identity(row)[2] == command, 'Exact launch authority, design and command association')


def phase(exitrow, launch, stop, must_succeed=False):
    need(exitrow.get('launch') == launch and exitrow.get('exact_owned_identity_retired') is True
         and type(exitrow.get('exit_code')) is int
         and type(exitrow.get('forced_deadline_stop')) is bool,
         'Exact phase exit association and explicit forced-stop flag')
    need(timestamp(launch['stop_utc']) == stop, 'Original phase deadline association')
    if must_succeed:
        need(exitrow['exit_code'] == 0 and exitrow['forced_deadline_stop'] is False,
             'Finalizer must have an unforced exit code zero')


def references(artifacts, full=False):
    mapping(EXPECTED)
    a = c.bound(); need(a['start_utc'] == c.START and a['end_utc'] == c.END
        and a['simulation_cutoff_utc'] == c.CUTOFF, 'Same original absolute authorization')
    sd, td = read(SD), read(TD)
    need(sd['authorization_sha256'] == td['authorization_sha256'] == sha(c.AUTH)
         and sd['end_utc'] == td['authorized_end_utc'] == c.END
         and sd['simulation_cutoff_utc'] == td['simulation_cutoff_utc'] == c.CUTOFF
         and not sd['candidate_production_authorized'] and not td['candidate_production_authorized'],
         'Original recovery sources, physics and absolute clocks')
    for path in (c.AUTH, SD, TD, HERE/'finalize_recovery_v2.py', HERE/'monitor_recovery_v3.py'):
        artifacts[str(path)] = sha(path)
    for name in PROOFS:
        path = c.OUT/name/'results.json'; row = sealed(path)
        need(row['passed'] is True and row['authorization_sha256'] == sha(c.AUTH),
             'Sealed proof has exact authority: '+name)
        for key in ('inputs', 'sources', 'artifacts'):
            if key in row:
                mapping(row[key]); artifacts.update(row[key])
        artifacts[str(path)] = sha(path)
        artifacts[str(path.parent/'completion.json')] = sha(path.parent/'completion.json')
    mapping(sd['sources']); artifacts.update(sd['sources'])
    mapping(td['source_files']); artifacts.update(td['source_files'])
    if full:
        for values in (a['sources'], a['inputs'], sd['inputs'], td['inputs'], td['physical_inputs']):
            mapping(values); artifacts.update(values)
    return a, sd, td


def authenticate():
    c.bound(); c.environment()
    need(Path(sys.executable).resolve() == Path(PYTHON).resolve(), 'Qualified Python runtime')
    need(not DEST.exists(), 'Create-only final retirement; no overwritten receipt')
    # Fail before any large evidence rehash if the controller or a child is live.
    for path in (FINAL, FINAL.parent/'completion.json', SUP/'exit.json', SUP/'baseline_exit.json',
                 SUP/'final_authentication_exit.json', FINAL.parent/'plan_update.json'):
        need(path.is_file(), 'Final retirement cannot run before closure: '+str(path))
    for path in (LAUNCHER/'launch.json', SUP/'launch.json', SUP/'baseline_worker_launch.json',
                 WORK/'launch.json', SUP/'final_authentication_worker_launch.json'):
        c.bound(); retired(read(path)); c.bound()
    prep = sealed(PREP/'results.json'); mapping(prep['artifacts']); mapping(prep['sources'])
    need(prep['passed'] and prep['authorization_sha256'] == sha(c.AUTH)
         and prep['process_actions'] == prep['live_process_inspections'] == prep['numerical_calls'] == 0,
         'Frozen zero-action retirement preparation')
    artifacts = {str(PREP/'results.json'):sha(PREP/'results.json'),
                 str(PREP/'completion.json'):sha(PREP/'completion.json')}
    a, sd, td = references(artifacts, full=True)
    authority = sha(c.AUTH); supervisor_sha = sha(SD); transport_sha = sha(TD)
    command_supervisor = [PYTHON, '-B', '-u', str(HERE/'launch_recovery_v2.py'), 'supervise']
    command_baseline = [PYTHON, '-B', '-u', str(HERE/'continue_baseline_v3.py'), 'run']
    command_final = [PYTHON, '-B', '-u', str(HERE/'finalize_recovery_v2.py')]
    launches = [LAUNCHER/'launch.json', SUP/'launch.json', SUP/'baseline_worker_launch.json',
                WORK/'launch.json', SUP/'final_authentication_worker_launch.json']
    records = [read(p) for p in launches]
    for index, row in enumerate(records):
        command = command_supervisor if index < 2 else command_baseline if index < 4 else command_final
        associated(row, command, 'transport_design_sha256' if index == 3 else 'supervisor_design_sha256',
                   transport_sha if index == 3 else supervisor_sha, authority)
    need(identity(records[0]) == identity(records[1])
         and identity(records[2]) == identity(records[3]), 'Exact launcher/controller/worker identities agree')
    need(records[0]['end_utc'] == records[1]['end_utc'] == c.END
         and records[3]['physical_design_sha256'] == td['physical_design_sha256']
         and records[3]['dispatch_decision_sha256'] == sha(c.OUT/'dispatch_decision_02/results.json')
         and records[3]['prior_shared_saved_steps'] == sd['prior_shared_saved_steps'] == 1304660,
         'Exact worker physical, dispatch and inherited-budget associations')
    retirement = []
    for path, row in zip(launches, records):
        c.bound(); retirement.append(dict(receipt=str(path), inspection=retired(row))); c.bound()
    ready = read(SUP/'handoff_ready.json'); handoff = read(LAUNCHER/'handoff_committed.json')
    need(ready['passed'] and handoff['passed'] and ready['supervisor_launch'] == records[0]
        and ready['launch_receipt_sha256'] == handoff['launch_receipt_sha256'] == sha(launches[0])
        and handoff['supervisor_ready_sha256'] == sha(SUP/'handoff_ready.json')
        and ready['authorization_sha256'] == handoff['authorization_sha256'] == authority,
        'Exact durable three-step ownership association')
    baseline_exit = read(SUP/'baseline_exit.json'); final_exit = read(SUP/'final_authentication_exit.json')
    phase(baseline_exit, records[2], timestamp(c.CUTOFF))
    phase(final_exit, records[4], timestamp(c.END)-10, must_succeed=True)
    deadline = SUP/'baseline_deadline_stop.json'
    need(deadline.exists() == baseline_exit['forced_deadline_stop'], 'Exact baseline forced-stop receipt inventory')
    if deadline.exists():
        stoprow = read(deadline)
        need(stoprow['launch'] == records[2] and timestamp(stoprow['utc']) >= timestamp(c.CUTOFF),
             'Forced baseline stop is tied to its original numerical cutoff')
    for name in ('failure.json', 'baseline_failure_cleanup.json', 'final_authentication_failure_cleanup.json',
                 'final_authentication_deadline_stop.json'):
        need(not (SUP/name).exists(), 'Unexpected controller failure/forced finalizer; preserve for separate disposition')
    for name in ('failure_cleanup.json', 'post_handoff_failure.json'):
        need(not (LAUNCHER/name).exists(), 'Unexpected launcher failure; preserve for separate disposition')
    disposition = read(SUP/'phase_disposition.json'); exitrow = read(SUP/'exit.json')
    need(disposition['phases'] == [baseline_exit] and disposition['candidate_production_authorized'] is False
         and disposition['cost_rerun'] is False and exitrow['phases'] == [baseline_exit, final_exit]
         and exitrow['reason'] == disposition['reason'] == 'recovery_baseline_retired'
         and exitrow['authorization_sha256'] == authority
         and exitrow['supervisor_design_sha256'] == supervisor_sha
         and exitrow['dependent_dispatch_stopped'] is True and exitrow['final_authentication_completed'] is True,
         'Exact normal supervisor phase/exit disposition')
    need(timestamp(exitrow['utc']) < timestamp(c.END), 'Controller exited within the original hard end')
    final = sealed(FINAL); mapping(final['artifacts']); artifacts.update(final['artifacts'])
    need(final['passed'] is True and final['final_accounting_authenticated'] is True
         and final['authorization_sha256'] == authority and final['transport_design_sha256'] == transport_sha
         and final['maximum_end_utc'] == c.END and final['candidate_production_authorized'] is False
         and final['population_shape_flow_campaign'] is False
         and final['initial_failed_attempt_preserved'] is True
         and final['all_accepted_full_checkpoint_history_ancestry_reconstructed'] is True,
         'Original sealed final accounting, ancestry and claim boundary')
    deferred = {str(SUP/'final_authentication_stdout.log'), str(SUP/'final_authentication_stderr.log')}
    need(set(final['finalizer_live_logs_preserved_unsealed']) == deferred
         and final['finalizer_retirement_receipt_required'] == str(SUP/'final_authentication_exit.json'),
         'Exactly the declared finalizer logs and retirement receipt')
    update = read(FINAL.parent/'plan_update.json')
    need(update['final_results_sha256'] == sha(FINAL), 'Finalizer plan update associates with this disposition')
    for folder in (SUP, LAUNCHER):
        for path in sorted(folder.rglob('*')):
            c.bound()
            if path.is_file():
                artifacts[str(path)] = sha(path)
    for path in (FINAL, FINAL.parent/'completion.json', FINAL.parent/'plan_update.json'):
        artifacts[str(path)] = sha(path)
    # A second identity inspection after hashing proves that logs remained closed.
    for row in records:
        c.bound(); retired(row); c.bound()
    result = dict(passed=True,utc=c.utc(),authorization_sha256=authority,
        supervisor_design_sha256=supervisor_sha,transport_design_sha256=transport_sha,
        original_end_utc=c.END,all_exact_launch_identities_retired=True,identity_inspections=retirement,
        finalizer_exit_code=final_exit['exit_code'],finalizer_forced_deadline_stop=final_exit['forced_deadline_stop'],
        supervisor_normal_exit_receipt_authenticated=True,finalizer_deferred_logs_now_authenticated=sorted(deferred),
        initial_failed_attempt_preserved=True,monitor_only_negative_and_repair_preserved=True,
        final_disposition_sha256=sha(FINAL),
        final_accounting={k:v for k,v in final.items() if k not in ('artifacts','finalizer_live_logs_preserved_unsealed')},
        campaign_success_is_not_inferred_from_accounting_pass=True,
        whole_overnight_success=final['whole_overnight_success'],cases=final['cases'],unresolved=final['unresolved'],
        process_actions=0,numerical_calls=0,new_trajectory_steps=0,automation_changes=0,
        sources={str(Path(__file__).resolve()):sha(__file__)},artifacts=artifacts)
    c.bound(); c.commit(DEST/'results.json',result)
    c.bound(); c.commit(DEST/'completion.json',dict(passed=True,results_sha256=sha(DEST/'results.json')))
    print('RECOVERY_RETIREMENT_AUTHENTICATED',sha(DEST/'results.json'))


def prepare():
    c.bound(); c.environment(); need(not PREP.exists(), 'Create-only preparation')
    cases = []
    launch = dict(pid=1234,created=1000.,command=['python.exe','-B','worker.py'])
    class Fake:
        def __init__(self,birth,command): self.birth=birth; self.command=command; self.command_reads=0
        def create_time(self):
            if isinstance(self.birth,Exception): raise self.birth
            return self.birth
        def cmdline(self):
            self.command_reads+=1
            if isinstance(self.command,Exception): raise self.command
            return self.command
    def control(name, action, reject=False):
        c.bound()
        try:
            action(); passed=not reject
        except Exception:
            passed=reject
        need(passed,'Retirement control failed: '+name); cases.append(dict(name=name,passed=True))
    different = Fake(2000.,psutil.AccessDenied(1234))
    control('different_birth_never_reads_denied_unrelated_command',lambda: retired(launch,lambda _:different))
    need(different.command_reads==0,'No unrelated command inspection after proven birth mismatch')
    control('absent_pid',lambda: retired(launch,lambda _: (_ for _ in ()).throw(psutil.NoSuchProcess(1234))))
    control('exact_process_running_rejected',lambda: retired(launch,lambda _:Fake(1000.,launch['command'])),True)
    control('matching_birth_different_full_command',lambda: retired(launch,lambda _:Fake(1000.,['different.exe'])))
    control('same_birth_denied_command_rejected',lambda: retired(launch,lambda _:Fake(1000.,psutil.AccessDenied(1234))),True)
    control('denied_birth_rejected',lambda: retired(launch,lambda _:Fake(psutil.AccessDenied(1234),[])),True)
    control('denied_factory_rejected',lambda: retired(launch,lambda _: (_ for _ in ()).throw(psutil.AccessDenied(1234))),True)
    control('conflicting_command_argv_rejected',lambda: identity(dict(launch,argv=['different.exe'])),True)
    control('missing_command_rejected',lambda: identity(dict(pid=1234,created=1000.)),True)
    control('nonfinite_birth_rejected',lambda: identity(dict(launch,created=float('nan'))),True)
    fake_launch=dict(launch,stop_utc=c.END)
    good=dict(launch=fake_launch,exact_owned_identity_retired=True,exit_code=0,forced_deadline_stop=False)
    control('exact_finalizer_phase',lambda:phase(good,fake_launch,timestamp(c.END),True))
    control('finalizer_forced_stop_rejected',lambda:phase(dict(good,forced_deadline_stop=True),fake_launch,timestamp(c.END),True),True)
    control('nonzero_finalizer_exit_rejected',lambda:phase(dict(good,exit_code=1),fake_launch,timestamp(c.END),True),True)
    control('wrong_phase_launch_rejected',lambda:phase(good,dict(fake_launch,pid=5678),timestamp(c.END),True),True)
    control('wrong_phase_deadline_rejected',lambda:phase(good,fake_launch,timestamp(c.END)-1,True),True)
    tree=ast.parse(Path(__file__).read_text(encoding='utf-8'))
    forbidden={'Popen','terminate','kill','send_signal','cpu_affinity','automation_update','create_worktree'}
    need(not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in forbidden
                 for n in ast.walk(tree)),'Read-only source has no launch or process mutations')
    cases.append(dict(name='no_launch_signal_mutation_or_automation_calls_in_source',passed=True))
    artifacts={str(path):sha(path) for path in map(Path,EXPECTED)}
    for name in PROOFS:
        path=c.OUT/name/'results.json'; row=sealed(path)
        need(row['passed'] and row['authorization_sha256']==sha(c.AUTH),'Prepared proof association')
        artifacts[str(path)]=sha(path); artifacts[str(path.parent/'completion.json')]=sha(path.parent/'completion.json')
    mapping(EXPECTED)
    c.bound(); c.commit(PREP/'results.json',dict(passed=True,utc=c.utc(),authorization_sha256=sha(c.AUTH),
        original_end_utc=c.END,numerical_calls=0,new_trajectory_steps=0,process_actions=0,
        live_process_inspections=0,number_of_controls=len(cases),cases=cases,
        no_active_bindings_changed=True,no_retirement_receipt_issued=True,
        invocation='Qualified Python -B authenticate_recovery_retirement_v1.py authenticate only after all exact identities retire and sealed final_disposition_02 exists.',
        sources={str(Path(__file__).resolve()):sha(__file__)},artifacts=artifacts))
    c.bound(); c.commit(PREP/'completion.json',dict(passed=True,results_sha256=sha(PREP/'results.json')))
    print('RETIREMENT_PREPARATION_PASSED',sha(__file__),sha(PREP/'results.json'))


if __name__=='__main__':
    need(len(sys.argv)==2 and sys.argv[1] in ('prepare','authenticate'),'Explicit preparation or final authentication required')
    prepare() if sys.argv[1]=='prepare' else authenticate()
