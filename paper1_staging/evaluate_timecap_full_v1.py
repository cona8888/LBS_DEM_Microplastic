"""Post-worker full-path evidence replay for the fixed onset timecap.

No integration, contact solve, authorization or numerical dispatch is exposed.
Original physics, observation, path metrics and pair gates remain unchanged.
The administrative owner may be live; every numerical producer must be retired.
"""
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import copy
import numpy as np

import run_core_v2 as shared
import compare_core_v2 as comparator
import audit_onset_timecap_v1 as policy_auditor
import contact_onset_timecap_v1 as selector

s, api = shared.s, shared.s.api
SELF = Path(__file__).resolve()
SOURCE_FILES = {str(path.resolve()): s.sha(path) for path in (
    SELF, Path(shared.__file__), Path(comparator.__file__),
    Path(policy_auditor.__file__), Path(selector.__file__),
    Path(s.q.job.path_metrics.metrics.__code__.co_filename),
    Path(s.q.job.policy.pair_gates.__code__.co_filename))}


def require(value, message):
    api.require(value, 'Full timecap evidence audit: ' + message)


def _bind(path, artifacts):
    path = Path(path).resolve()
    require(path.is_file(), 'existing evidence file ' + str(path))
    artifacts[str(path)] = s.sha(path)


def _document(path, docs, physical_sha, artifacts):
    path = Path(path)
    value = docs.read(path)
    _bind(path, artifacts)
    reference = s.read(path)
    if isinstance(reference, dict) and reference.get('format') == shared.documents.FORMAT:
        payload = path.with_name(path.stem + '.payload.json.xz')
        require(Path(reference['payload']).resolve() == payload.resolve()
                and reference['design_sha256'] == physical_sha,
                'same-directory complete audit document and physical design')
        _bind(payload, artifacts)
        _bind(payload.with_suffix('.seal.json'), artifacts)
    return value


def _deadline(plan):
    start = datetime.fromisoformat(plan['start_utc'])
    end = datetime.fromisoformat(plan['end_utc'])
    require(start.tzinfo is not None and end.tzinfo is not None
            and 0 < (end - start).total_seconds() <= 36 * 3600,
            'bounded shared absolute window')
    require(datetime.now(timezone.utc) < end,
            'complete full replay before the shared absolute deadline')


def _context(plan, plan_path, physical_path):
    # Original context construction only. No original closed twelve-hour bound
    # is consulted or reopened by this read-only post-exit auditor.
    def bound():
        _deadline(plan)
        return plan
    def no_write(*args, **kwargs):
        raise RuntimeError('Full evidence replay cannot write a numerical record')
    def verify_inputs(value):
        bound()
        api.verify_mapping(value['source_files'])
        api.verify_mapping(value['physical_inputs'])
    admin = SimpleNamespace(bound=bound, commit=no_write, sha=s.sha, utc=s.utc)
    result = s.context.build(plan_path, Path(plan_path).with_name('authorization_01.json'),
                             physical_path, admin, verify_inputs)
    result.job.codec = shared.archives.build(result.job.codec, preset=9)
    return result


def _reservation_inventory(level, native, artifacts):
    production = native['production_labels']
    diagnostics = native['diagnostic_labels']
    require(production and production == [f'production_{i:05d}'
            for i in range(1, len(production) + 1)],
            'complete contiguous fresh production labels')
    labels = production + diagnostics
    require(len(labels) == len(set(labels)) and all(isinstance(x, str)
            and Path(x).name == x for x in labels), 'unique safe integration labels')
    paths = list((level / 'reservations').glob('*.json'))
    require({x.stem for x in paths} == set(labels)
            and {x.name for x in (level / 'records').iterdir() if x.is_dir()} == set(labels),
            'every integration record and reservation is accounted for')
    result = {}
    for path in paths:
        row = s.read(path)
        label = path.stem
        require(row['label'] == label and row['level_id'] == level.name
                and type(row['maximum_saved_steps']) is int
                and 0 < row['maximum_saved_steps'] <= 5000
                and type(row['global_index']) is int and row['global_index'] > 0,
                'exact bounded reservation identity')
        require((row['kind'] == 'production') == (label in production),
                'production and discarded diagnostic roles remain distinct')
        _bind(path, artifacts)
        result[label] = row
    indices = [x['global_index'] for x in result.values()]
    require(len(indices) == len(set(indices)), 'no duplicated global integration reservation')
    return result


