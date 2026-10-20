"""New immutable campaign: one qualified metadata helper changed, no physics.

Stage203 is preserved failed/incomplete. Preparation requires its sealed full
terminal evaluation. No old checkpoint, trajectory test, or restart is used.
"""
from pathlib import Path
from types import FunctionType
import copy, os, sys, shutil

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'stage203_staging'), str(ROOT / 'stage204_staging')]
import autonomous_completion_campaign_v1 as old
import receipt_ack_single_pass_v1 as ack

api, q, pre, job = old.api, old.q, old.pre, old.job
BASE = 'receipt_repaired_campaign_20260930'
OLD_DESIGN = ROOT / 'stage203_designs/autonomous_completion_20260929/design_01.json'
OLD_EVAL = ROOT / 'stage203_evaluations/autonomous_completion_20260929/evaluation_01/results.json'
OLD_RUN = Path('D:/MATDEM_MICROPLASTIC/stage203_runs/autonomous_completion_20260929/run_01')
job.SELF = Path(__file__).resolve(); job.BASE = BASE
job.DESIGN = ROOT / 'stage205_designs' / BASE / 'design_01.json'
job.RUN = Path('D:/MATDEM_MICROPLASTIC/stage205_runs') / BASE / 'run_01'
job.OUT = ROOT / 'stage205_evaluations' / BASE
job.WORK = ROOT / 'stage205_designs' / BASE / 'authorization_01.json'
job.PREFLIGHT = job.RUN.parent / 'not_authorized'
RESOURCE = job.OUT / 'resource_schedule_01/results.json'
BRIDGE = job.OUT / 'qualification_bridge_01/results.json'
INDEPENDENT = job.OUT / 'independent_bridge_01/results.json'
REPAIR = ROOT / 'stage204_evaluations/receipt_race_20260930/independent_01/results.json'
REPAIR_QUAL = ROOT / 'stage204_evaluations/receipt_race_20260930/qualification_01/results.json'
INVENTORY = ROOT / 'stage204_evaluations/receipt_race_20260930/failed_inventory_01/results.json'
raw_execute = FunctionType(pre.raw_execute.__code__, dict(job.__dict__), 'execute_segment', pre.raw_execute.__defaults__, pre.raw_execute.__closure__)
job.execute_segment = FunctionType(pre.execute_segment.__code__, dict(pre.execute_segment.__globals__, job=job, raw_execute=raw_execute), 'execute_segment', pre.execute_segment.__defaults__, pre.execute_segment.__closure__)


def acknowledged(d, pending):
    return ack.acknowledged(api, job.policy, job.DESIGN, d, pending)
job.acknowledged = acknowledged


def sealed(path):
    return old.sealed(path)


def bindings():
    old.inherited()
    repair, qual = sealed(REPAIR), sealed(REPAIR_QUAL)
    api.require(repair['passed'] and qual['passed'] and repair['new_trajectory_steps'] == qual['new_trajectory_steps'] == 0, 'qualified zero-step metadata repair')
    api.require(repair['qualified_result_sha256'] == api.sha(REPAIR_QUAL) and repair['candidate_sha256'] == api.sha(ack.__file__), 'exact repaired helper qualification')
    api.verify_mapping(qual['sources'])
    proofs = {}
    for name in old.IDENTICAL:
        if name == 'acknowledged': continue
        a, b = getattr(job, name), getattr(pre.job, name)
        api.require(a.__code__ == b.__code__ and q.campaign.code_sha(a) == q.campaign.code_sha(b), 'same lifecycle ' + name)
        proofs[name] = q.campaign.code_sha(a)
    api.require(job.worker.__globals__ is job.__dict__ and job.worker.__globals__['acknowledged'] is acknowledged, 'real producer bound to single-pass adapter')
    api.require(acknowledged.__globals__['ack'] is ack and ack.__file__ == str(ROOT / 'stage204_staging/receipt_ack_single_pass_v1.py'), 'exact helper module')
    api.require(raw_execute.__code__ is pre.raw_execute.__code__ and job.execute_segment.__code__ is pre.execute_segment.__code__, 'unchanged integration and contact route')
    for key in ('parent', 'fast', 'prior', 'deadline', 'capture', 'observer'):
        api.require(raw_execute.__globals__[key] is pre.raw_execute.__globals__[key], 'unchanged physics dependency ' + key)
    for key in ('repair', 'candidate', 'previous'):
        api.require(job.execute_segment.__globals__[key] is pre.execute_segment.__globals__[key], 'unchanged numerical dependency ' + key)
    api.require(raw_execute.__globals__['DESIGN'] == job.DESIGN and raw_execute.__globals__['codec'] is pre.job.codec, 'new evidence identity with old codec')
    api.require(job.kernel is pre.job.kernel and job.codec is pre.job.codec and job.observer is pre.job.observer, 'original kernel codec observer')
    return dict(unchanged_function_sha256=proofs, integration_sha256=q.campaign.code_sha(raw_execute),
                contact_route_sha256=q.campaign.code_sha(job.execute_segment), adapter_sha256=q.campaign.code_sha(acknowledged),
                candidate_sha256=api.sha(ack.__file__), original_verifier_sha256=api.sha(job.policy.__file__))


