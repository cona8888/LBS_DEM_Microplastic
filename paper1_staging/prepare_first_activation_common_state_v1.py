"""Prepare the first-activation common-FULL-state discriminator; no method change or dispatch.

Only sealed metadata, the unchanged lossless raw/history codec, checkpoint
contract rebinding and synthetic metric controls are used. There is no worker,
authorization writer, transport, contact solve or physical-auditor replay.
"""
from datetime import datetime, timezone
from pathlib import Path
import copy
import json
import math
import shutil
import sys

import psutil

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_core_v2 as original

s, api = original.s, original.s.api
ROOT = s.ROOT
SELF = Path(__file__).resolve()
PRIOR_DESIGN = ROOT / 'paper1_designs/full_horizon_timecap_20261016'
PRIOR_RUN = ROOT / 'paper1_runs/full_horizon_timecap_20261016'
DESIGN = ROOT / 'paper1_designs/first_activation_common_state_20261018'
PHYSICAL = DESIGN / 'physical_cases_01.json'
PROPOSAL = DESIGN / 'proposal_01.json'
PREPARATION_LAUNCH = ROOT / 'paper1_evaluations/first_activation_preparation_20261018/preparation_01/launch.json'
DEADLINE = '2026-10-18T02:59:34.905691+00:00'
SOURCE_LEVEL = PRIOR_RUN / 'levels/f0p03125'
SOURCE_LAST = 'production_00120'
SOURCE_LAST_FULL_CHECKPOINT_SHA256 = '40fcc4d5d0d6305bc87858bb70522ce29e8c14a73aa3a84e9ccd2f04b88449e1'
ANCHOR_S = .15358196739490534
DURATION_S = .0025
BRANCH_STEPS = (4500, 9000)
BRANCH_LOCAL_CALLS = (2, 3)
RESTART_STEPS_EACH = 512
ACTIVE_RESTART_STEPS_EACH = 8192
NEW_STEPS = sum(BRANCH_STEPS) + 2 * RESTART_STEPS_EACH + 2 * ACTIVE_RESTART_STEPS_EACH
NEW_CALLS = sum(BRANCH_LOCAL_CALLS) + 12
LOCAL_CLOSED = ROOT / 'paper1_runs/support_common_state_20261017_v2/final_execution_receipt_01/results.json'
DIVERGENCE = ROOT / 'paper1_evaluations/timecap_failure_20261017/independent_divergence_01/results.json'
DIVERGENCE_EXIT = ROOT / 'paper1_evaluations/timecap_failure_20261017/divergence_execution_01/receipt_01/results.json'
LATEST_CLOSED = ROOT / 'paper1_runs/first_persistent_common_state_20261017/final_execution_receipt_01/results.json'
CONTEXT = ROOT / 'paper1_evaluations/first_activation_preparation_20261018/context_02/results.json'
CONTEXT_EXIT = ROOT / 'paper1_evaluations/first_activation_preparation_20261018/context_execution_02/receipt_01/results.json'
EXPECTED = {
    str(CONTEXT): '5e0e7fcbc3ce468cda7fe0ce19b05eb60457e7e235b70aae7a344a3bc0940aab',
    str(CONTEXT_EXIT): '175cc6b21ad33f8f18a694d804b845f94fdfda85cfc539971f7c9d3cd1e1ccf7',
    str(LATEST_CLOSED): '9e63a1abc10801cbd566e61438d1c704c6918fbb7d591f2cfd5d93af94107db3',
    str(ROOT / 'paper1_staging/run_first_activation_common_state_v1.py'): 'aa10079519a36fc58c41a62b12861c5d6b7bc8372869be4f97532e1ea0f008dc',
    str(ROOT / 'paper1_staging/test_first_activation_runtime_v1.py'): '6c0c328cb58e28ddb99ff99413015e3f7774d16f7f0a084b6336432473100d62',
    str(ROOT / 'paper1_staging/prepare_support_common_state_v4.py'): '85ccf090dad71205ffdbc539f4b495cda2ecfaa744f989123499768e5ba1f5bf',
    str(ROOT / 'paper1_staging/run_support_common_state_v3.py'): '229589bcf20dec6c2c1bbd92ff7d5974f12c6f16a2ce18dc85826116717ea867',
    str(PRIOR_RUN / 'comparison_fine/results.json'): '15d48be2710368ad8499a2998b53f0c31c085b6f1880116fc317d47b1ad048d7',
    str(PRIOR_RUN / 'final_execution_receipt_01/results.json'): 'd23b764b5d5c3769ee2607aca7c0107e424352641306b6575a9b2522f943bf1f',
    str(PRIOR_DESIGN / 'design_01.json'): 'aead45d9b3983c928f9f5eabd0c77c21c23084ff7e9d9c185c520ed59380f41f',
    str(PRIOR_DESIGN / 'physical_cases_01.json'): '8538038840008bc1b5b06b0c595f4b916cfc9601f3573fff09284dba837d742b',
    str(LOCAL_CLOSED): 'd34c607f6278235173470f1778826e4320320b48cd565f9eb975d31d551511cb',
    str(DIVERGENCE): '72c4edde6ff0f999a0b050bc2e56a60938c9192b9925f3f75560112aadec3e94',
    str(DIVERGENCE_EXIT): '9e532e11cd2a7c1e0b0c0079d44e8d7f75c7255775b101b0e7ce128c1c5b0927',
}


