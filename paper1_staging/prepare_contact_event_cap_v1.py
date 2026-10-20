"""Source/mock preparation of an INACTIVE precontact-cap experiment.

No model graph is imported, warmed, advanced or mechanically replayed here.
The old closed negative, its accounting and its accepted boundary are retained.
This creates neither a numerical design/authority nor a ready-to-launch claim.
"""
from pathlib import Path
import argparse
import ast
import copy
from dataclasses import asdict
import hashlib
import importlib.util
import json
import lzma
import os
import re
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT/'paper1_staging'
FAMILY = ROOT/'paper1_designs/contact_event_cap_20261019'
OUT = ROOT/'paper1_runs/full_horizon_repair_20261018_recovery04'
DRIVER_SHA = '05447c49e219dfff6849f6b2c543037b894feaafa71be184db5f44133e69cf69'
CLOSURE_SHA = '6251eed02f4b3e5c3c4290f28f81cfd97edb364e2fc646866bc2234964045d25'
SCREEN_SHA = '773329c555b83c8fb96e3d265cff9d1b216dc66056ce9cf8b3fd0211314d1eab'
END = '2026-10-24T07:43:33.769535+00:00'
SOURCES = ('contact_event_cap_v1.py', 'check_contact_event_cap_v1.py',
           'full_state_integration_adapter_v4.py', 'check_full_state_integration_adapter_v4.py',
           'audit_full_state_stepdoubling_v3.py', 'check_stepdoubling_audit_v3.py')
CONTROLS = ('check_contact_event_cap_v1.py', 'check_full_state_integration_adapter_v4.py',
            'check_stepdoubling_audit_v3.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_administration():
    path = STAGING/'run_stepdoubling_qualification_v4.py'
    assert sha(path) == DRIVER_SHA
    spec = importlib.util.spec_from_file_location('_inactive_event_cap_preparation_admin', path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


def original_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def definitions(path):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    answer = {}
    for item in tree.body:
        if isinstance(item, ast.FunctionDef):
            answer[item.name] = ast.dump(item, include_attributes=False)
        elif isinstance(item, ast.ClassDef):
            for child in item.body:
                if isinstance(child, ast.FunctionDef):
                    answer[item.name+'.'+child.name] = ast.dump(child, include_attributes=False)
    return answer


def diagnostic_contract(spec, binding, originals):
    """Execute ONLY two pinned pure contract functions, never their imports."""
    path = ROOT/'stage116_staging/evaluate_short_matrix_v1.py'
    rigid = ROOT/'stage151_staging/rigid_rotation_v1.py'
    for source in (path, rigid):
        if sha(source) != originals[str(source)]:
            raise ValueError('Pinned original contract expression changed')
    namespace = dict(api=SimpleNamespace(digest=original_digest), MODE='rigid_euler_old_gyro_v1')
    for source, name in ((path, 'expected_contract'), (rigid, 'binding_for')):
        fn = next(item for item in ast.parse(source.read_text()).body
                  if isinstance(item, ast.FunctionDef) and item.name == name)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source)+'::PURE_CONTRACT_ONLY', 'exec'), namespace)
    return namespace['expected_contract'](spec, namespace['binding_for'](binding, True))


def discarded_seed(adapter, source_checkpoint, spec, binding, limits, original_sources):
    """New diagnostic controller; exact inherited physical state, ZERO prefix credit.

    This is a prospective input recipe. Source/mock identity does not qualify a
    new physical step, authorize dispatch or resume any closed stage.
    """
    full = copy.deepcopy(source_checkpoint['physical_checkpoint'])
    full['contract'] = diagnostic_contract(spec, binding, original_sources)
    if full['state'] != source_checkpoint['physical_checkpoint']['state']:
        raise ValueError('No physical state/history alteration during diagnostic contract rebinding')
    if original_digest(full['state']) != full['state_sha256']:
        raise ValueError('Literal inherited physical state integrity')
    full_sha = original_digest(full)
    store = adapter.HistoryStore(full['state']['history'])
    history = store.start(full_sha)
    state = {k: copy.deepcopy(v) for k,v in full['state'].items() if k != 'history'}
    state.update(history_node=history.node, history_length=len(full['state']['history']))
    parent = adapter.token(dict(kind='packet-boundary-original-FULL', sha256=full_sha))
    identity = adapter.state_token(parent, state, [])
    frame = dict(token=identity, parent=parent, state=state, history_delta=[], contract=full['contract'])
    cursor = dict(phase='idle', macro_index=0, trial_index=0, origin_state_token=identity, h_s=None,
        original_selected_cap_s=None, macro_initial_cap_s=None, event_cap_witness=None,
        depth=0, branch_ids=[], decision=None, published_half_count=0, pending_branch_id=None)
    return dict(schema=adapter.CHECKPOINT_SCHEMA, physical_checkpoint=full, published_state_token=identity,
        adapter_source_sha256=sha(adapter.__file__), limits_sha256=adapter.token(asdict(limits)),
        event_policy_sha256=adapter.EVENT_POLICY_SHA256, event_source_sha256=adapter.EVENT_SOURCE_SHA256,
        policy_sha256=limits.numerical_binding, spec_sha256=original_digest(spec), physical_binding=binding,
        history_root=store.descriptor, staged_history_nodes={}, frames={identity:frame}, cursor=cursor,
        numeric_ledger=dict(all_work_rows=0, accepted_half_rows=0, rejected_trials=0), pending_branches=[])