def equivalence(d):
    previous = api.read(OLD_DESIGN); authority = api.read(job.WORK); resource = sealed(RESOURCE)
    allowed = old.ALLOWED | {'receipt_acknowledgement_repair'}
    changed = {k for k in set(d) | set(previous) if d.get(k) != previous.get(k)}
    api.require(changed <= allowed, 'no scientific field change')
    for key in ('cases', 'numerical_gates', 'budget', 'minimum_gap_semantics', 'worker_logical_cpus', 'auditor_logical_cpu',
                'maximum_unverified_segments_per_case', 'maximum_unverified_segments_total', 'poll_seconds', 'stop_reserve_seconds'):
        api.require(d[key] == previous[key], 'unchanged scientific/resource field ' + key)
    api.require(d['numerical_gates'] == job.policy.GATES and d['budget']['workers'] == authority['production_workers'] == 3, 'original gates and three slots')
    api.require(d['maximum_unverified_segments_per_case'] * 3 <= d['maximum_unverified_segments_total'] == authority['maximum_outstanding_records'] == 6, 'original global-six bound')
    api.require(not d['physical_changes'] and d['fresh_start_required'] and d['production_authorized'], 'same fresh original physics')
    for key in ('simulation_cutoff_utc', 'final_audit_deadline_utc', 'agent_work_end_utc'):
        api.require(d[key] == authority[key], 'authorized calendar')
    api.require(d['resource_scenario'] == resource, 'exact measured resource plan')
    api.require(all(d['sources'].get(p) == h for p, h in previous['sources'].items()) and
                all(d['inputs'].get(p) == h for p, h in previous['inputs'].items()), 'all old lineage retained')
    api.require(d['sources'][str(job.SELF)] == api.sha(job.SELF) and d['inputs'][str(job.WORK)] == api.sha(job.WORK), 'new source and authority bound')
    api.require(d['receipt_acknowledgement_repair'] == bindings(), 'exact helper and full-stack bindings')
    return sorted(changed)


def verify(d):
    api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'design seal')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    api.require(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'BLAS/OpenMP1')
    equivalence(d)
job.verify = verify


def verify_preflight(d):
    verify(d); result = old.inherited(); bridge = sealed(BRIDGE)
    api.require(bridge['passed'] and bridge['design_sha256'] == api.sha(job.DESIGN) and
                bridge['bindings'] == bindings() and bridge['new_trajectory_steps'] == 0, 'zero-step amended full-stack bridge')
    return {**result, 'refreshed_hours_with_margin': sealed(RESOURCE)['hours_with_margin']}
job.verify_preflight = verify_preflight


def old_terminal():
    terminal = api.read(OLD_RUN / 'completion.json'); result = sealed(OLD_EVAL)
    api.require(terminal['all_owned_processes_retired'] and terminal['stop_reasons'], 'old failed campaign retired')
    api.require(not result['passed'], 'old failed observation never promoted')
    witness = ROOT / 'stage203_evaluations/autonomous_completion_20260929/terminal_evaluator_01'
    exit_record = api.read(witness / 'exit.json'); witness_seal = api.read(witness / 'completion.json')
    api.require(witness_seal['exit_sha256'] == api.sha(witness / 'exit.json') and witness_seal['passed'] and
                exit_record['exit_code'] == 0 and exit_record['results_sha256'] == api.sha(OLD_EVAL), 'old frozen full evaluator witnessed exit')
    inventory = sealed(INVENTORY)
    api.require(inventory['passed'] and inventory['total_records'] == 824 and inventory['receipt_verified_steps'] == 8239328, 'failed attempt exact ledger retained')
    api.require(result['design_sha256'] == api.sha(OLD_DESIGN) and result['total_accepted_steps'] ==
                result['producer_declared_saved_steps'] == 8239328 and not result['unsealed_artifacts'],
                'all saved raw/history evidence decoded and accounted, without orphan artifacts')
    details = {item['case']: item for item in result['details']}
    for item in inventory['cases']:
        detail = details[item['case']]
        api.require(detail['records'] == item['segments'] and detail['verified_accepted_steps'] ==
                    detail['producer_declared_saved_steps'] == item['receipt_verified_steps'], 'exact full decoded case inventory')
        expected_errors = [] if item['producer_completion_present'] else ["ValueError('producer completion present')"]
        api.require(detail['errors'] == expected_errors, 'only disclosed missing producer completion; no unexplained raw/physics failure')
    auditor = api.read(OLD_RUN / 'auditor_complete.json')
    api.require(auditor['passed'] and not auditor['failures'] and len(auditor['items']) == 824 and
                all(item['passed'] for item in auditor['items']), 'all original independent raw physics receipts passed')
    api.verify_mapping(result['artifacts'])
    return result