def clock():
    api.require(datetime.now(timezone.utc) < datetime.fromisoformat(DEADLINE), 'Original absolute bound; no reset')


def bound(extra_bytes=0):
    s.environment()
    clock()
    retained = sum(p.stat().st_size for name in ('paper1_runs', 'paper1_designs', 'paper1_evaluations')
                   for p in (ROOT / name).rglob('*') if p.is_file())
    free = shutil.disk_usage(ROOT).free
    api.require(retained + extra_bytes < 20 * 1024**3 and free - extra_bytes > 20 * 1024**3,
                'Unchanged 20GiB retention and 20GiB free reserve')
    return dict(retained_bytes=retained, free_bytes=free)


def budget(saved=10283231, calls=2159, shared_saved=4635319, shared_calls=989):
    api.require(all(type(value) is int and value >= 0 for value in (saved, calls, shared_saved, shared_calls))
                and saved + NEW_STEPS <= 11300000
                and calls + NEW_CALLS <= 2400, 'No cumulative case budget increase')
    api.require(shared_saved + NEW_STEPS <= 5632768 and shared_calls + NEW_CALLS <= 1217,
                'No original shared all-attempt saved-step or call ceiling increase')
    return dict(prior_conservative_case_saved_steps=saved, prior_conservative_case_calls=calls,
        maximum_additional_saved_steps=NEW_STEPS, maximum_additional_calls=NEW_CALLS,
        maximum_case_saved_steps_after=saved + NEW_STEPS, maximum_case_calls_after=calls + NEW_CALLS,
        existing_case_saved_step_cap=11300000, existing_case_call_cap=2400,
        prior_shared_saved_steps=shared_saved, prior_shared_calls=shared_calls,
        original_shared_saved_step_cap=5632768, original_shared_call_cap=1217,
        maximum_shared_saved_steps_after=shared_saved + NEW_STEPS,
        maximum_shared_calls_after=shared_calls + NEW_CALLS,
        branch_local_step_caps=list(BRANCH_STEPS), branch_local_call_caps=list(BRANCH_LOCAL_CALLS),
        exact_restart_steps_per_branch=RESTART_STEPS_EACH, exact_restart_calls_per_branch=3,
        restart_serial_steps=256, restart_split_steps=[128, 128],
        maximum_active_restart_steps_per_branch=8192, active_restart_calls_per_branch=3,
        maximum_first_active_record_rows=4096, preactive_call_cap=4096, postqualified_call_cap=5000,
        all_new_saved_steps_are_discarded_diagnostics=True)


def prefix_saved_steps(counts):
    """Sum authenticated record counts; a record cap is never an actual count."""
    api.require(type(counts) in (list, tuple) and len(counts) > 0
                and all(type(value) is int and 0 < value <= 5000 for value in counts),
                'Actual positive integer saved counts within original per-record cap')
    return sum(counts)


def require_prefix_counter(actual, counts):
    api.require(type(actual) is int and actual == prefix_saved_steps(counts),
                'Full checkpoint counter equals authenticated heterogeneous saved-row sum')


def audited_guard(folder, audit):
    """Authenticate both original guard documents before reading their count."""
    guard_path = folder / 'guard_completion/results.json'
    pins = {str(path): audit['artifacts'][str(path)]
            for path in (guard_path, guard_path.with_name('completion.json'))}
    api.verify_mapping(pins)
    guard = s.fields.sealed(guard_path)
    api.require(guard['passed'] and prefix_saved_steps([guard['saved_steps']]) == guard['saved_steps'],
                'Original accepted guard count bound by both full-audit seals')
    api.verify_mapping(pins)
    return guard, pins


