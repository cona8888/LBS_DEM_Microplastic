"""Guarded execution of one separately approved same-FULL-state diagnostic.

Preparation does not authorize execution.  No action defaults to a worker, and
authorize requires a caller-pinned NEW direct-human approval of this proposal.
Original physical transactions, fixed selector, independent auditors and raw
codec are reused through private namespaces.  No full-path admission exists.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import FunctionType
import copy
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
sys.path.insert(0, str(ROOT / 'paper1_staging'))
import numpy as np
import psutil
import run_core_v2 as original
import onset_timecap_experiment_v1 as timecap
import contact_onset_timecap_v1 as selector
import audit_onset_timecap_v1 as policy_auditor
import prepare_support_common_state_v2 as preparation

s, api = original.s, original.s.api
DESIGNS = ROOT / 'paper1_designs/support_common_state_20261017'
OUT = ROOT / 'paper1_runs/support_common_state_20261017'
PLAN = DESIGNS / 'design_01.json'
AUTH = DESIGNS / 'authorization_01.json'
PHYSICAL = DESIGNS / 'physical_cases_01.json'
PROPOSAL = DESIGNS / 'proposal_01.json'
APPROVAL = DESIGNS / 'human_approval_01/results.json'
PREPARED = DESIGNS / 'preparation_01/results.json'
PREPARATION_EXIT = DESIGNS / 'preparation_execution_receipt_01/results.json'
DEADLINE = '2026-10-18T02:59:34.905691+00:00'
STEP_CAP, CALL_CAP = 52024, 17
PRIOR_STEPS, PRIOR_CALLS = 10184681, 2125
LOCAL_STEPS, LOCAL_CALLS = (17000, 34000), (4, 7)
CASE_STEPS, CASE_CALLS = 11300000, 2400
SHARED_STEPS, SHARED_CALLS = 5632768, 1217
PRIOR_SHARED_STEPS, PRIOR_SHARED_CALLS = 4536769, 955
TOTAL_DIAGNOSTIC_STEPS, TOTAL_DIAGNOSTIC_CALLS = 70008, 34
CONFIG = dict(enabled=True, policy=copy.deepcopy(selector.POLICY))
PYTHON, DOC = s.PYTHON, original.DOC
sha, read, commit, seal = s.sha, s.read, s.commit, s.seal


def need(value, message):
    if not value:
        raise RuntimeError('Support common-state diagnostic: ' + message)


def clone(fn, namespace):
    result = FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)
    result.__kwdefaults__ = copy.copy(fn.__kwdefaults__)
    return result


def approval_scope():
    return dict(support_common_state_diagnostic_authorized=True,
        supplemental_diagnostic_allocation_authorized=True,
        maximum_new_saved_steps=STEP_CAP, maximum_new_integration_calls=CALL_CAP,
        maximum_discarded_diagnostic_steps=TOTAL_DIAGNOSTIC_STEPS,
        maximum_diagnostic_integration_calls=TOTAL_DIAGNOSTIC_CALLS,
        existing_case_saved_step_cap=CASE_STEPS, existing_case_call_cap=CASE_CALLS,
        original_shared_saved_step_cap=SHARED_STEPS, original_shared_call_cap=SHARED_CALLS,
        maximum_window_minutes=60, original_shared_end_utc=DEADLINE)


def validate_approval(approval, proposal_sha):
    need(approval.get('passed') is True and approval.get('proposal_sha256') == proposal_sha,
         'NEW passing human approval binds this exact proposal')
    need(all(isinstance(approval.get(key), str) and approval[key].strip()
             for key in ('human_reply', 'question_reference')),
         'verbatim direct human reply and trusted question provenance are required')
    need(isinstance(approval.get('preparation_execution_receipt_sha256'), str)
         and len(approval['preparation_execution_receipt_sha256']) == 64
         and all(c in '0123456789abcdef' for c in approval['preparation_execution_receipt_sha256']),
         'trusted human approval anchors the post-exit preparation receipt')
    scope = approval.get('scope', {})
    need(all(type(scope.get(key)) is type(value) and scope[key] == value
             for key, value in approval_scope().items()),
         'independent diagnostic dispatch and exact supplemental allocations approved')
    return True


def bounds(start):
    end = min(start + timedelta(minutes=60), datetime.fromisoformat(DEADLINE))
    cutoff = min(start + timedelta(minutes=30), end - timedelta(minutes=30))
    need(start.tzinfo is not None and start < cutoff < end,
         'same absolute deadline leaves numerical work and a full30min finalization reserve')
    return cutoff, end


def activation_index(journal):
    # Includes a final pending witness, rather than truncating to accepted rows.
    return next((i for i, witness in enumerate(journal) if witness['trigger_grain_ids']), None)


def budget_guard(steps, calls, *, prior_case_saved=PRIOR_STEPS, prior_case_calls=PRIOR_CALLS,
                 prior_shared_saved=PRIOR_SHARED_STEPS, prior_shared_calls=PRIOR_SHARED_CALLS):
    need(all(type(x) is int and x >= 0 for x in (steps, calls, prior_case_saved, prior_case_calls,
                                                prior_shared_saved, prior_shared_calls))
         and steps <= STEP_CAP and calls <= CALL_CAP
         and prior_case_saved + steps <= CASE_STEPS and prior_case_calls + calls <= CASE_CALLS
         and prior_shared_saved + steps <= SHARED_STEPS and prior_shared_calls + calls <= SHARED_CALLS,
         'unchanged all-attempt shared and cumulative case budgets, including unknown reservations')
    return True


def controls():
    """Pure mocked admission/budget/clock controls; no source/seed/native reads."""
    proposal_sha = 'a' * 64
    approved = dict(passed=True, proposal_sha256=proposal_sha, human_reply='Fixture only',
                    question_reference='synthetic-control', preparation_execution_receipt_sha256='b' * 64,
                    scope=approval_scope())
    need(validate_approval(approved, proposal_sha), 'positive synthetic approval control')
    rejected = 0
    for key in ('passed', 'proposal_sha256', 'human_reply', 'question_reference',
                'preparation_execution_receipt_sha256', 'scope'):
        bad = copy.deepcopy(approved)
        bad.pop(key)
        try:
            validate_approval(bad, proposal_sha)
        except RuntimeError:
            rejected += 1
        else:
            raise AssertionError('Missing approval field admitted: ' + key)
    for key in approval_scope():
        bad = copy.deepcopy(approved)
        bad['scope'][key] = None
        try:
            validate_approval(bad, proposal_sha)
        except RuntimeError:
            rejected += 1
        else:
            raise AssertionError('Wrong independent scope admitted: ' + key)
    start = datetime.fromisoformat(DEADLINE) - timedelta(minutes=50)
    cutoff, end = bounds(start)
    need(end == datetime.fromisoformat(DEADLINE) and cutoff == end - timedelta(minutes=30),
         'original deadline clipping control')
    try:
        bounds(datetime.fromisoformat(DEADLINE) - timedelta(minutes=30))
    except RuntimeError:
        rejected += 1
    else:
        raise AssertionError('No numerical interval admitted')
    need(sum(LOCAL_STEPS) + 1024 == STEP_CAP and sum(LOCAL_CALLS) + 6 == CALL_CAP
         and PRIOR_STEPS + STEP_CAP <= CASE_STEPS and PRIOR_CALLS + CALL_CAP <= CASE_CALLS,
         'exact all-diagnostic budget arithmetic')
    need(budget_guard(STEP_CAP, CALL_CAP), 'original case AND original all-attempt shared budget control')
    for override in (dict(prior_case_saved=CASE_STEPS - STEP_CAP + 1),
                     dict(prior_case_calls=CASE_CALLS - CALL_CAP + 1),
                     dict(prior_shared_saved=SHARED_STEPS - STEP_CAP + 1),
                     dict(prior_shared_calls=SHARED_CALLS - CALL_CAP + 1)):
        try:
            budget_guard(STEP_CAP, CALL_CAP, **override)
        except RuntimeError:
            rejected += 1
        else:
            raise AssertionError('Shared/case ceiling overflow admitted')
    need(activation_index([]) is None and activation_index([dict(trigger_grain_ids=[])]) is None
         and activation_index([dict(trigger_grain_ids=[15])]) == 0
         and activation_index([dict(trigger_grain_ids=[]), dict(trigger_grain_ids=[182])]) == 1,
         'any activation, including a pending last witness, is detected without extra work')
    return dict(passed=True, mocked_rejections=rejected, zero_native_solver_calls=0,
        zero_transport_steps=0, exact_step_call_allocation=True, missing_or_wrong_approval_rejected=True,
        old_or_unpinned_approval_confers_no_authority=True, original_absolute_deadline_not_reset=True,
        private_original_transaction_and_auditor_required=True,
        both_original_all_attempt_shared_and_case_ceilings_unchanged=True,
        any_selector_activation_including_pending_stops_dependent_dispatch=True)


def resources(p):
    own = sum(x.stat().st_size for folder in (OUT, DESIGNS) if folder.exists()
              for x in folder.rglob('*') if x.is_file())
    total = sum(x.stat().st_size for name in ('paper1_runs', 'paper1_designs', 'paper1_evaluations')
                for x in (ROOT / name).rglob('*') if x.is_file())
    need(own < p['maximum_output_bytes'] and total < p['unchanged_total_retention_bytes']
         and shutil.disk_usage(ROOT).free > p['minimum_free_disk_bytes'],
         'unchanged output, total retention and free-disk limits')
    return dict(own_retained_bytes=own, total_retained_bytes=total,
                free_bytes=shutil.disk_usage(ROOT).free)


def authority(numerical=False):
    s.environment()
    p = read(PLAN)
    now = datetime.now(timezone.utc)
    need(datetime.fromisoformat(p['start_utc']) <= now < datetime.fromisoformat(p['end_utc'])
         <= datetime.fromisoformat(DEADLINE), 'live separately approved SAME absolute authority')
    if numerical:
        need(now < datetime.fromisoformat(p['simulation_cutoff_utc']), 'strict numerical cutoff')
    need(p['binding'] == api.digest({k: v for k, v in p.items() if k != 'binding'})
         and p['authorization_sha256'] == sha(AUTH) and p['physical_design_sha256'] == sha(PHYSICAL)
         and p['proposal_sha256'] == sha(PROPOSAL) and p['human_approval_sha256'] == sha(APPROVAL),
         'frozen separately approved authority, proposal, physical design and human receipt')
    approval = s.fields.sealed(APPROVAL)
    validate_approval(approval, sha(PROPOSAL))
    need(p['maximum_saved_steps'] == STEP_CAP and p['maximum_new_integration_calls'] == CALL_CAP
         and p['maximum_discarded_diagnostic_steps'] == TOTAL_DIAGNOSTIC_STEPS
         and p['maximum_diagnostic_integration_calls'] == TOTAL_DIAGNOSTIC_CALLS
         and p['maximum_cumulative_physical_steps_per_case'] == CASE_STEPS
         and p['maximum_cumulative_calls_per_case'] == CASE_CALLS
         and p['original_shared_saved_step_cap'] == SHARED_STEPS
         and p['original_shared_call_cap'] == SHARED_CALLS
         and p['prior_shared_saved_steps'] == PRIOR_SHARED_STEPS and p['prior_shared_calls'] == PRIOR_SHARED_CALLS
         and p['workers'] == p['threads'] == p['maximum_unverified_records'] == 1
         and p['step_cap_per_call'] == 5000 and p['logical_cpu'] == 14
         and p['accuracy_promotion_authorized'] is False and p['successor_cases_authorized'] is False,
         'unchanged approved diagnostic, case, process and gate ceilings')
    api.verify_mapping(p['source_files'])
    api.verify_mapping(p['physical_inputs'])
    resources(p)
    return p


def bound():
    return authority(True)


def verify_inputs(p):
    current = authority(True)
    need(current == p or (p['binding'] == current['binding']), 'same immutable numerical authority')


def authorize(expected_approval_sha256):
    """Call ONLY after a real direct human reply; this function never creates it."""
    s.environment()
    need(isinstance(expected_approval_sha256, str) and len(expected_approval_sha256) == 64
         and all(c in '0123456789abcdef' for c in expected_approval_sha256),
         'caller must pin the exact NEW trusted human-approval receipt SHA')
    need(not PLAN.exists() and not AUTH.exists() and not OUT.exists(), 'create-only new independent window')
    need(sha(APPROVAL) == expected_approval_sha256, 'trusted root-supplied approval hash')
    human = s.fields.sealed(APPROVAL)
    validate_approval(human, sha(PROPOSAL))
    proposal, prepared = read(PROPOSAL), s.fields.sealed(PREPARED)
    preparation_exit = s.fields.sealed(PREPARATION_EXIT)
    preparation_launch = read(preparation.PREPARATION_LAUNCH)
    need(human['preparation_execution_receipt_sha256'] == sha(PREPARATION_EXIT)
         and preparation_exit['passed'] is True and type(preparation_exit['actual_returncode']) is int
         and preparation_exit['actual_returncode'] == 0
         and preparation_exit['exact_launch_retired'] is True
         and preparation_exit['preparation_launch_sha256'] == sha(preparation.PREPARATION_LAUNCH)
         and preparation_exit['preparation_source_sha256'] == sha(preparation.__file__)
             == preparation_launch['preparation_source_sha256']
         and preparation_exit['runner_source_sha256'] == sha(SELF) == preparation_launch['runner_source_sha256']
         and preparation_exit['original_shared_end_utc'] == preparation_launch['original_shared_end_utc'] == DEADLINE
         and inspect(preparation_launch)['retired'], 'authenticated exact preparation exit and frozen runner/source')
    need(prepared['passed'] and prepared['dispatch_authorized'] is False
         and prepared['proposal_sha256'] == sha(PROPOSAL)
         and prepared['physical_design_sha256'] == sha(PHYSICAL), 'reviewable complete preparation')
    need(proposal['dispatch_authorized'] is False
         and proposal['status'] == 'REQUIRES_SEPARATE_HUMAN_APPROVAL_AFTER_SCIENTIFIC_STOP'
         and proposal['original_shared_end_utc'] == DEADLINE
         and proposal['physics_changes'] == proposal['accuracy_gate_changes']
             == proposal['contact_route_changes'] == proposal['selector_policy_changes'] == [],
         'closed failed qualification is not reopened or physically changed')
    for value in (proposal, prepared):
        api.verify_mapping(value['source_files'])
        api.verify_mapping(value['physical_inputs'])
    need(proposal['source_files'].get(str(SELF)) == sha(SELF)
         and proposal['budget']['maximum_additional_saved_steps'] == STEP_CAP
         and proposal['budget']['maximum_additional_calls'] == CALL_CAP
         and proposal['budget']['prior_conservative_case_saved_steps'] == PRIOR_STEPS
         and proposal['budget']['prior_conservative_case_calls'] == PRIOR_CALLS
         and proposal['budget']['original_shared_saved_step_cap'] == SHARED_STEPS
         and proposal['budget']['original_shared_call_cap'] == SHARED_CALLS
         and proposal['budget']['prior_shared_saved_steps'] == PRIOR_SHARED_STEPS
         and proposal['budget']['prior_shared_calls'] == PRIOR_SHARED_CALLS
         and proposal['budget']['maximum_shared_saved_steps_after'] == PRIOR_SHARED_STEPS + STEP_CAP
         and proposal['budget']['maximum_shared_calls_after'] == PRIOR_SHARED_CALLS + CALL_CAP
         and proposal['diagnostic_suballocation']['already_used_diagnostic_steps'] == 17984
         and proposal['diagnostic_suballocation']['already_used_diagnostic_calls'] == 17,
         'reviewed runnable source and complete prior conservative charges')
    start = datetime.now(timezone.utc)
    cutoff, end = bounds(start)
    a = dict(start_utc=start.isoformat(), end_utc=end.isoformat(), simulation_cutoff_utc=cutoff.isoformat(),
        worker_cutoff_utc=cutoff.isoformat(), maximum_saved_steps=STEP_CAP,
        maximum_new_integration_calls=CALL_CAP, maximum_discarded_diagnostic_steps=TOTAL_DIAGNOSTIC_STEPS,
        maximum_diagnostic_integration_calls=TOTAL_DIAGNOSTIC_CALLS,
        maximum_cumulative_physical_steps_per_case=CASE_STEPS, maximum_cumulative_calls_per_case=CASE_CALLS,
        original_shared_saved_step_cap=SHARED_STEPS, original_shared_call_cap=SHARED_CALLS,
        prior_shared_saved_steps=PRIOR_SHARED_STEPS, prior_shared_calls=PRIOR_SHARED_CALLS,
        workers=1, threads=1, maximum_unverified_records=1, logical_cpu=14, step_cap_per_call=5000,
        native_seconds_per_record=45, minimum_free_disk_bytes=20 * 1024**3,
        maximum_output_bytes=256 * 1024**2, unchanged_total_retention_bytes=20 * 1024**3,
        human_approval_sha256=expected_approval_sha256, accuracy_promotion_authorized=False,
        successor_cases_authorized=False, diagnostic_only=True, original_shared_end_utc=DEADLINE)
    resources(a)
    sources = {**proposal['source_files'], str(SELF): sha(SELF),
               str(Path(timecap.__file__).resolve()): sha(timecap.__file__)}
    inputs = {**proposal['physical_inputs'], str(PROPOSAL): sha(PROPOSAL), str(APPROVAL): sha(APPROVAL),
              str(APPROVAL.with_name('completion.json')): sha(APPROVAL.with_name('completion.json')),
              str(PREPARATION_EXIT): sha(PREPARATION_EXIT),
              str(PREPARATION_EXIT.with_name('completion.json')): sha(PREPARATION_EXIT.with_name('completion.json')),
              str(PREPARED): sha(PREPARED), str(PREPARED.with_name('completion.json')): sha(PREPARED.with_name('completion.json'))}
    api.verify_mapping(sources)
    api.verify_mapping(inputs)
    commit(AUTH, a)
    p = {**a, 'authorization_sha256': sha(AUTH), 'physical_design_sha256': sha(PHYSICAL),
         'proposal_sha256': sha(PROPOSAL), 'source_files': sources, 'physical_inputs': inputs,
         'logical_core_id': proposal['logical_core_id'], 'numerical_policy_contract_sha256': sha(s.q.job.WORK)}
    p['binding'] = api.digest(p)
    commit(PLAN, p)
    seal(OUT / 'authorization_01', dict(passed=True, design_sha256=sha(PLAN),
        human_approval_sha256=expected_approval_sha256, new_transport_steps=0, new_native_solver_calls=0,
        original_shared_end_utc=DEADLINE, utc=s.utc()))
    print(json.dumps(dict(authorized=True, design_sha256=sha(PLAN), numerical_cutoff_utc=cutoff.isoformat(),
                          end_utc=end.isoformat())), flush=True)


def context(numerical=True):
    namespace = {**vars(original), **vars(timecap), **globals(), 'OUT': OUT,
                 'PLAN': PLAN, 'AUTH': AUTH, 'PHYSICAL': PHYSICAL, 'CONFIG': CONFIG,
                 'bound': bound if numerical else lambda: authority(False),
                 'verify_inputs': verify_inputs if numerical else lambda p: authority(False)}
    namespace['make_context'] = clone(original.make_context, namespace)
    namespace['physical_transaction'] = clone(original.transaction, namespace)
    namespace['transaction'] = clone(timecap.transaction, namespace)
    need(namespace['physical_transaction'].__code__ is original.transaction.__code__
         and namespace['transaction'].__code__ is timecap.transaction.__code__,
         'unchanged original physics and fixed-selector transaction code objects')
    return namespace['make_context'](), namespace['transaction']


def ledger():
    reservations = sorted((OUT / 'reservations').glob('*.json'))
    need([x.stem for x in reservations] == [f'{i:03d}' for i in range(1, len(reservations) + 1)],
         'complete contiguous conservative call reservations')
    accepted = known = unknown = 0
    labels, rows, admission_failures = [], [], []
    for path in reservations:
        row = read(path)
        need(row['index'] == len(rows) + 1 and row['kind'] == 'discarded_diagnostic'
             and 0 < row['maximum_saved_steps'] <= 5000, 'bounded diagnostic reservation')
        label = row['label']
        admission = OUT / 'admissions' / path.stem / 'results.json'
        admitted = None
        if admission.exists() or admission.with_name('completion.json').exists():
            try:
                need(admission.is_file() and admission.with_name('completion.json').is_file(),
                     'both admission document and completion seal exist')
                admitted = s.fields.sealed(admission)
                need(admitted['passed'] and admitted['label'] == label
                     and admitted['reservation_sha256'] == sha(path)
                     and 0 < admitted['saved_steps'] <= row['maximum_saved_steps'], 'sealed exact record admission')
                folder = OUT / 'records' / label
                guard_path = folder / 'guard_completion/results.json'
                policy_path = folder / 'timecap_guard/results.json'
                guard = s.fields.sealed(guard_path)
                policy = s.fields.sealed(policy_path)
                need(guard['passed'] and policy['passed']
                     and admitted['raw_sha256'] == sha(folder / 'call.json.xz') == policy['raw_sha256']
                     and admitted['physical_guard_sha256'] == sha(guard_path) == policy['original_physical_guard_sha256']
                     and admitted['timecap_guard_sha256'] == sha(policy_path)
                     and admitted['full_checkpoint_sha256'] == guard['full_checkpoint_sha256']
                     and admitted['saved_steps'] == guard['saved_steps'],
                     'every earlier admitted raw/guard remains exact before successor dispatch')
                api.verify_mapping(guard['artifacts'])
            except Exception as exc:
                admission_failures.append(dict(label=label, admission_path=str(admission), error=repr(exc)))
                admitted = None
        if admitted is not None:
            accepted += admitted['saved_steps']
            labels.append(label)
        else:
            accounting = OUT / 'records' / label / 'accounting.json'
            try:
                account = read(accounting) if accounting.is_file() else {}
                raw = OUT / 'records' / label / 'call.json.xz'
                qualified = (account.get('saved_steps_known') is True and type(account.get('saved_steps')) is int
                    and 0 <= account['saved_steps'] <= row['maximum_saved_steps']
                    and raw.is_file() and account.get('raw_sha256') == sha(raw))
            except Exception:
                qualified = False
            if qualified:
                known += account['saved_steps']
            else:
                unknown += row['maximum_saved_steps']
        rows.append(row)
    need(len(set(x['label'] for x in rows)) == len(rows)
         and {x.name for x in (OUT / 'records').glob('*') if x.is_dir()} <= {x['label'] for x in rows},
         'no unreserved record or duplicated label')
    budget_guard(accepted + known + unknown, len(rows))
    return dict(accepted_diagnostic_steps=accepted, known_unaccepted_saved_steps=known,
        unknown_reserved_steps_upper_bound=unknown, conservative_call_charges=len(rows),
        labels=labels, reservations=rows, cumulative_saved_steps=PRIOR_STEPS + accepted + known + unknown,
        cumulative_conservative_calls=PRIOR_CALLS + len(rows),
        shared_saved_steps=PRIOR_SHARED_STEPS + accepted + known + unknown,
        shared_conservative_calls=PRIOR_SHARED_CALLS + len(rows), admission_failures=admission_failures,
        ledger_authenticated=True)


def failed_ledger(error):
    """Failure-only uncertainty receipt. Never used for admission or dispatch."""
    paths = sorted((OUT / 'reservations').glob('*.json'))
    caps, failures = 0, []
    for path in paths:
        try:
            row = read(path)
            cap = row['maximum_saved_steps']
            need(type(cap) is int and 0 < cap <= 5000, 'readable bounded original reservation cap')
            caps += cap
        except Exception as exc:
            failures.append(dict(path=str(path), error=repr(exc)))
    readable = not failures
    demonstrable = (readable and caps <= STEP_CAP and len(paths) <= CALL_CAP
        and PRIOR_STEPS + caps <= CASE_STEPS and PRIOR_CALLS + len(paths) <= CASE_CALLS
        and PRIOR_SHARED_STEPS + caps <= SHARED_STEPS and PRIOR_SHARED_CALLS + len(paths) <= SHARED_CALLS)
    return dict(ledger_authenticated=False, original_ledger_error=repr(error), accepted_diagnostic_steps=0,
        accepted_work_asserted=False, known_unaccepted_saved_steps=None,
        unknown_reserved_steps_upper_bound=caps if readable else None,
        readable_registered_reservation_cap_sum=caps, conservative_call_charges=len(paths),
        unreadable_reservations=failures, unknown_or_unverifiable_work=True,
        authorized_envelope_demonstrable=demonstrable, authorized_additional_saved_step_ceiling=STEP_CAP,
        authorized_additional_call_ceiling=CALL_CAP, authorized_case_saved_step_ceiling=CASE_STEPS,
        authorized_case_call_ceiling=CASE_CALLS, authorized_shared_saved_step_ceiling=SHARED_STEPS,
        authorized_shared_call_ceiling=SHARED_CALLS, labels=[], reservations=[], admission_failures=[],
        fallback_cannot_authorize_dispatch_or_evaluation=True)


def control_hash_snapshot():
    result = {}
    for path in (PLAN, AUTH, PHYSICAL, SELF, APPROVAL):
        try:
            result[str(path)] = dict(sha256=sha(path))
        except Exception as exc:
            result[str(path)] = dict(error=repr(exc))
    return result


def retirement_snapshot():
    rows = []
    for name in ('controller_01', 'evaluator_01'):
        path = OUT / name / 'exit.json'
        if not path.exists():
            if (OUT / name).exists():
                rows.append(dict(role=name, retirement_verified=False, unresolved_identity=True,
                                 error='No complete child exit record available'))
            continue
        try:
            exit_record = read(path)
            launch = exit_record.get('launch')
            state = inspect(launch) if launch is not None else exit_record['identity']
            rows.append(dict(role=name, path=str(path), sha256=sha(path), inspection=state,
                exact_identity_available=launch is not None,
                retirement_verified=launch is not None and state['retired'] is True,
                unresolved_identity=launch is None or state['retired'] is not True,
                actual_returncode=exit_record.get('returncode'), live_logs_unsealed=exit_record.get('live_logs_unsealed', True)))
        except Exception as exc:
            rows.append(dict(role=name, path=str(path), retirement_verified=False,
                             unresolved_identity=True, error=repr(exc)))
    return rows


def invoke(ctx, transaction, p, physical, case, branch, label, cap, before, prefix, previous):
    authority(True)
    need(time.time() + 90 < datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp(),
         'native45s plus complete audit/retirement reserve before numerical cutoff')
    current = ledger()
    need(len(current['labels']) == current['conservative_call_charges']
         and not current['admission_failures']
         and current['accepted_diagnostic_steps'] + cap <= STEP_CAP
         and current['conservative_call_charges'] < CALL_CAP, 'one unverified record and bounded next reservation')
    budget_guard(current['accepted_diagnostic_steps'] + cap, current['conservative_call_charges'] + 1)
    index = current['conservative_call_charges'] + 1
    reservation = dict(index=index, branch=branch, label=label, kind='discarded_diagnostic',
        maximum_saved_steps=cap, input_checkpoint_sha256=api.digest(before), previous_result_sha256=previous,
        design_sha256=sha(PLAN), utc=s.utc())
    reserve_path = OUT / 'reservations' / f'{index:03d}.json'
    commit(reserve_path, reservation)
    record, updated, row = transaction(ctx, p, physical, case, label, cap, before, prefix, previous)
    folder = OUT / 'records' / label
    restored, state = ctx.job.codec.read_record(folder / 'call.json.xz', sha(PHYSICAL), prefix)
    need(api.digest(restored) == api.digest(record) and state.reference() == updated.reference(),
         'lossless original full raw/history reconstruction before next dispatch')
    count = len(record['rows'])
    need(0 < count <= cap and record['result']['rejected'] == 0, 'bounded original zero-rejection increment')
    gate = s.fields.sealed(folder / 'guard_completion/results.json')
    extra = s.fields.sealed(folder / 'timecap_guard/results.json')
    api.verify_mapping(gate['artifacts'])
    need(gate['passed'] and extra['passed'] and gate['full_checkpoint_sha256'] == api.digest(record['result']['checkpoint'])
         and extra['raw_sha256'] == sha(folder / 'call.json.xz')
         and extra['original_physical_guard_sha256'] == sha(folder / 'guard_completion/results.json'),
         'unchanged independent physical and selector gates bind this raw/full checkpoint')
    seal(OUT / 'admissions' / f'{index:03d}', dict(passed=True, label=label, branch=branch,
        saved_steps=count, reservation_sha256=sha(reserve_path), full_checkpoint_sha256=api.digest(record['result']['checkpoint']),
        raw_sha256=sha(folder / 'call.json.xz'), physical_guard_sha256=sha(folder / 'guard_completion/results.json'),
        timecap_guard_sha256=sha(folder / 'timecap_guard/results.json'), utc=s.utc()))
    print('SUPPORT_DIAGNOSTIC_ACCEPTED', index, label, count, record['result']['checkpoint']['state']['t'], flush=True)
    triggered = activation_index(record['onset_timecap']['journal'])
    if triggered is not None:
        # This fixed support experiment has no extra active-restart allocation.
        # Keep and charge the completed authenticated record before stopping.
        stopped = OUT / 'activation_stop_01'
        DOC.store(stopped / 'checkpoint.json', record['result']['checkpoint'], sha(PHYSICAL))
        commit(stopped / 'prefix.json', updated.reference())
        seal(stopped, dict(passed=False, expected_inactive_support_failed=True, label=label,
            first_trigger_index=triggered, pending_witness=triggered >= count,
            raw_sha256=sha(folder / 'call.json.xz'), original_physical_and_selector_gates_passed=True,
            completed_output_preserved=True, completed_saved_steps_charged=count,
            successor_dispatch_stopped=True, extra_active_restart_authorized=False,
            full_path_accuracy_passed=False, core_result_admitted=False, utc=s.utc()))
        raise RuntimeError('Unexpected fixed-selector activation (including pending witness); authenticated output retained, no successor dispatch')
    return record, updated, row


def run():
    p = authority(True)
    expected_design_sha = sha(PLAN)
    registration_deadline = min(time.time() + 5, datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp())
    while not (OUT / 'controller_01/worker_launch.json').exists() and time.time() < registration_deadline:
        time.sleep(.02)
    expected = read(OUT / 'controller_01/worker_launch.json')
    me = psutil.Process()
    need(expected['pid'] == me.pid and expected['created'] == me.create_time()
         and expected['command'] == me.cmdline(), 'only exact supervisor-owned numerical worker')
    me.cpu_affinity([14])
    commit(OUT / 'worker_launch.json', {**expected, 'utc': s.utc()})
    ctx, transaction = context()
    physical = read(PHYSICAL)
    branches, error, latest, finalization_failures, worker_passed = [], None, {}, [], False
    try:
        s.q.reference.JOB.parent.b.old.parent.configure()
        s.q.kernel.warm()
        s.q.kernel.reset()
        for index, case in enumerate(physical['cases']):
            initial, _ = preparation.seed_for(index)
            serial, _, _ = invoke(ctx, transaction, p, physical, case, index, f'branch{index}_serial',
                                  256, copy.deepcopy(initial), None, None)
            left, left_prefix, _ = invoke(ctx, transaction, p, physical, case, index, f'branch{index}_split_a',
                                         128, copy.deepcopy(initial), None, None)
            right, _, _ = invoke(ctx, transaction, p, physical, case, index, f'branch{index}_split_b',
                                 128, left['result']['checkpoint'], left_prefix,
                                 sha(OUT / 'records' / f'branch{index}_split_a/results.json'))
            need(len(serial['rows']) == 256 and len(left['rows']) == len(right['rows']) == 128
                 and api.digest(serial['rows']) == api.digest(left['rows'] + right['rows'])
                 and api.digest(serial['result']['checkpoint']) == api.digest(right['result']['checkpoint']),
                 'exact fresh late-seed256 versus128+128 rows and FULL checkpoint/history')
            seal(OUT / f'restart_branch{index}', dict(passed=True, branch=index,
                labels=dict(serial=f'branch{index}_serial', split_a=f'branch{index}_split_a', split_b=f'branch{index}_split_b'),
                discarded_diagnostic_steps=512, exact_rows=True, exact_full_checkpoint_history=True,
                original_seed_full_checkpoint_sha256=api.digest(initial), utc=s.utc()))
            del serial, left, right, left_prefix
            before, prefix, previous, labels, steps = copy.deepcopy(initial), None, None, [], 0
            for number in range(1, LOCAL_CALLS[index] + 1):
                cap = min(5000, LOCAL_STEPS[index] - steps)
                need(cap > 0, 'positive prospective branch remainder')
                label = f'branch{index}_local_{number:05d}'
                record, prefix, _ = invoke(ctx, transaction, p, physical, case, index, label, cap, before, prefix, previous)
                steps += len(record['rows'])
                before = record['result']['checkpoint']
                labels.append(label)
                previous = sha(OUT / 'records' / label / 'results.json')
                latest[index] = (before, prefix)
                if record['result']['status'] in ('present_at_horizon', 'full_window_exit'):
                    break
            complete = record['result']['status'] in ('present_at_horizon', 'full_window_exit')
            need(complete, 'bounded local branch reached its declared terminal observation')
            folder = OUT / f'recoverable_branch{index}'
            DOC.store(folder / 'checkpoint.json', before, sha(PHYSICAL))
            commit(folder / 'prefix.json', prefix.reference())
            branches.append(dict(branch=index, labels=labels, saved_steps=steps,
                terminal_status=record['result']['status'], terminal_time_s=before['state']['t'],
                full_checkpoint_sha256=api.digest(before), reset_from_original_common_seed=True))
    except Exception as exc:
        error = dict(message=repr(exc), traceback=traceback.format_exc())
        print(json.dumps(error), flush=True)
    finally:
        for index, (checkpoint, prefix) in latest.items():
            folder = OUT / f'recoverable_branch{index}'
            try:
                if not folder.exists():
                    DOC.store(folder / 'checkpoint.json', checkpoint, p['physical_design_sha256'])
                    commit(folder / 'prefix.json', prefix.reference())
            except Exception as exc:
                finalization_failures.append(dict(kind='last_checkpoint_materialization', error=repr(exc)))
        try:
            authority(False)
        except Exception as exc:
            finalization_failures.append(dict(kind='final_source_input_resource_gate', error=repr(exc)))
        try:
            counts = ledger()
        except Exception as exc:
            counts = failed_ledger(exc)
            finalization_failures.append(dict(kind='ledger_authentication', error=repr(exc)))
        need(datetime.now(timezone.utc) < datetime.fromisoformat(p['end_utc'])
             <= datetime.fromisoformat(DEADLINE), 'worker finalization remains within held original deadline')
        worker_passed = (error is None and not finalization_failures and len(branches) == 2
            and counts['ledger_authenticated'] and not counts['admission_failures']
            and counts['known_unaccepted_saved_steps'] == counts['unknown_reserved_steps_upper_bound'] == 0)
        # Raw chains remain authoritative even if cutoff interrupts checkpoint materialization.
        seal(OUT / 'worker_disposition_01', dict(passed=worker_passed,
            error=error, finalization_failures=finalization_failures,
            native_complete=worker_passed and len(branches) == 2, branches=branches, ledger=counts,
            accepted_physical_steps=0, all_saved_steps_discarded_diagnostics=True,
            full_path_accuracy_passed=False, core_result_admitted=False, design_sha256=expected_design_sha,
            expected_source_files=p['source_files'], observed_control_files=control_hash_snapshot(), utc=s.utc()))
    if not worker_passed:
        raise SystemExit(2)


def inspect(launch):
    return s.identity(launch)


def stop_exact(process, launch):
    status = inspect(launch)
    if not status['retired']:
        # inspect checked BOTH exact birth and the entire accessible command.
        process.terminate()
        process.wait(timeout=5)
    need(inspect(launch)['retired'], 'exact owned process retired after stop')


def recapture_owned_launch(process, command, cutoff):
    """Fresh BOTH-identity capture, only while the original handle is live.

    A PID alone never establishes ownership.  Matching the full command AND a
    readable birth while the original Popen handle remains alive excludes PID
    recycling.  Failure returns explicit uncertainty rather than retirement.
    """
    errors = []
    end = min(time.time() + 5, cutoff)
    for attempt in range(3):
        if process.poll() is not None:
            return None, errors
        try:
            observed = psutil.Process(process.pid)
            birth = observed.create_time()
            observed_command = observed.cmdline()
            need(process.poll() is None and observed_command == command,
                 'original live process handle and exact full command during birth recapture')
            return dict(pid=process.pid, created=birth, command=observed_command,
                        design_sha256=sha(PLAN), utc=s.utc(), freshly_recaptured=True), errors
        except Exception as exc:
            errors.append(dict(attempt=attempt + 1, error=repr(exc), utc=s.utc()))
        if time.time() >= end:
            break
        time.sleep(min(.1, max(0., end - time.time())))
    return None, errors


def child(action, folder, cutoff):
    folder.mkdir(parents=True, exist_ok=False)
    command = [str(PYTHON), '-B', '-u', str(SELF), action]
    forced, launch, code, failure, identity_errors = False, None, None, None, []
    with (folder / 'stdout.log').open('xb') as stdout, (folder / 'stderr.log').open('xb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, env=os.environ.copy(), stdout=stdout, stderr=stderr,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            launch = dict(pid=process.pid, created=psutil.Process(process.pid).create_time(), command=command,
                          design_sha256=sha(PLAN), utc=s.utc())
            need(process.poll() is None and not inspect(launch)['retired'], 'fresh exact task-owned child')
            commit(folder / ('worker_launch.json' if action == 'run' else 'launch.json'), launch)
            try:
                code = process.wait(timeout=max(.001, cutoff - time.time()))
            except subprocess.TimeoutExpired:
                forced = True
        except BaseException as exc:
            failure = dict(message=repr(exc), traceback=traceback.format_exc())
        finally:
            # Covers launch-file failures and all wait/administration errors.
            # A numerical/evaluator child cannot start without its registration.
            if launch is None:
                launch, identity_errors = recapture_owned_launch(process, command, cutoff)
            if launch is not None:
                try:
                    if process.poll() is None:
                        stop_exact(process, launch)
                        forced = True
                    code = process.wait(timeout=5)
                except Exception as exc:
                    identity_errors.append(dict(stage='exact_retirement', error=repr(exc), utc=s.utc()))
            elif process.poll() is not None:
                code = process.wait(timeout=1)
                # Otherwise leave an explicit unresolved identity record.  Do
                # not infer retirement, fabricate a birth or kill by PID alone.
    try:
        status = inspect(launch) if launch is not None else dict(retired=process.poll() is not None,
            original_popen_handle_exited=process.poll() is not None, exact_birth_capture_failed=True,
            unresolved_identity=process.poll() is None, requested_pid=process.pid, requested_command=command)
    except Exception as exc:
        status = dict(retired=False, unresolved_identity=True, inspection_error=repr(exc),
                      requested_pid=process.pid, requested_command=command)
    live = not status['retired']
    result = dict(returncode=code, forced=forced, identity=status, launch=launch, administration_error=failure,
        identity_recapture_errors=identity_errors,
        logs={} if live else {str(path): sha(path) for path in folder.glob('*.log')},
        live_logs_unsealed=live, only_parent_log_handles_closed=True,
        dependent_dispatch_stopped=live or failure is not None, utc=s.utc())
    commit(folder / 'exit.json', result)
    need(not live, 'unresolved child birth/command identity retained; dependent dispatch stopped, logs remain unsealed')
    if failure is not None:
        raise RuntimeError('Child administration failed after exact retirement: ' + failure['message'])
    return result


def evaluate():
    """Post-worker local evidence/metrics only; no original full-path gate call."""
    p = authority(False)
    me = psutil.Process()
    me.cpu_affinity([14])
    registration_deadline = min(time.time() + 5, datetime.fromisoformat(p['end_utc']).timestamp())
    while not (OUT / 'evaluator_01/launch.json').exists() and time.time() < registration_deadline:
        time.sleep(.02)
    expected = read(OUT / 'evaluator_01/launch.json')
    need(expected['pid'] == me.pid and expected['created'] == me.create_time()
         and expected['command'] == me.cmdline(), 'only exact supervisor-owned post-exit evaluator')
    exit_path = OUT / 'controller_01/exit.json'
    exited = read(exit_path)
    need(exited['returncode'] == 0 and exited['forced'] is False
         and inspect(read(OUT / 'controller_01/worker_launch.json'))['retired'], 'numerical worker actually exited0 and retired')
    api.verify_mapping(exited['logs'])
    final = s.fields.sealed(OUT / 'worker_disposition_01/results.json')
    counts = ledger()
    need(final['passed'] and final['native_complete'] and final['ledger'] == counts,
         'complete two-branch all-diagnostic ledger without unresolved work')
    physical = read(PHYSICAL)
    ctx, _ = context(False)
    decoded, prefixes, artifacts, local = {}, {}, {}, [[], []]
    for reservation in counts['reservations']:
        authority(False)
        index, label = reservation['branch'], reservation['label']
        case = physical['cases'][index]
        initial, _ = preparation.seed_for(index)
        if label.endswith('_split_b'):
            parent_label = f'branch{index}_split_a'
        elif '_local_' in label and int(label.rsplit('_', 1)[1]) > 1:
            parent_label = f'branch{index}_local_{int(label.rsplit("_", 1)[1]) - 1:05d}'
        else:
            parent_label = None
        before = initial if parent_label is None else decoded[parent_label]['result']['checkpoint']
        prefix = None if parent_label is None else prefixes[parent_label]
        previous = None if parent_label is None else sha(OUT / 'records' / parent_label / 'results.json')
        need(reservation['input_checkpoint_sha256'] == api.digest(before)
             and reservation['previous_result_sha256'] == previous, 'independent exact branch FULL seed/ancestry')
        folder = OUT / 'records' / label
        guard, policy = [s.fields.sealed(folder / name / 'results.json') for name in ('guard_completion', 'timecap_guard')]
        need(guard['passed'] and policy['passed'], 'unchanged passed independent record gates')
        api.verify_mapping(guard['artifacts'])
        record, updated = ctx.job.codec.read_record(folder / 'call.json.xz', sha(PHYSICAL), prefix)
        need(record['spec'] == case['spec'] and record['input_checkpoint_sha256'] == api.digest(before)
             and guard['full_checkpoint_sha256'] == api.digest(record['result']['checkpoint'])
             and len(record['rows']) == guard['saved_steps'] <= reservation['maximum_saved_steps'],
             'complete original raw/checkpoint and work associations')
        receipt = DOC.read(folder / 'results.json')
        need(read(folder / 'completion.json')['results_sha256'] == sha(folder / 'results.json')
             and receipt['passed'] and receipt['summary']['passed']
             and receipt['transport_design_sha256'] == sha(PLAN)
             and receipt['physical_design_sha256'] == sha(PHYSICAL)
             and receipt['input_checkpoint_sha256'] == api.digest(before)
             and receipt['previous_receipt_sha256'] == previous
             and receipt['output_checkpoint_sha256'] == api.digest(record['result']['checkpoint'])
             and receipt['new_saved_steps'] == len(record['rows'])
             and receipt['role'] == 'restart_diagnostic'
             and receipt['original_binding'] == ctx.job.binding(physical, case)
             and receipt['numerical_policy_contract_sha256'] == record['numerical_policy_contract_sha256'] == sha(ctx.job.WORK),
             'original complete physics receipt binds identical design, policy, seed and predecessor')
        api.verify_mapping(receipt['artifacts'])
        admission = s.fields.sealed(OUT / 'admissions' / f'{reservation["index"]:03d}' / 'results.json')
        need(admission['raw_sha256'] == sha(folder / 'call.json.xz')
             and admission['full_checkpoint_sha256'] == api.digest(record['result']['checkpoint'])
             and admission['physical_guard_sha256'] == sha(folder / 'guard_completion/results.json')
             and admission['timecap_guard_sha256'] == sha(folder / 'timecap_guard/results.json')
             and policy['raw_sha256'] == sha(folder / 'call.json.xz')
             and policy['original_physical_guard_sha256'] == sha(folder / 'guard_completion/results.json'),
             'complete owner admission and original policy/physics gates bind identical raw')
        launch = read(folder / 'launch.json')
        command = launch.get('command', launch.get('argv'))
        worker_launch = read(OUT / 'controller_01/worker_launch.json')
        need(launch['pid'] == worker_launch['pid'] and launch['created'] == worker_launch['created']
             and command == worker_launch['command']
             and launch['transport_design_sha256'] == sha(PLAN)
             and launch['physical_design_sha256'] == sha(PHYSICAL)
             and launch['input_checkpoint_sha256'] == api.digest(before)
             and inspect({**launch, 'command': command})['retired'],
             'actual exact retired numerical producer and full command bind this record')
        geometry = ctx.geometry_for(case)
        physical_check = ctx.baseline.kernel(record, case['spec'], ctx.job.binding(physical, case),
            before, geometry, sha(PHYSICAL), physical['minimum_gap_semantics'])
        guard_check = s.q.guard.audit(record)
        policy_check = policy_auditor.audit(record, before, case, CONFIG, ctx)
        need(physical_check['passed'] and guard_check['passed'] and policy_check['passed'],
             'original independent post-exit physics, guard and fixed-selector replay')
        trace = np.asarray([[r['time_s'], *r['position_m'], *r['orientation'], *r['velocity_generalized']]
                            for r in record['rows']], dtype=np.float64)
        need(np.array_equal(trace, np.load(folder / 'trace.npy', mmap_mode='r', allow_pickle=False)),
             'every original raw row matches the saved trace')
        decoded[label], prefixes[label] = record, updated
        if '_local_' in label:
            local[index].append(label)
        for path in folder.rglob('*'):
            if path.is_file():
                artifacts[str(path)] = sha(path)
    for index in (0, 1):
        serial, left, right = [decoded[f'branch{index}_{name}'] for name in ('serial', 'split_a', 'split_b')]
        restart = s.fields.sealed(OUT / f'restart_branch{index}/results.json')
        need(restart['passed'] and len(serial['rows']) == 256 and len(left['rows']) == len(right['rows']) == 128
             and api.digest(serial['rows']) == api.digest(left['rows'] + right['rows'])
             and api.digest(serial['result']['checkpoint']) == api.digest(right['result']['checkpoint']),
             'post-exit exact256 versus128+128 FULL checkpoint/history restart')
        branch = final['branches'][index]
        need(branch['branch'] == index and branch['labels'] == local[index]
             and len(local[index]) <= LOCAL_CALLS[index]
             and sum(len(decoded[label]['rows']) for label in local[index]) == branch['saved_steps'] <= LOCAL_STEPS[index],
             'complete ordered local branch calls/steps, diagnostics excluded')
        cp = DOC.read(OUT / f'recoverable_branch{index}/checkpoint.json')
        need(api.digest(cp) == api.digest(decoded[local[index][-1]]['result']['checkpoint']) == branch['full_checkpoint_sha256']
             and read(OUT / f'recoverable_branch{index}/prefix.json') == prefixes[local[index][-1]].reference(),
             'standalone final FULL checkpoint/raw prefix identical to admitted local chain')
    seeds = [preparation.seed_for(i)[0]['state'] for i in (0, 1)]
    need(seeds[0] == seeds[1], 'both branches reset to the identical original FULL physical state/history')
    initial = [[v['t'], *v['x'], *v['p'], *v['q']] for v in seeds]
    terminal = [decoded[labels[-1]]['result'] for labels in local]
    stops = [value['checkpoint']['state']['t'] for value in terminal]
    def blocks(index):
        for label in local[index]:
            yield np.load(OUT / 'records' / label / 'trace.npy', mmap_mode='r', allow_pickle=False)
    spec = physical['cases'][0]['spec']
    cfg = spec['config']
    metrics = s.q.job.path_metrics.metrics(blocks(0), blocks(1), initial[0], initial[1], stops[0], stops[1],
        cfg['prolate_semiaxes_m'][1], cfg['target_mean_interstitial_velocity_m_s'])
    gates = s.q.job.policy.GATES
    need(read(PROPOSAL)['original_accuracy_gates'] == gates, 'original accuracy gates unchanged')
    limits = {key: gates[key] for key in ('whole_position_over_b_max', 'whole_axis_vector_norm_max',
                                        'endpoint_q_over_U_max', 'mean_L1_q_over_U_max')}
    checks = {key: bool(np.isfinite(metrics[key]) and 0 <= metrics[key] <= value) for key, value in limits.items()}
    complete = all(t == physical['local_stop_s'] for t in stops)
    events = terminal[0]['status'] == terminal[1]['status'] and terminal[0]['persistent_contact_observed'] == terminal[1]['persistent_contact_observed']
    def event_time(key, limit):
        a, b = [value[key] for value in terminal]
        return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= gates[limit])
    dwell = event_time('first_contact_dwell_time_s', 'first_dwell_time_difference_s_max')
    exits = [value['time_s'] if value['status'] == 'full_window_exit' else None for value in terminal]
    exit_times = (exits[0] is None and exits[1] is None) or (exits[0] is not None and exits[1] is not None
        and abs(exits[0] - exits[1]) <= gates['exit_time_difference_s_max'])
    need(metrics['common_start_s'] == physical['seed_time_s'] and metrics['common_stop_s'] == min(stops),
         'original held-velocity metric and absolute nonzero local clock')
    authority(False)
    api.verify_mapping(artifacts)
    seal(OUT / 'evaluation_01', dict(passed=True, local_only=True,
        local_screen_passed=all(checks.values()) and complete and events and dwell and exit_times,
        metrics=metrics, original_numeric_limits=limits, local_numeric_checks=checks,
        complete_declared_local_interval=complete, local_events_equal=events, local_dwell_times_pass=dwell,
        local_exit_times_pass=exit_times, ledger=counts, artifacts=artifacts, source_files=p['source_files'],
        physical_inputs=p['physical_inputs'], design_sha256=sha(PLAN), original_full_path_admission=False,
        full_path_accuracy_passed=False, core_result_admitted=False, publication_case_count_increment=0,
        two_factors_do_not_establish_convergence_order=True, new_native_solver_calls=0, new_transport_steps=0,
        exact_numerical_worker_retired=True, administrative_evaluator_live_when_written=True,
        external_final_exit_log_receipt_required=True, utc=s.utc()))


def supervise():
    p = authority(False)
    expected_design_sha = sha(PLAN)
    need(time.time() + 90 < datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp(),
         'fresh numerical dispatch still has the unchanged transaction reserve')
    me = psutil.Process()
    me.cpu_affinity([14])
    need(not (OUT / 'supervisor_launch.json').exists(), 'no duplicate independent diagnostic supervisor')
    commit(OUT / 'supervisor_launch.json', dict(pid=me.pid, created=me.create_time(), command=me.cmdline(),
        design_sha256=sha(PLAN), utc=s.utc()))
    worker = evaluator = None
    error, finalization_failures = None, []
    try:
        worker = child('run', OUT / 'controller_01', datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp())
        need(worker['returncode'] == 0 and not worker['forced'], 'complete numerical worker retired normally')
        evaluator = child('evaluate', OUT / 'evaluator_01', datetime.fromisoformat(p['end_utc']).timestamp() - 60)
        need(evaluator['returncode'] == 0 and not evaluator['forced'], 'bounded post-exit local evaluator retired normally')
    except Exception as exc:
        error = dict(message=repr(exc), traceback=traceback.format_exc())
    finally:
        try:
            authority(False)
        except Exception as exc:
            finalization_failures.append(dict(kind='final_source_input_resource_gate', error=repr(exc)))
            if error is None:
                error = dict(message=repr(exc), traceback=traceback.format_exc())
        # Record a negative source/input gate without excusing it or dispatching
        # again.  Finalization itself remains inside the original hard clock.
        need(datetime.now(timezone.utc) < datetime.fromisoformat(p['end_utc'])
             <= datetime.fromisoformat(DEADLINE), 'negative/positive finalization before the SAME absolute end')
        try:
            resources(p)
        except Exception as exc:
            finalization_failures.append(dict(kind='resource_limit', error=repr(exc)))
        try:
            counts = ledger()
        except Exception as exc:
            counts = failed_ledger(exc)
            finalization_failures.append(dict(kind='ledger_authentication', error=repr(exc)))
        try:
            evaluation = s.fields.sealed(OUT / 'evaluation_01/results.json') if (OUT / 'evaluation_01/completion.json').exists() else None
        except Exception as exc:
            evaluation = None
            finalization_failures.append(dict(kind='evaluation_receipt', error=repr(exc)))
        retirements = retirement_snapshot()
        numerical_retired = any(row['role'] == 'controller_01' and row['retirement_verified'] for row in retirements)
        all_children_retired = bool(retirements) and all(row['retirement_verified'] for row in retirements)
        passed = (error is None and not finalization_failures and counts['ledger_authenticated']
                  and not counts['admission_failures'] and all_children_retired
                  and evaluation is not None and worker is not None and evaluator is not None)
        seal(OUT / 'final_disposition_01', dict(passed=passed, error=error, local_only=True,
            local_screen_passed=evaluation['local_screen_passed'] if evaluation is not None else None,
            ledger=counts, worker_exit=worker, evaluator_exit=evaluator, finalization_failures=finalization_failures,
            full_path_accuracy_passed=False, core_result_admitted=False, publication_case_count_increment=0,
            all_exact_numerical_producers_retired=numerical_retired, retirement_inspections=retirements,
            all_exact_child_identities_retired=all_children_retired,
            unresolved_identities=[row for row in retirements if row['unresolved_identity']],
            supervisor_live_logs_deferred=True, external_final_exit_log_receipt_required=True,
            source_files=p['source_files'], physical_inputs=p['physical_inputs'], design_sha256=expected_design_sha,
            observed_control_files=control_hash_snapshot(), utc=s.utc()))
    if not passed:
        raise SystemExit(2)


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else None
    if action == 'controls':
        print(json.dumps(controls(), sort_keys=True), flush=True)
    elif action == 'authorize' and len(sys.argv) == 3:
        authorize(sys.argv[2])
    elif action in ('run', 'supervise', 'evaluate') and len(sys.argv) == 2:
        {'run': run, 'supervise': supervise, 'evaluate': evaluate}[action]()
    else:
        raise SystemExit('Explicit controls, authorize EXACT_NEW_HUMAN_APPROVAL_SHA, supervise, run or evaluate only; no default dispatch.')