def resource():
    old.RESOURCE = RESOURCE
    old.resource()


def resource_gate(d):
    verify_preflight(d); r = sealed(RESOURCE); now = job.utc()
    hours = (job.policy.utc(d['simulation_cutoff_utc']) - now).total_seconds() / 3600
    audit_hours = (job.policy.utc(d['final_audit_deadline_utc']) - job.policy.utc(d['simulation_cutoff_utc'])).total_seconds() / 3600
    need = r['bytes_with_margin'] + d['budget']['minimum_free_disk_bytes']; free = shutil.disk_usage(job.ROOT).free
    api.require(hours >= r['hours_with_margin'] and audit_hours >= r['required_final_audit_hours'] and free >= need and r['call_limit_passed'], 'measured time audit disk and call ceilings')
    return dict(required_hours=r['hours_with_margin'], available_hours=hours, required_audit_hours=r['required_final_audit_hours'],
                available_audit_hours=audit_hours, storage_with_reserve_bytes=need, free_D_bytes=free)


def prepare():
    old_terminal(); bindings(); r = sealed(RESOURCE)
    api.require(not job.DESIGN.exists() and not job.RUN.exists(), 'fresh immutable output')
    d = copy.deepcopy(api.read(OLD_DESIGN)); d.pop('binding')
    files = [Path(__file__), Path(ack.__file__), Path(__file__).with_name('audit_receipt_repaired_bridge_v1.py')]
    inputs = [job.WORK, OLD_DESIGN, OLD_EVAL, OLD_EVAL.parent / 'completion.json', REPAIR, REPAIR.parent / 'completion.json',
              REPAIR_QUAL, REPAIR_QUAL.parent / 'completion.json', INVENTORY, INVENTORY.parent / 'completion.json',
              RESOURCE, RESOURCE.parent / 'completion.json']
    d.update(stage='Stage205 receipt-repaired fresh original six-case campaign',
             sources={**d['sources'], **{str(p): api.sha(p) for p in files}}, inputs={**d['inputs'], **{str(p): api.sha(p) for p in inputs}},
             resource_scenario=r, receipt_acknowledgement_repair=bindings(), qualification_inheritance=old.qualification_lineage(),
             provenance_transaction_hours_with_margin=r['hours_with_margin'], provenance_bytes_with_margin=r['bytes_with_margin'],
             guard='Only acknowledgement publication handling amended. Original scientific full-stack qualification explicitly reused. No old checkpoint, restart or gate relaxation.',
             claim='Two labelled placements separately, full fresh selected/fine gates required. Failed Stage203 retained with complete terminal audit.')
    d['binding'] = api.digest(d); verify(d)
    job.commit(job.DESIGN, d)
    result = dict(passed=True, utc=job.utc().isoformat(), design_sha256=api.sha(job.DESIGN), source_sha256=api.sha(__file__),
                  changed_fields=equivalence(d), bindings=bindings(), new_trajectory_steps=0, inherited_steps_not_rerun=17000,
                  old_full_terminal_result_sha256=api.sha(OLD_EVAL), old_campaign_remains_failed=True)
    job.commit(BRIDGE, result); job.commit(BRIDGE.parent / 'completion.json', dict(passed=True, results_sha256=api.sha(BRIDGE)))
    print('PREPARED', api.sha(job.DESIGN), resource_gate(d), flush=True)


def owned(name=None):
    d = api.read(job.DESIGN); verify(d)
    core = d['auditor_logical_cpu'] if name is None else d['worker_logical_cpus'][next(i for i, c in enumerate(d['cases']) if c['id'] == name)]
    info = pre.affinity.bind(core)
    job.commit(job.RUN / ((name or 'auditor') + '.affinity.json'), {**info, 'design_sha256': api.sha(job.DESIGN), 'argv': sys.argv, 'utc': job.utc().isoformat()})


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['check-bindings']: print(bindings(), flush=True)
    elif args == ['resource']: resource()
    elif args == ['prepare']: prepare()
    elif args == ['check']: print(resource_gate(api.read(job.DESIGN)), flush=True)
    elif args == ['supervise', 'campaign']:
        old_terminal(); resource_gate(api.read(job.DESIGN))
        independent = sealed(INDEPENDENT)
        api.require(independent['passed'] and independent['design_sha256'] == api.sha(job.DESIGN), 'independent amended bridge')
        api.require(not old.active_owned(), 'no duplicate simulation or evaluator')
        job.supervise('campaign')
    elif len(args) == 3 and args[:2] == ['worker', 'campaign']: owned(args[2]); job.worker('campaign', args[2])
    elif args == ['auditor', 'campaign']: owned(); job.auditor('campaign')
    elif args == ['evaluate', 'campaign']: job.evaluate('campaign')
    else: raise ValueError('check-bindings | resource | prepare | check | supervise campaign | worker campaign CASE | auditor campaign | evaluate campaign')