def controls():
    b = budget()
    assert b['maximum_additional_saved_steps'] == 30908 and b['maximum_additional_calls'] == 17
    assert sum(BRANCH_LOCAL_CALLS) + 12 == NEW_CALLS
    assert sum(BRANCH_STEPS) + 1024 + 16384 == NEW_STEPS
    for saved, calls in ((11300000 - NEW_STEPS + 1, 0), (0, 2400 - NEW_CALLS + 1)):
        try:
            budget(saved, calls)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Case ceiling overflow admitted')
    for shared_saved, shared_calls in ((5632768 - NEW_STEPS + 1, 0), (0, 1217 - NEW_CALLS + 1)):
        try:
            budget(shared_saved=shared_saved, shared_calls=shared_calls)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Original shared ceiling overflow admitted')
    heterogeneous = [4096] * 121 + [5000] * 158
    assert len(heterogeneous) == 279
    assert prefix_saved_steps(heterogeneous) == 1285616
    require_prefix_counter(1285616, heterogeneous)
    try:
        require_prefix_counter(1395000, heterogeneous)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Record-count times cap substituted for actual saved rows')
    for invalid in ([True], [0], [-1], [5001], [4096.0], []):
        try:
            prefix_saved_steps(invalid)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Invalid record count admitted')
    initial = [.4, 0., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0., 0.]
    rows = np.asarray([[.405, 0., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0., 0.],
                       [.41000000000000003, 0., 0., 0., 1., 0., 0., 0., 0., 0., 0., 0., 0.]])
    end = float(rows[-1, 0])
    metrics = s.q.job.path_metrics.metrics([rows], [rows], initial, initial, end, end, 1., 1.)
    assert metrics['common_start_s'] == .4 and metrics['common_stop_s'] == end
    assert metrics['mean_L1_q_over_U_max'] == metrics['endpoint_q_over_U_max'] == 0.
    try:
        s.q.job.policy.pair_gates(dict(complete_observation=True, stop_s=end),
                                 dict(complete_observation=True, stop_s=end), metrics, s.q.job.policy.GATES)
    except ValueError:
        pass
    else:
        raise AssertionError('Local clock admitted as an original fresh full path')
    return dict(passed=True, zero_transport_steps=0, zero_native_solver_calls=0,
        budget_arithmetic_exact=True, saved_step_overflow_rejected=True, call_overflow_rejected=True,
        original_shared_saved_step_overflow_rejected=True, original_shared_call_overflow_rejected=True,
        heterogeneous_saved_prefix_count_exact=True, uniform_record_cap_counter_rejected=True,
        invalid_saved_record_counts_rejected=True,
        identical_local_trace_error_zero=True, absolute_clock_preserved=True,
        forged_full_observation_does_not_bypass_original_fresh_path_gate=True,
        numerical_dispatch_entry_point_absent=True)


def seed_for(index):
    """Return an exact physical seed with only a new diagnostic contract binding."""
    api.require(type(index) is int and 0 <= index < 2, 'Declared diagnostic branch')
    physical = s.read(PHYSICAL)
    provenance = s.fields.sealed(DESIGN / 'seed_source/provenance_01/results.json')
    api.verify_mapping(provenance['seed_artifacts'])
    before = original.DOC.read(DESIGN / 'seed_source/checkpoint.json')
    api.require(api.digest(before) == provenance['full_checkpoint_sha256'], 'Authenticated complete seed')
    case = physical['cases'][index]
    result = s.q.job.parent.model.checkpoint(case['spec'], s.q.job.binding(physical, case), before, True)
    api.require(result['state'] == before['state'] and result['state_sha256'] == before['state_sha256'],
                'No physical state, history, pending trial or counter changed')
    return result, None