def prepare_seed_inputs(run, source_checkpoint, originals, pins):
    """Prospective common-state inputs only; no actor/design/AUTH is created."""
    sys.path.insert(0, str(STAGING))
    import full_state_integration_adapter_v4 as adapter
    import full_state_stepdoubling_v1 as kernel
    physical_path = ROOT/'paper1_designs/full_horizon_repair_20261018/physical_cases_qualification_01.json'
    proposal_path = ROOT/'paper1_designs/full_horizon_repair_20261018/qualification_proposal_01.json'
    for path in (physical_path, proposal_path):
        run.need(sha(path) == originals[str(path)], 'original physical/limit source remains pinned')
    old = json.loads(physical_path.read_text())
    proposal = json.loads(proposal_path.read_text())
    original_case = next(item for item in old['cases'] if item['level_id'] == 'f0p0625')
    run.need(diagnostic_contract(original_case['spec'], original_case['binding'], originals)
             == source_checkpoint['physical_checkpoint']['contract'],
             'pure original contract recipe exactly reproduces the authenticated source FULL contract')
    start = source_checkpoint['physical_checkpoint']['state']['t']
    end = start+.0004
    cases = copy.deepcopy(old['cases'])
    for case in cases:
        case['id'] = case['id']+'__discarded_event_cap_local'
        case['role'] = 'prospective_discarded_common_state_falsifier_not_core_qualification'
        case['spec']['case_id'] = case['id']
        case['spec']['horizon_s'] = end
        case.pop('binding', None)
    physical = dict(schema='paper1.prospective-common-state-event-cap-inputs.v1',
        purpose='Discarded local falsifier only; no full-path/prefix credit or dispatch authority',
        source_physical_design_sha256=sha(physical_path), source_limits_proposal_sha256=sha(proposal_path),
        common_start_time_s=start, common_end_time_s=end, duration_s=.0004,
        original_publication_exposure_s=.9364396280429768,
        source_original_FULL_sha256=original_digest(source_checkpoint['physical_checkpoint']),
        source_original_FULL_state_sha256=source_checkpoint['physical_checkpoint']['state_sha256'],
        cases=cases, physics_changes=[], original_accuracy_gate_changes=[],
        no_old_controller_or_failed_packet_promotion=True, dispatch_authorized=False)
    physical['binding'] = original_digest(physical)
    for case in cases:
        case['binding'] = original_digest([physical['binding'], case['id']])
    physical_sha = original_digest(physical)
    limits_by_level = {item['level_id']:item['limits'] for item in proposal['levels']}
    seeds, summaries = {}, []
    for case in cases:
        level = case['level_id']
        numerical = adapter.token(dict(purpose='inactive-discarded-common-state-event-cap-input',
            physical_sha256=physical_sha, level_id=level, source_pins=pins,
            event_policy_sha256=adapter.EVENT_POLICY_SHA256))
        values = dict(limits_by_level[level]); values['numerical_binding'] = numerical
        limits = kernel.Limits(**values); limits.validate()
        seed = discarded_seed(adapter, source_checkpoint, case['spec'], case['binding'], limits, originals)
        run.need(seed['physical_checkpoint']['state'] == source_checkpoint['physical_checkpoint']['state']
                 and seed['numeric_ledger'] == dict(all_work_rows=0, accepted_half_rows=0, rejected_trials=0)
                 and seed['history_root']['history_length'] == 1972,
                 'same literal physical state/history; no old controller or new work credit')
        adapter.validate_outer_checkpoint_admission(seed, numerical, sha(adapter.__file__))
        identity = seed['published_state_token']; frame = seed['frames'][identity]
        run.need(identity == adapter.state_token(frame['parent'], frame['state'], [])
                 and frame['state']['history_node'] == adapter.token(seed['history_root'])
                 and frame['state']['history_length'] == 1972, 'pure exact new-controller ancestry')
        store = adapter.HistoryStore(seed['physical_checkpoint']['state']['history'], seed['history_root'])
        history = store.start(original_digest(seed['physical_checkpoint']))
        run.need(store.materialize(history.node) == source_checkpoint['physical_checkpoint']['state']['history'],
                 'literal full inherited history remains exact after new root construction')
        data = dict(schema='paper1.inactive-discarded-common-state-input.v1', case=case, limits=asdict(limits),
            checkpoint=seed, physical_input_digest=physical_sha, source_pins=pins,
            source_original_FULL_sha256=physical['source_original_FULL_sha256'],
            dispatch_authorized=False, full_horizon_qualification_claimed=False,
            source_mock_input_preparation_only=True)
        encoded = (json.dumps(data, sort_keys=True, indent=2, allow_nan=True)+'\n').encode()
        compressed = lzma.compress(encoded)
        run.need(lzma.decompress(compressed) == encoded, 'exact prospective input compression roundtrip')
        seeds[level] = compressed
        summaries.append(dict(level_id=level, factor=case['factor'],
            source_state_sha256=seed['physical_checkpoint']['state_sha256'],
            prospective_original_FULL_sha256=original_digest(seed['physical_checkpoint']),
            prospective_controller_sha256=adapter.token(seed), limits=asdict(limits),
            new_integration_work_rows=0, full_history_rows=1972, compression_roundtrip_exact=True))
    run.need(len(summaries) == 3 and len({item['source_state_sha256'] for item in summaries}) == 1,
             'ALL three original factors use exactly the SAME inherited FULL physical state/history')
    return physical, seeds, summaries


