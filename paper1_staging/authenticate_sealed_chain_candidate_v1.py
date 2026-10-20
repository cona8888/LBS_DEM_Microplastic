"""Uninstalled saved-evidence candidate; no solver, dispatch or case admission.

The pinned oracle's complete inventory/raw/history/trace/restart checks are
retained. Only its three repeated mechanical audits are replaced by checks of
their already sealed independent receipts. A caller must supply a separately
bounded offline-validation clock, a trusted closed-execution receipt hash and
an explicit destination OUTSIDE the original run. No CLI runs a retained path.
The original codec is unchanged, including its prior-prefix reopening.
"""
from datetime import datetime, timezone
from pathlib import Path
from types import FunctionType
import ast
import copy
import hashlib
import importlib
import json
import shutil
import time

SELF = Path(__file__).resolve()
ROOT = SELF.parents[1]
ORACLE = SELF.with_name('evaluate_timecap_full_v1.py')
ORACLE_SHA256 = '9db2e9816986fbb74580618fc6d53731ee5a6e03612cb68a10ddd2dad27f16e3'
RECEIPT_OUTPUT_CAP = 8 * 1024**2
SEAL_ALLOWANCE = 16 * 1024
INVENTORY_INTERVAL_SECONDS = 60.


def need(value, message):
    if not value:
        raise RuntimeError('Sealed-chain CANDIDATE: ' + message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_final_pins(candidate_path, candidate_sha, closure_path, closure_sha,
                      oracle_path, oracle_sha):
    for label, path, expected in (('candidate', candidate_path, candidate_sha),
                                  ('closed execution receipt', closure_path, closure_sha),
                                  ('oracle', oracle_path, oracle_sha)):
        need(sha(path) == expected, 'fresh final ' + label + ' source/evidence pin')


def validation_bounds(start_text, end_text, original_start_text, original_end_text, now=None):
    values = [datetime.fromisoformat(x) for x in
              (start_text, end_text, original_start_text, original_end_text)]
    need(all(x.tzinfo is not None and x.utcoffset() is not None for x in values), 'aware validation and original bounds')
    start, end, original_start, original_end = values
    need(0 < (original_end - original_start).total_seconds() <= 36 * 3600,
         'same original bounded36h authority')
    need(original_start <= start < end <= original_end, 'offline bounds stay inside original absolute authority')
    now = datetime.now(timezone.utc) if now is None else now
    need(now.tzinfo is not None and now.utcoffset() is not None and start <= now < end,
         'offline validation authority has started and remains unexpired')
    return start, end


def resource_inventory(root, run, destination):
    def size(path):
        return sum(x.stat().st_size for x in path.rglob('*') if x.is_file()) if path.exists() else 0
    candidate_bytes = size(destination)
    return size(run), sum(size(root / name) for name in
                          ('paper1_runs', 'paper1_designs', 'paper1_evaluations')), candidate_bytes


class ResourceBoundary:
    """Cheap free checks per boundary; whole inventories only periodically/finally."""
    def __init__(self, plan, run, destination, *, inventory=resource_inventory,
                 free=None, monotonic=time.monotonic):
        self.run, self.destination = Path(run), Path(destination)
        self.output_cap = plan['maximum_new_output_bytes']
        self.total_cap = plan['unchanged_total_retention_bytes']
        self.free_reserve = plan['unchanged_free_reserve_bytes']
        need(plan.get('maximum_output_bytes', self.output_cap) == self.output_cap
             and plan.get('minimum_free_disk_bytes', self.free_reserve) == self.free_reserve,
             'unchanged matching plan output/free declarations')
        need(all(type(x) is int and x > 0 for x in (self.output_cap, self.total_cap, self.free_reserve)),
             'positive original resource ceilings')
        self.inventory, self.free, self.monotonic = inventory, free or (lambda: shutil.disk_usage(ROOT).free), monotonic
        self.last_scan = None
        self.snapshot = None

    def check(self, *, force=False, reserved_output=RECEIPT_OUTPUT_CAP):
        need(type(reserved_output) is int and 0 <= reserved_output <= RECEIPT_OUTPUT_CAP,
             'bounded fixed candidate receipt-output reserve')
        free = self.free()
        need(free >= self.free_reserve + reserved_output, 'original free reserve plus candidate output')
        now = self.monotonic()
        if force or self.last_scan is None or now - self.last_scan >= INVENTORY_INTERVAL_SECONDS:
            own, total, candidate_bytes = self.inventory(ROOT, self.run, self.destination)
            need(own + candidate_bytes + reserved_output <= self.output_cap,
                 'original run plus external candidate stays inside unchanged output cap')
            need(total + reserved_output <= self.total_cap, 'unchanged total Paper1 retention cap')
            need(candidate_bytes + reserved_output <= RECEIPT_OUTPUT_CAP, 'fixed candidate receipt output cap')
            self.snapshot = dict(run_bytes=own, candidate_bytes=candidate_bytes, paper1_retained_bytes=total,
                                 free_bytes=free, reserved_candidate_output_bytes=reserved_output)
            self.last_scan = now
        return self.snapshot

    def serialized_size(self, body):
        # Same ordinary JSON presentation plus a conservative seal allowance.
        size = len((json.dumps(body, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8'))
        need(size + SEAL_ALLOWANCE <= RECEIPT_OUTPUT_CAP, 'serialized receipt and seal fit fixed8MiB cap')
        return size + SEAL_ALLOWANCE


def external_destination(level, value):
    level, target = Path(level).resolve(), Path(value).resolve()
    run = level.parent.parent
    need(target != run and run not in target.parents, 'external destination, never an original run path')
    need('full_audit_01' not in target.parts and not target.exists(), 'new explicit non-oracle destination')
    need(ROOT / 'paper1_evaluations' in target.parents,
         'external candidate destination belongs to inventoried Paper1 evaluations')
    return target


def receipt_decisions(receipt, guard, policy, record, seed, case, folder,
                     reservation, plan_sha, physical_sha, previous_sha, api,
                     config, selector_sha, ctx, physical):
    """Authenticate decisions, never reconstruct forces/geometry or solve."""
    folder = Path(folder)
    count = len(record['rows'])
    cp = record['result']['checkpoint']
    output = api.digest(cp)
    before = api.digest(seed)
    summary = receipt['summary']
    role = 'core_pending_accuracy' if reservation['kind'] == 'production' else 'restart_diagnostic'
    need(receipt['passed'] is True and summary['passed'] is True
         and guard['passed'] is True and guard['guard_audit']['passed'] is True
         and policy['passed'] is True, 'all independent receipt decisions passed')
    need(record['spec'] == case['spec'] and record['design_sha256'] == physical_sha
         and record['input_checkpoint_sha256'] == before
         and receipt['transport_design_sha256'] == plan_sha
         and receipt['physical_design_sha256'] == physical_sha
         and receipt['input_checkpoint_sha256'] == before
         and receipt['previous_receipt_sha256'] == previous_sha
         and receipt['output_checkpoint_sha256'] == output
         and receipt['role'] == role, 'identical physical/raw/seed/predecessor/role associations')
    need(receipt['numerical_policy_contract_sha256'] == record['numerical_policy_contract_sha256']
         == api.sha(ctx.job.WORK)
         and receipt['original_binding'] == ctx.job.binding(physical, case),
         'original complete numerical-policy contract and physical binding')
    need(0 < count == receipt['new_saved_steps'] == guard['saved_steps']
         <= reservation['maximum_saved_steps'] == record['step_cap']
         and guard['full_checkpoint_sha256'] == output,
         'positive bounded complete checkpoint and row counts')
    initial_t = 0. if seed is None else seed['state']['t']
    initial_n = 0 if seed is None else seed['state']['steps']
    need(summary['start_s'] == initial_t and summary['stop_s'] == cp['state']['t']
         and cp['state']['steps'] == initial_n + count
         and record['result']['rejected'] == 0, 'original clock/step/zero-rejection associations')
    raw = str((folder / 'call.json.xz').resolve())
    raw_sha = sha(raw)
    need(receipt['artifacts'][raw] == guard['artifacts'][raw] == policy['raw_sha256'] == raw_sha
         and policy['original_physical_guard_sha256'] == sha(folder / 'guard_completion/results.json'),
         'receipt decisions bind identical current raw and original physical guard')
    evidence = record['onset_timecap']
    journal = evidence['journal']
    need(evidence['enabled'] == config['enabled'] and evidence['policy'] == config['policy']
         and evidence['source_sha256'] == selector_sha,
         'same frozen selector mode, policy and source')
    pending = cp['state']['pending_trial'] is not None
    need(len(journal) == count + int(pending)
         and policy['accepted_rows'] == count
         and policy['journal_entries'] == len(journal)
         and policy['pending_witnesses'] == int(pending)
         and policy['start_s'] == initial_t and policy['stop_s'] == cp['state']['t']
         and policy['trigger_count'] == sum(bool(x['trigger_grain_ids']) for x in journal)
         and policy['tightened_steps'] == sum(x['selected_dt_s'] < x['base_dt_s'] for x in journal)
         and policy['original_caps_never_increased'] is True
         and policy['independent_geometry_and_policy_replayed'] is True
         and policy['replaces_original_physics_audit'] is False
         and policy['native_solver_calls'] == policy['new_saved_steps'] == 0,
         'complete existing independent policy receipt and literal journal coverage')
    return summary, guard['guard_audit'], policy


def candidate_ast():
    """Five narrow, checked edits to the pinned oracle; no namespace mutation."""
    need(sha(ORACLE) == ORACLE_SHA256, 'unchanged complete oracle source')
    tree = ast.parse(ORACLE.read_text(encoding='utf-8'))
    fn = copy.deepcopy(next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'authenticate'))
    fn.name = '_candidate_body'
    fn.args.kwonlyargs.append(ast.arg(arg='external_destination'))
    fn.args.kw_defaults.append(None)
    counts = dict(destination=0, mechanical=0, message=0, body=0, returned=0)

    class Adapt(ast.NodeTransformer):
        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name == 'destination':
                    need(ast.unparse(node.value) == "level / 'full_audit_01'", 'exact oracle destination statement')
                    counts['destination'] += 1
                    return ast.parse('destination = _external_destination(level, external_destination)').body[0]
                if name in ('physical_check', 'guard_check', 'policy_check'):
                    expected = {'physical_check': 'ctx.baseline.kernel', 'guard_check': 's.q.guard.audit',
                                'policy_check': 'policy_auditor.audit'}[name]
                    need(isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == expected,
                         'exact oracle mechanical audit statement ' + name)
                    counts['mechanical'] += 1
                    if name != 'physical_check':
                        return None
                    return ast.parse('physical_check, guard_check, policy_check = _receipt_decisions('
                        'receipt, gate, cap_gate, rec, seed, case, folder, reservation, plan_sha, physical_sha, '
                        'previous_sha, api, shared_config, s.sha(selector.__file__), ctx, physical)').body[0]
                if name == 'body':
                    counts['body'] += 1
                    node.value = ast.Call(func=ast.Name(id='_candidate_metadata', ctx=ast.Load()),
                                          args=[node.value], keywords=[])
            return self.generic_visit(node)

        def visit_Constant(self, node):
            if node.value == 'independent post-exit physical and full numerical-policy replay':
                counts['message'] += 1
                return ast.Constant('authenticated original independent receipts; no repeated mechanical replay')
            return node

        def visit_Return(self, node):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'dict':
                counts['returned'] += 1
                for key in node.value.keywords:
                    if key.arg == 'retirement_receipt_type':
                        key.value = ast.Constant('UNPROMOTED saved-evidence sealed-chain candidate; no mechanical replay')
                    elif key.arg == 'full_audit_path':
                        key.arg = 'chain_receipt_path'
                    elif key.arg == 'full_audit_sha256':
                        key.arg = 'chain_receipt_sha256'
            return self.generic_visit(node)

    fn = Adapt().visit(fn)
    need(counts == dict(destination=1, mechanical=3, message=1, body=1, returned=1),
         'only the declared destination/audit/metadata/return adaptations')
    result = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    # The original independent mechanics must remain available in the oracle,
    # but must not be callable from this receipt-authentication candidate.
    forbidden = {'ctx.baseline.kernel', 's.q.guard.audit', 'policy_auditor.audit'}
    need(not any(isinstance(x, ast.Call) and ast.unparse(x.func) in forbidden for x in ast.walk(result)),
         'candidate exposes no repeated mechanical audit call')
    return result, counts


def authenticate_chain(level, case, plan_path, physical_path, config, destination, *,
                       validation_start_utc, validation_end_utc, expected_candidate_sha256,
                       closed_execution_receipt, closed_execution_sha256):
    """Explicit future OFFLINE validation API, not execution authority.

    Not run during preparation. Requires already closed owned processes and a
    trusted external closure hash. It cannot admit or reinterpret a failed case.
    """
    need(sha(SELF) == expected_candidate_sha256, 'caller pins this candidate source before validation')
    tree, changes = candidate_ast()
    oracle = importlib.import_module('evaluate_timecap_full_v1')
    level = Path(level).resolve()
    target = external_destination(level, destination)
    closure_path = Path(closed_execution_receipt).resolve()
    need(sha(closure_path) == closed_execution_sha256, 'trusted already closed execution receipt')
    closure = oracle.s.fields.sealed(closure_path)
    need(closure['passed'] and closure['all_exact_owned_identities_retired']
         and closure['design_sha256'] == oracle.s.sha(plan_path), 'closed exact original execution/design')
    frozen_plan = oracle.s.read(plan_path)
    need(datetime.fromisoformat(frozen_plan['end_utc']) == datetime.fromisoformat(closure['original_shared_end_utc']),
         'closed receipt and original immutable authority have identical absolute end')
    start, end = validation_bounds(validation_start_utc, validation_end_utc,
                                   frozen_plan['start_utc'], closure['original_shared_end_utc'])
    resources = ResourceBoundary(frozen_plan, level.parent.parent, target)
    resources.check(force=True)
    final_stage = [False]

    def final_pin_check():
        verify_final_pins(SELF, expected_candidate_sha256, closure_path, closed_execution_sha256,
                          ORACLE, ORACLE_SHA256)

    def boundary(plan, reserved_output=RECEIPT_OUTPUT_CAP):
        now = datetime.now(timezone.utc)
        need(start <= now < end, 'inside separately supplied offline-validation clock')
        if final_stage[0]:
            final_pin_check()
        resources.check(reserved_output=reserved_output)
        for row in closure['identity_inspections_after_hashing']:
            need(oracle.s.sha(row['path']) == row['sha256']
                 and oracle.s.identity(oracle.s.read(row['path']))['retired'], 'all exact actors remain retired')

    def metadata(body):
        final_pin_check()
        boundary(None)
        for path, digest in body['artifacts'].items():
            need(closure['artifacts'].get(path) == digest,
                 'every consumed artifact, including external oracles, has original trusted closed bytes')
        body.update(schema='paper1.sealed-chain-UNPROMOTED-candidate.v1',
            full_selector_policy_replayed=False, original_physics_and_guard_replayed=False,
            original_independent_receipts_authenticated=True, postexit_mechanical_replay=False,
            candidate_uninstalled=True, qualification_passed=False, full_path_accuracy_passed=False,
            core_result_admitted=False, publication_case_count_increment=0,
            paper1_dataset_complete=False, administrative_owner_may_remain_live=False,
            original_accuracy_qualification_passed=closure['qualification_passed'],
            original_closed_execution_sha256=closed_execution_sha256,
            candidate_source_sha256=expected_candidate_sha256, oracle_source_sha256=ORACLE_SHA256,
            source_adaptations=changes, validation_start_utc=start.isoformat(), validation_end_utc=end.isoformat())
        body['source_files'] = {**body['source_files'], str(SELF): expected_candidate_sha256,
                                str(ORACLE): ORACLE_SHA256}
        body['resource_policy'] = dict(maximum_new_output_bytes=resources.output_cap,
            unchanged_total_retention_bytes=resources.total_cap, unchanged_free_reserve_bytes=resources.free_reserve,
            candidate_receipt_output_cap_bytes=RECEIPT_OUTPUT_CAP, inventory_interval_seconds=INVENTORY_INTERVAL_SECONDS,
            free_space_checked_at_every_boundary=True)
        body['resources_before_final_write'] = resources.check(force=True)
        resources.serialized_size(body)
        final_stage[0] = True
        return body

    namespace = {**vars(oracle), '_deadline': boundary, '_external_destination': external_destination,
                 '_receipt_decisions': receipt_decisions, '_candidate_metadata': metadata}
    namespace['_context'] = FunctionType(oracle._context.__code__, namespace, oracle._context.__name__,
                                         oracle._context.__defaults__, oracle._context.__closure__)
    exec(compile(tree, str(SELF) + '::pinned_oracle_chain', 'exec'), namespace)
    boundary(None)
    result = namespace['_candidate_body'](level, case, plan_path, physical_path, config,
                                         external_destination=target)
    resources.check(force=True, reserved_output=0)
    boundary(None, reserved_output=0)
    return result


if __name__ == '__main__':
    raise SystemExit('UNINSTALLED candidate. Run only its fixture tests; retained-path validation requires explicit review.')