def prepare():
    bound()
    api.require(not DESIGN.exists(), 'New create-only package; no frozen source or evidence overwritten')
    import run_first_activation_common_state_v1 as runtime
    frozen_preparation_sources = {str(SELF): s.sha(SELF), str(Path(runtime.__file__).resolve()): s.sha(runtime.__file__)}
    pure = controls()
    runtime_controls = runtime.controls()
    api.require(runtime_controls['passed'], 'Concrete guarded runtime controls before preparation')
    api.verify_mapping(frozen_preparation_sources)
    proc = psutil.Process()
    preparation_launch = dict(pid=proc.pid, created=proc.create_time(), command=proc.cmdline(),
        preparation_source_sha256=frozen_preparation_sources[str(SELF)],
        runner_source_sha256=frozen_preparation_sources[str(Path(runtime.__file__).resolve())],
        original_shared_end_utc=DEADLINE, scope='Read-only administrative preparation; no numerical worker.', utc=s.utc())
    s.commit(PREPARATION_LAUNCH, preparation_launch)
    api.verify_mapping(EXPECTED)
    local_closed = s.fields.sealed(LOCAL_CLOSED)
    latest_closed = s.fields.sealed(LATEST_CLOSED)
    api.require(latest_closed['passed'] and latest_closed['administrative_execution_closed']
                and latest_closed['all_exact_owned_identities_retired']
                and latest_closed['local_screen_passed'] and not latest_closed['full_path_accuracy_passed'],
                'Both earlier common-state tests are locally passed and closed; full horizon is unqualified')
    divergence = s.fields.sealed(DIVERGENCE)
    divergence_exit = s.fields.sealed(DIVERGENCE_EXIT)
    api.require(local_closed['passed'] and local_closed['administrative_execution_closed']
                and local_closed['all_exact_owned_identities_retired']
                and local_closed['local_screen_passed'] and not local_closed['full_path_accuracy_passed'],
                'Prior local test is closed; local pass does not qualify the original full path')
    api.require(divergence['passed'] and divergence['new_native_solver_calls'] == 0
                and divergence['new_integration_calls'] == 0 and divergence_exit['passed']
                and divergence_exit['administrative_execution_closed']
                and divergence_exit['all_exact_owned_analysis_identities_retired']
                and divergence_exit['actual_python_returncode'] == 0
                and divergence['original_whole_path_scalars_reproduced'],
                'Authenticated closed saved-data selection; zero numerical work')
    api.require(runtime.inspect(divergence['launch'])['retired'], 'Exact saved-analysis birth/full command retired')
    context = s.fields.sealed(CONTEXT)
    context_exit = s.fields.sealed(CONTEXT_EXIT)
    api.require(context['passed'] and context_exit['passed']
                and context_exit['administrative_execution_closed']
                and context['exact_window_s'] == [.15280694670867345, .15280694670867345 + DURATION_S]
                and context['new_integration_calls'] == context['new_native_solver_calls'] == context['new_transport_steps'] == 0
                and runtime.inspect(context['launch'])['retired'], 'Closed exact-window saved context before prospective freeze')
    api.verify_mapping(context['artifacts'])
    episode = divergence['diagnosis']['first_duration_qualified_episodes']['0.001']
    api.require(episode['start_s'] == ANCHOR_S, 'Frozen first saved1ms episode anchor')
    for body in (local_closed, latest_closed, divergence):
        for key in ('expected_source_files', 'expected_physical_inputs', 'source_files', 'physical_inputs'):
            if key in body:
                api.verify_mapping(body[key])
    failed = s.fields.sealed(PRIOR_RUN / 'comparison_fine/results.json')
    closed = s.fields.sealed(PRIOR_RUN / 'final_execution_receipt_01/results.json')
    api.require(not failed['passed'] and failed['original_gate_values'] == s.q.job.policy.GATES
                and closed['passed'] and closed['all_exact_owned_identities_retired']
                and closed['dependent_dispatch_stopped'] and not closed['qualification_passed'],
                'Closed scientific failure remains stopped; preparation confers no dispatch authority')
    prior = s.read(PRIOR_DESIGN / 'design_01.json')
    old_auth = s.read(PRIOR_DESIGN / 'authorization_01.json')
    api.require(prior['end_utc'] == old_auth['end_utc'] == DEADLINE
                and prior['binding'] == api.digest({k: v for k, v in prior.items() if k != 'binding'}),
                'Original shared design and absolute deadline')
    for key in ('source_files', 'physical_inputs'):
        api.verify_mapping(prior[key])
    for key in ('source_files', 'evidence_files'):
        api.verify_mapping(failed[key])
    physical_source = s.read(PRIOR_DESIGN / 'physical_cases_01.json')
    source_case = next(x for x in physical_source['cases'] if x['factor'] == .03125)
    audit_path = SOURCE_LEVEL / 'full_audit_01/results.json'
    audit = s.fields.sealed(audit_path)
    api.require(s.sha(audit_path) == failed['evidence_files'][str(audit_path)]
                and audit['passed'] and audit['fresh_t0'] and audit['original_physics_and_guard_replayed']
                and audit['full_selector_policy_replayed'], 'Existing complete finer path audit')
    guards = []
    for label in audit['production_labels']:
        clock()
        path = SOURCE_LEVEL / 'records' / label / 'timecap_guard/results.json'
        api.require(s.sha(path) == audit['artifacts'][str(path)], 'Existing selector-clock seal')
        guards.append(s.fields.sealed(path))
    eligible = [i for i, value in enumerate(guards) if value['stop_s'] <= ANCHOR_S]
    endpoint_index = max(eligible)
    api.require(audit['production_labels'][endpoint_index] == SOURCE_LAST
                and guards[endpoint_index + 1]['stop_s'] > ANCHOR_S,
                'Last actual finer FULL checkpoint not after the first saved1ms episode onset')

    inputs = {**prior['physical_inputs'], **failed['evidence_files'], **EXPECTED,
              str(PREPARATION_LAUNCH): s.sha(PREPARATION_LAUNCH), str(audit_path): s.sha(audit_path),
              str(audit_path.with_name('completion.json')): s.sha(audit_path.with_name('completion.json'))}
    source_labels = audit['production_labels'][:endpoint_index + 1]
    api.require(source_labels == [f'production_{index:05d}' for index in range(1, endpoint_index + 2)],
                'Complete contiguous original source prefix')
    source_guards, source_counts, source_guard_pins = [], [], {}
    for label in source_labels:
        clock()
        guard, pins = audited_guard(SOURCE_LEVEL / 'records' / label, audit)
        source_guards.append(guard)
        source_counts.append(guard['saved_steps'])
        source_guard_pins.update(pins)
    expected_prefix_rows = prefix_saved_steps(source_counts)
    api.require(source_guards[-1]['full_checkpoint_sha256'] == SOURCE_LAST_FULL_CHECKPOINT_SHA256,
                'Prospective last checkpoint is the original accepted FULL identity')
    inputs.update(context['artifacts'])
    inputs.update(source_guard_pins)
    codec = original.archives.build(s.q.job.codec, preset=9)
    prefix = before = last = None
    for index, label in enumerate(source_labels, 1):
        clock()
        folder = SOURCE_LEVEL / 'records' / label
        guard, pins = audited_guard(folder, audit)
        api.require(guard == source_guards[index - 1] and guard['saved_steps'] == source_counts[index - 1],
                    'Preauthenticated count and guard remain unchanged before decode')
        for path, expected in guard['artifacts'].items():
            api.require(path in audit['artifacts'] and s.sha(path) == expected == audit['artifacts'][path],
                        'Original raw/receipt/trace artifact seal')
            inputs[path] = expected
        clock()
        rec, prefix = codec.read_record(folder / 'call.json.xz', s.sha(PRIOR_DESIGN / 'physical_cases_01.json'), prefix)
        clock()
        api.require(rec['spec'] == source_case['spec'] and rec['input_checkpoint_sha256'] == api.digest(before),
                    'Exact contiguous full-checkpoint/history ancestry from fresh t0')
        cp = rec['result']['checkpoint']
        previous_steps = 0 if before is None else before['state']['steps']
        api.require(len(rec['rows']) == source_counts[index - 1]
                    and cp['state']['steps'] == previous_steps + source_counts[index - 1]
                    and api.digest(cp) == guard['full_checkpoint_sha256'], 'All saved steps and full output identity')
        require_prefix_counter(cp['state']['steps'], source_counts[:index])
        expected_trace = np.asarray([[row['time_s'], *row['position_m'], *row['orientation'],
                                      *row['velocity_generalized']] for row in rec['rows']], dtype=np.float64)
        api.require(np.array_equal(expected_trace, np.load(folder / 'trace.npy', mmap_mode='r', allow_pickle=False)),
                    'Every source trace row reconstructs from unchanged raw codec')
        api.verify_mapping(pins)
        before, last = cp, rec
        if index % 50 == 0:
            print('SUPPORT_SEED_RAW_RECONSTRUCTED', index, flush=True)
    require_prefix_counter(before['state']['steps'], source_counts)
    api.require(before['state']['steps'] == expected_prefix_rows
                and api.digest(before) == SOURCE_LAST_FULL_CHECKPOINT_SHA256
                and before['state']['t'] == .15280694670867345
                and before['state']['pending_trial'] is None, 'Exact accepted support seed, no pending trial')
    start, stop = before['state']['t'], before['state']['t'] + DURATION_S
    cases = []
    for factor in (.0625, .03125):
        case = copy.deepcopy(next(x for x in physical_source['cases'] if x['factor'] == factor))
        case['id'] += '__same_full_state_first_activation_diagnostic'
        case['role'] = 'discarded_same_full_state_first_activation_diagnostic'
        case['spec']['case_id'] = case['id']
        case['spec']['horizon_s'] = stop
        cases.append(case)
    def normalized(case):
        result = copy.deepcopy(case['spec'])
        result.pop('case_id'); result.pop('refinement')
        for key in s.factory.SCALED_CONTROLS:
            result['config']['numerics'].pop(key)
        return result
    api.require(normalized(cases[0]) == normalized(cases[1])
                and all(cases[1]['spec']['config']['numerics'][key] == cases[0]['spec']['config']['numerics'][key] / 2
                        for key in s.factory.SCALED_CONTROLS), 'Only the original four numerical controls halve')
    physical = dict(schema='paper1.first-activation-common-state.physical.v1', cases=cases, diagnostic_only=True,
        seed_time_s=start, local_stop_s=stop, original_paper1_horizon_s=source_case['spec']['horizon_s'],
        minimum_gap_semantics=physical_source['minimum_gap_semantics'],
        numerical_controller=copy.deepcopy(physical_source['numerical_controller']),
        numerical_controller_source_sha256=physical_source['numerical_controller_source_sha256'],
        physical_equation_changes=[], accuracy_gate_changes=[])
    physical['binding'] = api.digest(physical)
    api.verify_mapping(frozen_preparation_sources)
    api.verify_mapping(inputs)
    bound(256 * 1024**2)
    DESIGN.mkdir(parents=True, exist_ok=False)
    s.commit(PHYSICAL, physical)
    seed_folder = DESIGN / 'seed_source'
    seed_folder.mkdir(parents=True, exist_ok=False)
    original.DOC.store(seed_folder / 'checkpoint.json', before, s.sha(PRIOR_DESIGN / 'physical_cases_01.json'))
    s.commit(seed_folder / 'prefix.json', prefix.reference())
    seed_artifacts = {str(path): s.sha(path) for path in seed_folder.iterdir() if path.is_file()}
    s.seal(seed_folder / 'provenance_01', dict(passed=True, preparation_only=True,
        preparation_launch_path=str(PREPARATION_LAUNCH), preparation_launch_sha256=s.sha(PREPARATION_LAUNCH),
        frozen_preparation_sources=frozen_preparation_sources,
        source_level='f0p03125', source_last_label=SOURCE_LAST, source_physical_sha256=s.sha(PRIOR_DESIGN / 'physical_cases_01.json'),
        source_full_audit_sha256=s.sha(audit_path), raw_records_reconstructed=endpoint_index + 1,
        raw_rows_reconstructed=before['state']['steps'], full_checkpoint_sha256=api.digest(before),
        source_record_saved_counts=source_counts, authenticated_expected_prefix_rows=expected_prefix_rows,
        original_guard_result_and_completion_pins=source_guard_pins,
        previous_closed_local_sha256=EXPECTED[str(LOCAL_CLOSED)],
        saved_divergence_selection_sha256=EXPECTED[str(DIVERGENCE)],
        physical_state_sha256=before['state_sha256'], seed_time_s=start,
        terminal_row=last['rows'][-1], source_history_prefix=prefix.reference(),
        complete_history_preserved=True, new_transport_steps=0, new_native_solver_calls=0,
        physical_auditor_replays=0, seed_artifacts=seed_artifacts, source_evidence_files=inputs, utc=s.utc()))
    seed_checks = []
    for index in range(2):
        rebound, fresh_prefix = seed_for(index)
        record = dict(design_sha256=s.sha(PHYSICAL), rows=[],
                      result=dict(checkpoint=rebound, history=rebound['state']['history']))
        packed, state = codec.encode(record, fresh_prefix)
        restored, restored_state = codec.decode(packed, fresh_prefix)
        api.require(api.digest(record) == api.digest(restored) and state == restored_state,
                    'Original literal full-history codec roundtrip for each rebound diagnostic contract')
        seed_checks.append(dict(branch=index, factor=cases[index]['factor'], full_checkpoint_sha256=api.digest(rebound),
                                same_full_physical_state_history=True, literal_initial_history_roundtrip=True))
    for path in DESIGN.rglob('*'):
        if path.is_file():
            inputs[str(path)] = s.sha(path)
    sources = {**prior['source_files'], **frozen_preparation_sources}
    for module in list(sys.modules.values()):
        file = getattr(module, '__file__', None)
        if file and Path(file).suffix == '.py' and ROOT in Path(file).resolve().parents and Path(file).is_file():
            path, actual = str(Path(file).resolve()), s.sha(file)
            api.require(path not in sources or sources[path] == actual, 'Existing frozen source binding cannot be replaced')
            sources[path] = actual
    api.verify_mapping(sources); api.verify_mapping(inputs)
    old_ledger = closed['ledger']
    local_ledger = local_closed['ledger']
    newest_ledger = latest_closed['ledger']
    api.require(newest_ledger['ledger_authenticated'] and not newest_ledger['admission_failures']
                and newest_ledger['known_unaccepted_saved_steps'] == newest_ledger['unknown_reserved_steps_upper_bound'] == 0
                and (newest_ledger['accepted_diagnostic_steps'], newest_ledger['conservative_call_charges']) == (49275,17),
                'Latest closed local work has exact charges and no unresolved reservation')
    api.require(local_ledger['ledger_authenticated'] and not local_ledger['admission_failures']
                and local_ledger['known_unaccepted_saved_steps'] == 0
                and local_ledger['unknown_reserved_steps_upper_bound'] == 0
                and (local_ledger['accepted_diagnostic_steps'], local_ledger['conservative_call_charges']) == (49275,17),
                'All previous diagnostic work charged; no unresolved reservation')
    saved = prior['baseline']['conservative_prospective_baseline_saved_steps'] + old_ledger['saved_steps'] + local_ledger['accepted_diagnostic_steps'] + newest_ledger['accepted_diagnostic_steps']
    calls = prior['baseline']['conservative_prospective_baseline_integration_calls'] + old_ledger['calls'] + local_ledger['conservative_call_charges'] + newest_ledger['conservative_call_charges']
    shared_saved = old_ledger['saved_steps'] + local_ledger['accepted_diagnostic_steps'] + newest_ledger['accepted_diagnostic_steps']
    shared_calls = old_ledger['calls'] + local_ledger['conservative_call_charges'] + newest_ledger['conservative_call_charges']
    diag_saved = old_ledger['diagnostic_steps'] + local_ledger['accepted_diagnostic_steps'] + newest_ledger['accepted_diagnostic_steps']
    diag_calls = old_ledger['diagnostic_calls'] + local_ledger['conservative_call_charges'] + newest_ledger['conservative_call_charges']
    api.require((saved,calls,shared_saved,shared_calls,diag_saved,diag_calls) == (10283231,2159,4635319,989,116534,51),
                'Current case/shared/diagnostic conservative all-attempt baseline')
    allocation = dict(old_frozen_diagnostic_step_cap=119283, old_frozen_diagnostic_call_cap=51,
        already_used_diagnostic_steps=diag_saved, already_used_diagnostic_calls=diag_calls,
        requested_revised_total_diagnostic_step_allocation=147442,
        requested_revised_total_diagnostic_call_allocation=68,
        required_step_allocation_increase=28159, required_call_allocation_increase=17,
        old_frozen_documents_unchanged=True,
        supplemental_allocation_and_dispatch_require_prospective_explicit_permission_record=True)
    proposal = dict(schema='paper1.first-activation-common-state.proposal.v1', passed=True,
        status='PREPARED_AWAITING_EXPLICIT_HUMAN_APPROVAL', dispatch_authorized=False,
        guarded_runtime_path=str(Path(runtime.__file__).resolve()), guarded_runtime_source_sha256=s.sha(runtime.__file__),
        guarded_runtime_controls=runtime_controls,
        preparation_launch_path=str(PREPARATION_LAUNCH), preparation_launch_sha256=s.sha(PREPARATION_LAUNCH),
        preparation_source_sha256=frozen_preparation_sources[str(SELF)],
        preparation_execution_receipt_required_before_authorization=True,
        required_human_approval_scope=runtime.approval_scope(),
        numerical_window_accounting=dict(prior_executed_numerical_windows=4,
            new_independent_window_ordinal=5, old_scheduler_window003_remains_nondispatched=True,
            not_a_continuation_or_reopening_of_a_closed_window=True),
        question='Does the first contact-activation error episode regenerate over2.5ms when both original factors start from the identical FULL physical state/history?',
        selection_rule='Last actual accepted finer production boundary before the first saved contiguous >.005 six-component discrepancy episode lasting at least1ms; fixed2.5ms duration covers that complete archived episode plus approximately0.634ms tail. Duration labels are descriptive, never accuracy gates; no later seed or future local outcome is used.',
        logical_core_id=failed['logical_core_id'], source_level='f0p03125', source_last_record=SOURCE_LAST,
        seed_time_s=start, local_stop_s=stop, local_duration_s=DURATION_S, factors=[.0625, .03125],
        seed_checks=seed_checks, original_numerical_controller=physical['numerical_controller'],
        original_accuracy_gates=failed['original_gate_values'],
        budget=budget(saved, calls, shared_saved, shared_calls), diagnostic_suballocation=allocation,
        maximum_window_minutes=60, requested_numerical_interval_minutes=30, requested_postnumerical_retirement_audit_minutes=30,
        authorization_start_utc=None, authorization_end_utc=None, original_shared_end_utc=DEADLINE,
        deadline_rule='After new explicit human approval of this frozen proposal and supplemental allocation, stop numerical work no later than min(approval+30min, original_shared_end-30min), retire/authenticate by min(approval+60min, original_shared_end). No clock reset or automatic extension.',
        workers=1, threads=1, logical_cpu=14, maximum_unverified_records=1, steps_per_record=5000,
        native_seconds_per_record=45, maximum_new_output_bytes=256 * 1024**2,
        unchanged_total_retention_bytes=20 * 1024**3, unchanged_free_reserve_bytes=20 * 1024**3,
        qualification='Before either branch, serial256 versus128+128 exact original rows and FULL checkpoint/history; discard512steps and reset the SAME original common seed. Initial-trigger or pending-trigger witness stops. At the FIRST actual accepted local trigger record, freeze its actual N<=4096,input FULL checkpoint/prefix/ancestry and first accepted trigger index j>0. Pause dependent local dispatch. Replay serialN versusj+(N-j),require exact ORIGINAL accepted rows and FULL checkpoint/history, actual trigger in split successor and no output pending trial. Charge/discard all2Nsteps and3calls. Restore the original accepted output/prefix only after this qualification passes. No later easier record or implicit waiver. Each branch must exercise and qualify the target event before any local pass.',
        prospective_selector_activation_policy=runtime.activation_protocol(),
        acceptance='Each future record must pass the unchanged independent physical auditor, fixed-selector audit and lossless raw reconstruction before any successor record. Failed/censored/unknown work is retained and counted.',
        analysis='Use original held-velocity/unshifted absolute clock and unchanged full-six-component meanL1/endpoint and pose/event thresholds over the declared2.5ms local interval; retain component norms as nonadditive diagnostics. Label all results local-only.',
        method_decision=dict(transport_contact_equation_change_justified=False,
            current_algorithm_and_selector_retained=True,
            selector_chatter_repair_rejected='Both archived paths have one contiguous activation burst; closing is about1.014U, far above.005U threshold.',
            next_discriminator='Remove inherited FULL-state differences before the FIRST active episode, rather than resetting after it.',
            event_registration_is_diagnostic_only=True, geometric_or_reaction_event_alignment_authorized=False,
            root_clipped_or_hysteretic_candidate_implemented=False, gap_snapping_or_impact_reset_authorized=False),
        full_horizon_feasibility=dict(qualified_case_count=1,
            remaining_shared_saved_steps_before=997449, remaining_shared_calls_before=228,
            observed_single_complete_f0p0625_production_steps=1506345,
            observed_single_complete_f0p0625_production_calls=313,
            even_one_repeat_step_shortfall_before_diagnostics=508896,
            even_one_repeat_call_shortfall_before_diagnostics=85,
            full_repair_or_publication_completion_demonstrated=False),
        inference_limits=['Two factors cannot establish first-order convergence or any convergence order.',
            'Local pass shows this selected pre-activation FULL state does not regenerate failed local metrics over2.5ms; it identifies no sole inherited component or whole-path cause.',
            'Local failure shows independent-prefix differences are not necessary for local failure, but does not establish which refinement is accurate.',
            'The first accepted actual trigger and its matching original-row/FULL-state replay are mandatory; selector activation is not identical to geometric touching or first positive reaction.',
            'A pass cannot admit the original full horizon, select or tune a timestep cap, qualify a publication case or authorize a successor case.'],
        selection_saved_analysis_sha256=EXPECTED[str(DIVERGENCE)],
        exact_archived_window_context_sha256=EXPECTED[str(CONTEXT)],
        archived_window_metrics=context['metrics'],
        archived_profile_artifacts=context['artifacts'],
        archived_same_window_has_no_new_admission_decision=True,
        earlier_first1ms_episode_retained=divergence['diagnosis']['first_duration_qualified_episodes']['0.001'],
        selected_first1ms_episode=episode,
        physics_changes=[], accuracy_gate_changes=[], contact_route_changes=[], selector_policy_changes=[],
        full_path_accuracy_promotion_authorized=False, original_full_path_admission=False, successor_dispatch_authorized=False,
        new_transport_steps=0, new_native_solver_calls=0, physical_auditor_replays=0,
        controls=pure, source_files=sources, physical_inputs=inputs, utc=s.utc())
    api.verify_mapping(frozen_preparation_sources)
    bound(8 * 1024**2)
    s.commit(PROPOSAL, proposal)
    s.seal(DESIGN / 'preparation_01', dict(passed=True, dispatch_authorized=False, proposal_sha256=s.sha(PROPOSAL),
        physical_design_sha256=s.sha(PHYSICAL), source_files=sources, physical_inputs=inputs,
        pure_controls=pure, guarded_runtime_controls=runtime_controls, seed_checks=seed_checks,
        preparation_launch_path=str(PREPARATION_LAUNCH), preparation_launch_sha256=s.sha(PREPARATION_LAUNCH),
        preparation_execution_receipt_required_before_authorization=True,
        new_transport_steps=0, new_native_solver_calls=0,
        original_shared_end_utc=DEADLINE, authority_timestamps_written=False, numerical_worker_launched=False, utc=s.utc()))
    print(json.dumps(dict(passed=True, dispatch_authorized=False, source_sha256=s.sha(SELF), proposal_sha256=s.sha(PROPOSAL),
        preparation_sha256=s.sha(DESIGN / 'preparation_01/results.json'), seed_time_s=start, local_stop_s=stop,
        maximum_new_saved_steps=NEW_STEPS, maximum_new_calls=NEW_CALLS, new_transport_steps=0), sort_keys=True), flush=True)


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) == 2 else None
    if command == 'controls':
        print(json.dumps(controls(), sort_keys=True), flush=True)
    elif command == 'prepare':
        prepare()
    else:
        raise SystemExit('Only controls or prepare; numerical dispatch is deliberately absent.')