def invariants(run):
    adapter_old = definitions(STAGING/'full_state_integration_adapter_v3.py')
    adapter_new = definitions(STAGING/'full_state_integration_adapter_v4.py')
    audit_old = definitions(STAGING/'audit_full_state_stepdoubling_v2.py')
    audit_new = definitions(STAGING/'audit_full_state_stepdoubling_v3.py')
    unchanged = {}
    for old, new, names, label in (
        (adapter_old, adapter_new, ('Runtime.select_dt', 'Runtime._branch', 'compile_machine',
                                    'decision_values'), 'original_substep_and_accuracy'),
        (audit_old, audit_new, ('audit_branch_caps', 'audit_compact_branch_caps',
                               'independent_decision', 'independent_trial_decision',
                               'audit_history_delta', 'audit_original_smoke_record'),
         'independent_mechanics_caps_accuracy_and_history')):
        for name in names:
            run.need(name in old and old.get(name) == new.get(name),
                     'literal original function AST retained: '+name)
        unchanged[label] = list(names)
    return unchanged


def main(pins_path, pins_sha):
    run = load_administration()
    run.environment()
    destination = FAMILY/'source_preparation_01'
    run.need(not destination.exists(), 'single create-only source preparation')
    run.need(run.instant(run.utc()) < run.instant(END), 'original absolute end is not reset')
    pins_path = Path(pins_path).resolve()
    run.need(sha(pins_path) == pins_sha, 'caller-pinned exact source inventory')
    pins = json.loads(pins_path.read_text())
    expected_paths = {str((STAGING/name).resolve()) for name in SOURCES}
    run.need(set(pins) == expected_paths, 'only explicit candidate and source/mock controls')
    run.verify_mapping(pins)
    own = {str(Path(__file__).resolve()): sha(__file__), str(pins_path): pins_sha,
           str(STAGING/'run_stepdoubling_qualification_v4.py'): DRIVER_SHA}
    closure_path = OUT/'final_execution_receipt_01/results.json'
    run.need(sha(closure_path) == CLOSURE_SHA, 'retired closed negative prerequisite')
    closed = run.sealed(closure_path, positive=True)
    run.need(closed['closure_complete'] and not closed['qualified'], 'never turn closure into qualification')
    identities = [row['launch'] for row in closed['exact_retirement_after']]
    before = run.assert_retired(identities)
    old_maps = run.merge_maps(closed['source_files'], closed['physical_inputs'],
                             closed['evidence_files'], closed['historical_evidence_files'],
                             closed['artifacts'])
    run.verify_mapping(old_maps)
    screen_path = FAMILY/'saved_screen_01/results.json'
    run.need(sha(screen_path) == SCREEN_SHA, 'fixed earlier saved-data decision')
    screen = run.sealed(screen_path, positive=True)
    run.need(screen['new_force_calls'] == screen['new_transport_steps'] == 0
             and not screen['dispatch_authorized'], 'pure screen is no execution authority')
    own[str(screen_path)] = SCREEN_SHA
    own[str(screen_path.with_name('completion.json'))] = sha(screen_path.with_name('completion.json'))
    seed_path = OUT/'levels/f0p0625/last_sealed_partial_01/controller_checkpoint.json.xz'
    seed = json.loads(lzma.decompress(seed_path.read_bytes()))
    checkpoint = seed['checkpoint']; physical = checkpoint['physical_checkpoint']
    run.need(original_digest(physical) == seed['original_FULL_sha256']
             == '878a8a639226c2091632cfe5986abf310f918f50ffdea8da2ddb99cd7aea6fe4',
             'exact separately preserved original FULL boundary')
    run.need(physical['state']['t'] == .15328271968165677
             and len(physical['state']['history']) == 1972
             and physical['state']['pending_trial'] is None
             and checkpoint['cursor']['phase'] == 'idle'
             and not checkpoint['pending_branches'], 'accepted seed remains idle with literal complete history')
    ast_checks = invariants(run)
    tests = []
    for name in CONTROLS:
        observed = subprocess.run([sys.executable, '-B', str(STAGING/name)], cwd=ROOT,
            env=os.environ.copy(), capture_output=True, text=True, timeout=120)
        match = re.search(r'Ran (\d+) tests', observed.stderr)
        row = dict(source=name, source_sha256=pins[str((STAGING/name).resolve())],
                   returncode=observed.returncode, stdout=observed.stdout, stderr=observed.stderr,
                   test_count=None if match is None else int(match.group(1)))
        tests.append(row)
        if observed.returncode != 0:
            print(json.dumps(row), flush=True)
        run.need(observed.returncode == 0 and row['test_count'] is not None,
                 'actual source/mock controls passed: '+name)
    physical_preview, seeds, seed_summaries = prepare_seed_inputs(run, checkpoint, old_maps, pins)
    run.verify_mapping(run.merge_maps(old_maps, pins, own))
    after = run.assert_retired(identities)
    inputs = FAMILY/'seed_inputs_01'
    run.need(not inputs.exists(), 'prospective input family is create-only, never a run directory')
    inputs.mkdir(parents=True, exist_ok=False)
    run.commit(inputs/'physical_cases_preview.json', physical_preview)
    new_inputs = {str(inputs/'physical_cases_preview.json'):sha(inputs/'physical_cases_preview.json')}
    for level, compressed in seeds.items():
        path = inputs/(level+'.json.xz')
        with path.open('xb') as stream:
            stream.write(compressed); stream.flush(); os.fsync(stream.fileno())
        run.need(path.read_bytes() == compressed, 'closed exact prospective input bytes')
        new_inputs[str(path)] = sha(path)
    body = dict(schema='paper1.inactive-event-cap.source-preparation.v1', passed=True, utc=run.utc(),
        source_files=run.merge_maps(pins, own), consumed_original_maps=old_maps,
        consumed_original_file_count=len(old_maps), closed_negative_sha256=CLOSURE_SHA,
        saved_screen_sha256=SCREEN_SHA, exact_retirement_before=before, exact_retirement_after=after,
        original_function_AST_invariants=ast_checks, actual_controls=tests,
        source_mock_test_count=sum(x['test_count'] for x in tests),
        prospective_common_state_inputs=new_inputs, prospective_seed_checks=seed_summaries,
        prospective_local_interval_s=[physical_preview['common_start_time_s'],physical_preview['common_end_time_s']],
        accepted_seed=dict(path=str(seed_path), compressed_sha256=sha(seed_path),
            original_FULL_sha256=seed['original_FULL_sha256'], time_s=physical['state']['t'],
            physical_steps=physical['state']['steps'], literal_history_rows=1972,
            existing_ancestry=seed['raw_six_field_prefix'],
            only_new_discarded_diagnostic_contracts_prepared=True, new_core_prefix_credit=False),
        minimum_step_and_momentum_conditioning_are_unqualified_native_risks=True,
        scalar_proxy_is_not_generalized_velocity_error_bound=True,
        fresh_coupled_test_is_required_before_any_full_horizon_admission=True,
        qualified_core_cases=1, required_core_cases=12, numerical_dataset_complete=False,
        new_force_calls=0, new_transport_steps=0, new_integration_records=0,
        native_physical_or_restart_qualification_completed=False, full_horizon_accuracy_repaired=False,
        numerical_launch_ready=False, dispatch_authorized=False, execution_authority_created=False,
        new_clock_created=False, original_absolute_end_utc=END,
        old_unknown_reserved_work_rows=4838, old_known_unaccepted_work_rows=1728,
        old_all_attempts_work_rows=752798, old_all_attempts_integration_records=186,
        remaining_original_grant_work_rows=17247202, remaining_original_grant_integration_records=3814,
        original_physics_gap_routes_accuracy_restart_full_history_gates_unchanged=True)
    run.seal(destination, body)
    print('INACTIVE_EVENT_CAP_SOURCE_PREPARATION', run.sha(destination/'results.json'), flush=True)


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('source_pins_path'); cli.add_argument('source_pins_sha256')
    args = cli.parse_args(); main(args.source_pins_path, args.source_pins_sha256)