def _admissions(root):
    result = {}
    for path in (root / 'admissions').glob('*/results.json'):
        try:
            index = int(path.parent.name)
        except ValueError as exc:
            raise RuntimeError('Non-numeric global admission index') from exc
        require(index not in result, 'unique global admission directory')
        result[index] = path
    return result


def _global_reservations(root):
    result = {}
    for path in (root / 'reservations').glob('*.json'):
        row = s.read(path)
        index = row['global_index']
        require(type(index) is int and index > 0 and index not in result,
                'unique global reservation identity')
        result[index] = path
    return result


def authenticate(level_dir, case, plan_path, physical_path, shared_config):
    """Seal a complete fresh path and return original-comparator input fields.

    This is per-level evidence qualification only. Original pair gates must
    subsequently pass; this function never grants publication-case admission.
    """
    level, plan_path, physical_path = [Path(x).resolve()
                                      for x in (level_dir, plan_path, physical_path)]
    root = level.parent.parent
    destination = level / 'full_audit_01'
    require(level.parent.name == 'levels' and not destination.exists(),
            'create-only full audit in the declared level directory')
    plan, physical = s.read(plan_path), s.read(physical_path)
    _deadline(plan)
    require(plan['binding'] == api.digest({k: v for k, v in plan.items() if k != 'binding'})
            and plan['physical_design_sha256'] == s.sha(physical_path),
            'exact frozen shared numerical and physical designs')
    authorization = plan_path.with_name('authorization_01.json')
    require(plan['authorization_sha256'] == s.sha(authorization),
            'shared authority remains immutable')
    require(len(physical['cases']) == 3 and sum(x == case for x in physical['cases']) == 1,
            'one exact case in the three-level physical design')
    require(type(shared_config.get('enabled')) is bool and shared_config['enabled']
            and api.digest(shared_config['policy']) == api.digest(policy_auditor.FROZEN_POLICY),
            'unchanged enabled selector16')
    api.verify_mapping(SOURCE_FILES)
    api.verify_mapping(plan['source_files'])
    api.verify_mapping(plan['physical_inputs'])
    for path, digest in SOURCE_FILES.items():
        require(plan['source_files'].get(path) == digest, 'evaluator dependencies frozen before dispatch')
    physical_sha, plan_sha = s.sha(physical_path), s.sha(plan_path)
    native_path = level / 'native_completion_01/results.json'
    native = s.fields.sealed(native_path)
    require(native['passed'] and native['native_complete']
            and native['known_unaccepted_saved_steps'] == native['unknown_reserved_steps_upper_bound'] == 0,
            'native complete with no hidden failed or unknown work')
    require(native['design_sha256'] == plan_sha and native['case_id'] == case['id']
            and native['level_id'] == level.name,
            'native completion binds this shared design and exact level')
    artifacts = {}
    for path in (plan_path, authorization, physical_path, native_path,
                 native_path.with_name('completion.json')):
        _bind(path, artifacts)
    inventory = _reservation_inventory(level, native, artifacts)
    admission_paths = _admissions(root)
    global_reservations = _global_reservations(root)
    for label, reservation in inventory.items():
        global_path = global_reservations.get(reservation['global_index'])
        local_path = level / 'reservations' / (label + '.json')
        require(global_path is not None and s.sha(global_path) == s.sha(local_path),
                'global and level reservation documents are byte-identical')
        _bind(global_path, artifacts)
    needed = {(inventory[label]['input_checkpoint_sha256'],
               inventory[label]['previous_result_sha256']) for label in native['diagnostic_labels']}
    codec = shared.archives.build(s.q.job.codec, preset=9)
    docs = shared.documents.build(s.q.job.codec, api)
    ctx = _context(plan, plan_path, physical_path)
    geometry = ctx.geometry_for(case)
    checkpoints = {(api.digest(None), None): (None, None)}
    identities, receipts, traces = {}, {}, []
    previous = prefix = before = terminal = None
    production_steps = diagnostic_steps = trigger_count = tightened = 0
    diagnostic_records = {}
    first_trigger = None

    def verify_record(label, seed, history_prefix, previous_sha, production):
        _deadline(plan)
        reservation = inventory[label]
        folder = level / 'records' / label
        require(reservation['input_checkpoint_sha256'] == api.digest(seed)
                and reservation['previous_result_sha256'] == previous_sha,
                'reservation and complete raw predecessor association')
        gate_path = folder / 'guard_completion/results.json'
        cap_path = folder / 'timecap_guard/results.json'
        gate, cap_gate = s.fields.sealed(gate_path), s.fields.sealed(cap_path)
        require(gate['passed'] and cap_gate['passed'], 'both original and supplemental gates passed')
        api.verify_mapping(gate['artifacts'])
        wire_complete = s.read(folder / 'completion.json')
        require(wire_complete['results_sha256'] == s.sha(folder / 'results.json'),
                'complete original audit document seal')
        receipt = _document(folder / 'results.json', docs, physical_sha, artifacts)
        require(receipt['passed'] and receipt['summary']['passed'],
                'unchanged original independent physics receipt')
        require(receipt['transport_design_sha256'] == plan_sha
                and receipt['physical_design_sha256'] == physical_sha,
                'original receipt binds the shared numerical and physical designs')
        api.verify_mapping(receipt['artifacts'])
        rec, nxt = codec.read_record(folder / 'call.json.xz', physical_sha, history_prefix)
        require(rec['spec'] == case['spec'] and rec['input_checkpoint_sha256'] == api.digest(seed),
                'exact original full-state/raw ancestry')
        count = len(rec['rows'])
        checkpoint = rec['result']['checkpoint']
        require(0 < count <= reservation['maximum_saved_steps'] == rec['step_cap'],
                'positive original bounded saved increment')
        accounting = s.read(folder / 'accounting.json')
        require(accounting['saved_steps_known'] and accounting['saved_steps'] == count
                and accounting['raw_sha256'] == s.sha(folder / 'call.json.xz'),
                'exact nonmissing native work accounting')
        n0 = 0 if seed is None else seed['state']['steps']
        t0 = 0. if seed is None else seed['state']['t']
        require(checkpoint['state']['steps'] == n0 + count
                and receipt['summary']['start_s'] == t0
                and receipt['summary']['stop_s'] == checkpoint['state']['t']
                and receipt['input_checkpoint_sha256'] == api.digest(seed)
                and receipt['previous_receipt_sha256'] == previous_sha
                and receipt['output_checkpoint_sha256'] == api.digest(checkpoint)
                and gate['full_checkpoint_sha256'] == api.digest(checkpoint)
                and gate['saved_steps'] == count,
                'exact complete checkpoint, clock, step and original receipt links')
        require(cap_gate['raw_sha256'] == s.sha(folder / 'call.json.xz')
                and cap_gate['original_physical_guard_sha256'] == s.sha(gate_path),
                'supplemental policy gate bound to original raw/physics gate')
        # These are original audit functions: geometry/force/clearance replay,
        # never a forward force solve or integration call.
        physical_check = ctx.baseline.kernel(rec, case['spec'], ctx.job.binding(physical, case),
                                             seed, geometry, physical_sha,
                                             physical['minimum_gap_semantics'])
        guard_check = s.q.guard.audit(rec)
        policy_check = policy_auditor.audit(rec, seed, case, shared_config, ctx)
        require(physical_check['passed'] and guard_check['passed'] and policy_check['passed'],
                'independent post-exit physical and full numerical-policy replay')
        expected_trace = np.asarray([[r['time_s'], *r['position_m'], *r['orientation'],
                                     *r['velocity_generalized']] for r in rec['rows']], dtype=np.float64)
        trace_path = folder / 'trace.npy'
        saved_trace = np.load(trace_path, mmap_mode='r', allow_pickle=False)
        require(np.array_equal(expected_trace, saved_trace), 'every original raw row matches the saved trace')
        launch = s.read(folder / 'launch.json')
        require(launch['transport_design_sha256'] == plan_sha
                and launch['physical_design_sha256'] == physical_sha
                and launch['input_checkpoint_sha256'] == api.digest(seed),
                'actual numerical producer launch binds the shared design and FULL seed')
        command = launch.get('command', launch.get('argv'))
        require(isinstance(command, list) and len(command) >= 5
                and Path(command[0]).resolve() == Path(s.PYTHON).resolve()
                and command[1:3] == ['-B', '-u']
                and 'pid' in launch and 'created' in launch,
                'exact producer birth and command evidence')
        producer_source = str(Path(command[3]).resolve())
        require(s.ROOT in Path(producer_source).parents
                and plan['source_files'].get(producer_source) == s.sha(producer_source),
                'the numerical producer command names a frozen task source')
        key = (launch['pid'], launch['created'], tuple(command))
        if key not in identities:
            inspection = s.identity({**launch, 'command': command})
            require(inspection['retired'], 'each exact numerical producer is retired before replay')
            identities[key] = dict(launch_path=str(folder / 'launch.json'),
                                   launch_sha256=s.sha(folder / 'launch.json'),
                                   launch={**launch, 'command': command}, inspection=inspection)
        admission_path = admission_paths.get(reservation['global_index'])
        require(admission_path is not None, 'every reservation has a sealed global admission')
        admission = s.fields.sealed(admission_path)
        require(admission['passed'] and admission['level_id'] == level.name
                and admission['label'] == label and admission['kind'] == reservation['kind']
                and admission['saved_steps'] == count
                and admission['cap'] == reservation['maximum_saved_steps']
                and admission['full_checkpoint_sha256'] == api.digest(checkpoint)
                and admission['raw_sha256'] == s.sha(folder / 'call.json.xz')
                and admission['physical_guard_sha256'] == s.sha(gate_path)
                and admission['timecap_guard_sha256'] == s.sha(cap_path)
                and admission['reservation_sha256'] == s.sha(level / 'reservations' / (label + '.json')),
                'complete owner admission matches independent per-record evidence')
        for path in folder.rglob('*'):
            if path.is_file():
                _bind(path, artifacts)
        _bind(admission_path, artifacts)
        _bind(admission_path.with_name('completion.json'), artifacts)
        receipts[str(folder / 'results.json')] = s.sha(folder / 'results.json')
        return rec, nxt, trace_path, policy_check, guard_check

    for label in native['production_labels']:
        rec, prefix, path, policy_check, _ = verify_record(label, before, prefix, previous, True)
        terminal = rec['result']
        before = terminal['checkpoint']
        production_steps += len(rec['rows'])
        trigger_count += policy_check['trigger_count']
        tightened += policy_check['tightened_steps']
        traces.append(path)
        accepted_triggers = [i for i, witness in enumerate(
            rec['onset_timecap']['journal'][:len(rec['rows'])]) if witness['trigger_grain_ids']]
        if first_trigger is None and accepted_triggers:
            first_trigger = dict(label=label, index=accepted_triggers[0], record=copy.deepcopy(rec))
        output_key = (api.digest(before), s.sha(level / 'records' / label / 'results.json'))
        if output_key in needed:
            checkpoints[output_key] = (copy.deepcopy(before), prefix)
        previous = s.sha(level / 'records' / label / 'results.json')
    require(production_steps == native['accepted_physical_steps'] == before['state']['steps']
            and api.digest(before) == native['full_checkpoint_sha256'],
            'entire new t0-to-terminal path, no inherited or conditional prefix')
    for label in sorted(native['diagnostic_labels'], key=lambda x: inventory[x]['global_index']):
        reservation = inventory[label]
        seed_key = (reservation['input_checkpoint_sha256'], reservation['previous_result_sha256'])
        require(seed_key in checkpoints,
                'discarded diagnostic has an authenticated complete seed/history')
        seed, parent_prefix = checkpoints[seed_key]
        rec, nxt, _, _, _ = verify_record(label, seed, parent_prefix,
                                         reservation['previous_result_sha256'], False)
        diagnostic_steps += len(rec['rows'])
        diagnostic_records[label] = rec
        output_key = (api.digest(rec['result']['checkpoint']),
                      s.sha(level / 'records' / label / 'results.json'))
        if output_key in needed:
            checkpoints[output_key] = (copy.deepcopy(rec['result']['checkpoint']), nxt)
    require(diagnostic_steps == native['discarded_diagnostic_steps'],
            'all discarded native work retained in the diagnostic ledger')
    require(native['restart_receipts'] and len(native['restart_receipts']) == len(set(native['restart_receipts'])),
            'complete unique restart receipt inventory')
    require({str(Path(x).resolve()) for x in native['restart_receipts']}
            == {str(x.resolve()) for x in level.glob('restart_*/results.json')},
            'no restart receipt is omitted from native completion')
    restart_kinds = []
    used_restart_labels = set()
    for path in native['restart_receipts']:
        path = Path(path).resolve()
        require(root in path.parents and path.name == 'results.json', 'task-owned sealed restart receipt')
        restart = s.fields.sealed(path)
        require(restart['passed'] and restart['exact_rows']
                and restart['exact_full_checkpoint_history'],
                'all fresh and triggered restart qualification receipts passed')
        if 'artifacts' in restart:
            api.verify_mapping(restart['artifacts'])
            artifacts.update(restart['artifacts'])
        labels = restart['labels']
        require(set(labels) == {'serial', 'split_a', 'split_b'}
                and len(set(labels.values())) == 3
                and all(x in diagnostic_records for x in labels.values()),
                'restart receipt names three distinct discarded native records')
        require(not used_restart_labels.intersection(labels.values()),
                'different restart experiments retain distinct native work')
        used_restart_labels.update(labels.values())
        serial, left, right = [diagnostic_records[labels[k]] for k in ('serial', 'split_a', 'split_b')]
        require(serial['input_checkpoint_sha256'] == left['input_checkpoint_sha256']
                and right['input_checkpoint_sha256'] == api.digest(left['result']['checkpoint'])
                and api.digest(serial['rows']) == api.digest(left['rows'] + right['rows'])
                and api.digest(serial['result']['checkpoint']) == api.digest(right['result']['checkpoint']),
                'post-exit exact serial/split rows and FULL checkpoint/history')
        kind = restart['kind']
        restart_kinds.append(kind)
        require(kind in ('initial', 'active', 'handoff'), 'only prospectively approved restart roles')
        if kind in ('initial', 'handoff'):
            require(len(serial['rows']) == 256 and len(left['rows']) == len(right['rows']) == 128,
                    'exact prescribed256-versus128+128 restart length')
        if kind == 'initial':
            require(serial['input_checkpoint_sha256'] == api.digest(None),
                    'fresh initial restart begins at the original t0 state')
        if kind == 'active':
            require(first_trigger is not None and first_trigger['index'] > 0,
                    'first accepted trigger is present after the production record begins')
            original = first_trigger['record']
            j = first_trigger['index']
            require(restart['original_production_label'] == first_trigger['label']
                    and restart['first_trigger_index'] == j
                    and restart['triggered_successor'] is True
                    and original['result']['checkpoint']['state']['pending_trial'] is None
                    and serial['input_checkpoint_sha256'] == original['input_checkpoint_sha256']
                    and len(serial['rows']) == len(original['rows'])
                    and len(left['rows']) == j and len(right['rows']) == len(original['rows']) - j
                    and api.digest(original['rows']) == api.digest(serial['rows'])
                    and api.digest(original['result']['checkpoint']) == api.digest(serial['result']['checkpoint'])
                    and any(x['trigger_grain_ids'] for x in
                            right['onset_timecap']['journal'][:len(right['rows'])]),
                    'first actual triggered production record reproduced exactly across the split')
        _bind(path, artifacts)
        _bind(path.with_name('completion.json'), artifacts)
    require(restart_kinds.count('initial') == restart_kinds.count('active') == 1
            and restart_kinds.count('handoff') <= 2,
            'initial and first-triggered restart qualification complete; handoffs bounded')
    require('diag_smoke32' in diagnostic_records, 'fresh32-row pretrigger smoke is retained')
    require(set(diagnostic_records) == used_restart_labels | {'diag_smoke32'},
            'all and only prospectively qualified smoke/restart diagnostics are present')
    smoke = diagnostic_records['diag_smoke32']
    require(smoke['input_checkpoint_sha256'] == api.digest(None) and len(smoke['rows']) == 32
            and not any(x['trigger_grain_ids'] for x in smoke['onset_timecap']['journal']),
            'exact fresh32-row smoke precedes any selector trigger')
    baseline_names = {.125: 'p1_i0_fibre_u0p5_20261014',
                      .0625: 'p1_i0_fibre_u0p5_fine_20261014',
                      .03125: 'p1_i0_fibre_u0p5_accuracy_recovery_20261014'}
    old_root = s.ROOT / 'paper1_runs' / baseline_names[case['factor']]
    old_physical = s.ROOT / 'paper1_designs' / old_root.name / 'physical_cases_01.json'
    old_raw = old_root / 'records/production_00001/call.json.xz'
    old_retirement_path = old_root / 'retirement_01/results.json'
    old_retirement = s.fields.sealed(old_retirement_path)
    require(old_retirement['passed'] and old_retirement['artifacts'][str(old_raw)] == s.sha(old_raw),
            'unchanged retired same-factor baseline smoke oracle')
    old_record, _ = codec.read_record(old_raw, s.sha(old_physical), None)
    require(api.digest(smoke['rows']) == api.digest(old_record['rows'][:32]),
            'all fresh pretrigger smoke row bits match the original same-factor path')
    for path in (old_physical, old_raw, old_raw.with_suffix('.seal.json'), old_retirement_path,
                 old_retirement_path.with_name('completion.json')):
        _bind(path, artifacts)
    recovered_path = level / 'recoverable/checkpoint.json'
    recovered = _document(recovered_path, docs, physical_sha, artifacts)
    require(api.digest(recovered) == api.digest(before), 'standalone complete terminal checkpoint')
    prefix_path = level / 'recoverable/prefix.json'
    require(s.read(prefix_path) == prefix.reference(), 'standalone complete terminal raw-history prefix')
    _bind(prefix_path, artifacts)
    evidence = dict(status=terminal['status'], steps=production_steps, start_s=0.,
                    stop_s=before['state']['t'], rejected=terminal['rejected'], failure_markers=[],
                    pending_trial=before['state']['pending_trial'],
                    first_dwell_s=terminal['first_contact_dwell_time_s'],
                    export_verified=terminal['status'] == 'full_window_exit',
                    raw_hashes_verified=True, clock_steps_verified=True,
                    physics_verified=True, fresh_start=True)
    observation = s.q.job.policy.observation(evidence, case['spec']['horizon_s'])
    require(observation['complete_observation'], 'unchanged original full observation gate')
    _deadline(plan)
    api.verify_mapping(plan['source_files'])
    api.verify_mapping(plan['physical_inputs'])
    api.verify_mapping(SOURCE_FILES)
    api.verify_mapping(artifacts)
    body = dict(passed=True, case_id=case['id'], level_id=level.name,
                logical_core_id=plan['logical_core_id'], observation=observation,
                native_completion_sha256=s.sha(native_path), design_sha256=plan_sha,
                physical_design_sha256=physical_sha, fresh_t0=True,
                accepted_physical_steps=production_steps, discarded_diagnostic_steps=diagnostic_steps,
                known_unaccepted_saved_steps=0, unknown_reserved_steps_upper_bound=0,
                all_exact_numerical_producers_retired=True, identities=list(identities.values()),
                production_labels=native['production_labels'], diagnostic_labels=native['diagnostic_labels'],
                integration_calls=len(inventory), trigger_count=trigger_count, tightened_steps=tightened,
                full_checkpoint_sha256=api.digest(before), full_selector_policy_replayed=True,
                original_physics_and_guard_replayed=True, source_files=SOURCE_FILES,
                artifacts=artifacts, receipts=receipts, publication_case_count_increment=0,
                full_path_accuracy_passed=False, core_result_admitted=False,
                administrative_owner_may_remain_live=True, new_native_solver_calls=0,
                new_transport_steps=0, utc=s.utc())
    _deadline(plan)
    s.seal(destination, body)
    audit_path = destination / 'results.json'
    evidence_files = {str(path): s.sha(path) for path in
                      (plan_path, authorization, physical_path, native_path,
                       native_path.with_name('completion.json'), audit_path,
                       audit_path.with_name('completion.json'))}
    return dict(case=case, logical_core_id=plan['logical_core_id'], observation=observation,
                paths=traces, receipts=receipts, evidence_files=evidence_files,
                final_sha256=s.sha(native_path), retirement_sha256=s.sha(audit_path),
                retirement_receipt_type='complete-post-worker-full-evidence-replay',
                full_audit_path=str(audit_path), full_audit_sha256=s.sha(audit_path))
