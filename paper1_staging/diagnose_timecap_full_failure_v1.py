"""Create-only, posthoc localization of an already closed negative comparison.

This wrapper hashes retained evidence and uses the unchanged read-only streaming
localizer. It does not evaluate, compare, replay, audit, solve or advance a path.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import localize_temporal_error_v1 as localization

s, api = localization.s, localization.api
ROOT = s.ROOT
SELF = Path(__file__).resolve()
DESIGN = ROOT / 'paper1_designs/full_horizon_timecap_20261016'
RUN = ROOT / 'paper1_runs/full_horizon_timecap_20261016'
DESTINATION = ROOT / 'paper1_evaluations/timecap_failure_20261017/diagnosis_01'
DEADLINE = '2026-10-18T02:59:34.905691+00:00'
EXPECTED = {
    str(Path(localization.__file__).resolve()): '91cbb91b53c55bc9dd841c5f71774e1f025d26cc7fec618e12a78814e1658838',
    str(RUN / 'comparison_fine/results.json'): '15d48be2710368ad8499a2998b53f0c31c085b6f1880116fc317d47b1ad048d7',
    str(RUN / 'final_execution_receipt_01/results.json'): 'd23b764b5d5c3769ee2607aca7c0107e424352641306b6575a9b2522f943bf1f',
    str(DESIGN / 'physical_cases_01.json'): '8538038840008bc1b5b06b0c595f4b916cfc9601f3573fff09284dba837d742b',
}
LEVELS = ('f0p0625', 'f0p03125')
EXPECTED_RECORDS = (313, 625)
EXPECTED_OVERLAPPING = (61, 122)


def bound(authorization, additional_bytes=0):
    s.environment()
    api.require(authorization['end_utc'] == authorization['simulation_cutoff_utc'] == DEADLINE,
                'Same existing absolute bound; no extension')
    api.require(datetime.now(timezone.utc) < datetime.fromisoformat(DEADLINE), 'Existing absolute deadline')
    cap = reserve = 20 * 1024**3
    api.require(authorization['unchanged_total_retention_bytes'] == cap
                and authorization['unchanged_free_reserve_bytes'] == reserve,
                'Unchanged total retention and free reserve')
    retained = sum(p.stat().st_size for name in ('paper1_runs', 'paper1_designs', 'paper1_evaluations')
                   for p in (ROOT / name).rglob('*') if p.is_file())
    free = shutil.disk_usage(ROOT).free
    api.require(retained + additional_bytes < cap and free - additional_bytes > reserve,
                'Diagnosis fits original retention and free reserve')
    return dict(retained_bytes_before=retained, free_bytes_before=free,
                anticipated_added_bytes=additional_bytes, total_retention_cap_bytes=cap,
                minimum_free_reserve_bytes=reserve)


def sealed(path):
    body = s.fields.sealed(path)
    api.require(s.read(path.with_name('completion.json'))['passed'] == body['passed'],
                'Completion status agrees with authenticated document')
    return body


def main():
    api.require(not DESTINATION.exists(), 'Create-only new diagnosis; preserve all existing seals')
    api.verify_mapping(EXPECTED)
    authorization = s.read(DESIGN / 'authorization_01.json')
    bound(authorization)
    controls = localization.controls()
    negative_path = RUN / 'comparison_fine/results.json'
    closure_path = RUN / 'final_execution_receipt_01/results.json'
    negative, closure = sealed(negative_path), sealed(closure_path)
    api.require(not negative['passed'] and negative['whole_start_to_terminal_paths']
                and not negative['paper1_dataset_complete'], 'Original complete negative remains negative')
    api.require(negative['original_gate_values'] == s.q.job.policy.GATES
                and negative['full_path_gates']['passed'] is False,
                'Exact original accuracy gates, unchanged')
    checks = negative['full_path_gates']['checks']
    api.require(checks['endpoint_q_over_U_max'] is False and checks['mean_L1_q_over_U_max'] is False
                and all(value for key, value in checks.items()
                        if key not in ('endpoint_q_over_U_max', 'mean_L1_q_over_U_max')),
                'Preserve exact two failed velocity gates and other passing gates')
    api.require(closure['passed'] and closure['all_exact_owned_identities_retired']
                and closure['dependent_dispatch_stopped'] and not closure['full_path_accuracy_passed']
                and not closure['core_result_admitted'] and not closure['live_logs_deferred']
                and closure['negative_fine_comparison_sha256'] == EXPECTED[str(negative_path)]
                and closure['original_shared_end_utc'] == DEADLINE,
                'Authenticated final closure of failed qualification, not scientific admission')
    for key in ('identity_inspections_before_hashing', 'identity_inspections_after_hashing'):
        api.require(len(closure[key]) == 4 and all(x['inspection'].get('no_such_process')
                    and x['inspection']['retired'] for x in closure[key]),
                    'Closed receipt preserves four exact retired identities')

    inputs = dict(EXPECTED)
    source_files = dict(negative['source_files'])
    for key in ('source_files', 'evidence_files', 'path_artifacts'):
        api.verify_mapping(negative[key])
    inputs.update(negative['evidence_files'])
    for path in (negative_path.with_name('completion.json'), closure_path.with_name('completion.json')):
        inputs[str(path)] = s.sha(path)
    plan = s.read(DESIGN / 'design_01.json')
    api.require(plan['binding'] == api.digest({k: v for k, v in plan.items() if k != 'binding'})
                and plan['authorization_sha256'] == s.sha(DESIGN / 'authorization_01.json')
                and plan['physical_design_sha256'] == EXPECTED[str(DESIGN / 'physical_cases_01.json')],
                'Frozen original authority and physical design binding')
    for key in ('source_files', 'physical_inputs'):
        api.verify_mapping(plan[key])
    source_files.update(plan['source_files'])
    inputs.update(plan['physical_inputs'])
    physical = s.read(DESIGN / 'physical_cases_01.json')
    api.require(physical['binding'] == api.digest({k: v for k, v in physical.items() if k != 'binding'})
                and physical['physical_equation_changes'] == physical['accuracy_gate_changes'] == [],
                'No physical equation or accuracy gate changes')
    pair = [next(x for x in physical['cases'] if x['factor'] == factor) for factor in (.0625, .03125)]
    api.require([x['id'] for x in pair] == [negative['core_case'], negative['reference_case']],
                'Exact original factors and physical cases')
    spec = pair[0]['spec']
    initial = spec['initial_state']
    initial_row = [0., *initial['position_m'], *initial['orientation'], *initial['velocity_generalized']]
    paths = [sorted((RUN / 'levels' / level / 'records').glob('production_*/trace.npy')) for level in LEVELS]
    trace_paths = [str(p) for branch in paths for p in branch]
    api.require([len(x) for x in paths] == list(EXPECTED_RECORDS)
                and len(trace_paths) == len(set(trace_paths)) == len(negative['path_artifacts']) == 938
                and set(trace_paths) == set(negative['path_artifacts']), 'Exact all-938 trace set; no omission')

    def blocks(branch):
        for path in branch:
            yield np.load(path, mmap_mode='r', allow_pickle=False)

    diagnosis = localization.localize(blocks(paths[0]), blocks(paths[1]), initial_row, spec['horizon_s'],
        spec['config']['prolate_semiaxes_m'][1], spec['config']['target_mean_interstitial_velocity_m_s'], 20)
    metrics = negative['full_path_gates']['metrics']
    metric_names = ('whole_position_over_b_max', 'whole_axis_vector_norm_max', 'endpoint_q_over_U_max',
                    'mean_L1_q_over_U_max', 'integrated_q_error_over_U_s',
                    'interval_velocity_sup_over_U_diagnostic_only')
    for name in metric_names:
        api.require(math.isclose(diagnosis[name], metrics[name], rel_tol=1e-11, abs_tol=1e-13),
                    'Unchanged original-clock metric reproduced: ' + name)
    api.require(metrics['common_start_s'] == 0. and metrics['common_stop_s'] == spec['horizon_s']
                and len(diagnosis['bins']) == 20, 'Original full horizon and equal absolute-time bins')
    selected = diagnosis['bins'][6:10]
    start, stop = selected[0]['start_s'], selected[-1]['stop_s']
    integral = math.fsum(row['integrated_q_error_over_U_s'] for row in selected)
    dominant = dict(zero_based_bin_indices=[6, 7, 8, 9], start_s=start, stop_s=stop,
                    integrated_q_error_over_U_s=integral, mean_q_error_over_U=integral / (stop - start),
                    fraction_of_total_L1=integral / diagnosis['integrated_q_error_over_U_s'])

    guard_files, coverage = {}, []
    for index, level in enumerate(LEVELS):
        level_root = RUN / 'levels' / level
        audit_path = level_root / 'full_audit_01/results.json'
        audit = sealed(audit_path)
        api.require(s.sha(audit_path) == negative['evidence_files'][str(audit_path)]
                    and audit['passed'] and audit['fresh_t0'] and audit['full_selector_policy_replayed']
                    and audit['original_physics_and_guard_replayed'], 'Existing complete raw/physics/selector audit')
        api.verify_mapping(audit['source_files'])
        source_files.update(audit['source_files'])
        labels = audit['production_labels']
        api.require(labels == [f'production_{i:05d}' for i in range(1, EXPECTED_RECORDS[index] + 1)]
                    and [p.parent.name for p in paths[index]] == labels, 'Entire ordered audited production path')
        witnesses, total_rows, total_tightened, total_triggers = [], 0, 0, 0
        for label in labels:
            record = level_root / 'records' / label
            guard_path = record / 'timecap_guard/results.json'
            guard_completion = guard_path.with_name('completion.json')
            for path in (guard_path, guard_completion):
                api.require(str(path) in audit['artifacts'] and s.sha(path) == audit['artifacts'][str(path)],
                            'Selector count document is sealed into original full audit')
                guard_files[str(path)] = s.sha(path)
            guard = sealed(guard_path)
            api.require(guard['passed'] and guard['independent_geometry_and_policy_replayed']
                        and guard['original_caps_never_increased'] and guard['pending_witnesses'] == 0
                        and guard['accepted_rows'] == guard['journal_entries']
                        and guard['native_solver_calls'] == guard['new_saved_steps'] == 0
                        and guard['replaces_original_physics_audit'] is False
                        and guard['raw_sha256'] == audit['artifacts'][str(record / 'call.json.xz')]
                        and guard['original_physical_guard_sha256'] == audit['artifacts'][str(record / 'guard_completion/results.json')],
                        'Exact existing selector/physical/raw document associations')
            total_rows += guard['accepted_rows']
            total_tightened += guard['tightened_steps']
            total_triggers += guard['trigger_count']
            if guard['start_s'] < stop and guard['stop_s'] > start:
                witnesses.append(dict(label=label, guard_path=str(guard_path), guard_sha256=s.sha(guard_path),
                    completion_sha256=s.sha(guard_completion), start_s=guard['start_s'], stop_s=guard['stop_s'],
                    accepted_rows=guard['accepted_rows'], tightened_steps=guard['tightened_steps'],
                    trigger_count=guard['trigger_count']))
        api.require(total_rows == audit['accepted_physical_steps'] and total_tightened == audit['tightened_steps']
                    and total_triggers == audit['trigger_count'], 'All sealed production selector counts reconcile')
        api.require(len(witnesses) == EXPECTED_OVERLAPPING[index]
                    and sum(x['tightened_steps'] for x in witnesses) == sum(x['trigger_count'] for x in witnesses) == 0,
                    'Exact dominant-band record coverage has no tightened steps or triggers')
        coverage.append(dict(level_id=level, all_production_records=len(labels), all_production_rows=total_rows,
            all_production_tightened_steps=total_tightened, all_production_trigger_count=total_triggers,
            overlapping_records=len(witnesses), overlapping_record_tightened_steps=0,
            overlapping_record_trigger_count=0, interval_definition='Entire records whose original clocks overlap dominant bins.',
            records=witnesses))

    endpoint = diagnosis['endpoint_delta_q_over_U']
    components = dict(mean_translation_norm_over_U=diagnosis['mean_translation_error_over_U'],
        mean_angular_scaled_norm_over_U=diagnosis['mean_angular_scaled_error_over_U'],
        endpoint_translation_norm_over_U=float(np.linalg.norm(endpoint[:3])),
        endpoint_angular_scaled_norm_over_U=float(np.linalg.norm(endpoint[3:])),
        interpretation='Separate three-component norms are nonadditive diagnostics, not portions of the original six-component norm. The original qrot is a*omega; all original gates retain the full six-component norm.')
    source_files[str(Path(localization.__file__).resolve())] = EXPECTED[str(Path(localization.__file__).resolve())]
    source_files[str(SELF)] = s.sha(SELF)
    api.verify_mapping(source_files)
    api.verify_mapping(inputs)
    api.verify_mapping(guard_files)
    api.verify_mapping(negative['path_artifacts'])
    body = dict(passed=True, schema='paper1.timecap-full.posthoc-error-localization.v1', utc=s.utc(),
        scope='Existing-evidence preparation only; diagnostic reproducibility passed, scientific qualification remains FAILED.',
        logical_core_id=negative['logical_core_id'], original_shared_end_utc=DEADLINE,
        new_transport_steps=0, new_native_solver_calls=0, evaluator_invocations=0, comparator_invocations=0,
        new_numerical_experiments=0, physical_equation_changes=[], accuracy_gate_changes=[],
        successor_dispatch_authorized=False, core_case_admission=False, paper1_dataset_complete=False,
        original_negative_comparison_sha256=EXPECTED[str(negative_path)],
        external_final_execution_receipt_sha256=EXPECTED[str(closure_path)],
        original_metrics=metrics, original_gate_values=negative['original_gate_values'],
        original_gate_checks=checks, original_metrics_reproduced=True,
        metric_comparison_tolerance=dict(relative=1e-11, absolute=1e-13), controls=controls,
        unchanged_localizer_callable='localize(blocks_a, blocks_b, initial_row, horizon_s, b_m, U_m_s, 20)',
        reproducible_invocation=[str(s.PYTHON), '-B', str(SELF)],
        required_environment={key: '1' for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')},
        no_smoothing_or_impact_alignment=True, no_extrapolation_or_postexport_imputation=True,
        diagnosis=diagnosis, component_norm_diagnostics_nonadditive=components,
        dominant_absolute_time_band=dominant, sealed_selector_coverage=coverage,
        trace_counts=dict(zip(LEVELS, EXPECTED_RECORDS)), path_artifacts=negative['path_artifacts'],
        source_files=source_files, evidence_files=inputs, selector_guard_files=guard_files,
        raw_contact_witnesses_included=False,
        raw_contact_witness_omission_reason='No fresh full-ancestry reconstruction is performed. Existing full-audit documents authenticate paths and selector counts; no raw-contact identity or force assertion is added.',
        inference_limits=[
            'Time bins are posthoc localization, not a prospective selector tuning or accuracy criterion.',
            'Independent fresh paths share t0 only; later mismatch cannot distinguish inherited divergence from newly generated truncation error or contact sensitivity.',
            'Zero selector tightening in the dominant interval establishes coverage only, not a causal coverage failure or a claim about active contacts.',
            'Previous common-state local diagnostics use different full initial states and cannot qualify these complete paths or isolate the ultimate cause.',
            'No causal attribution, convergence-order estimate, accuracy admission or new dispatch authority follows from this diagnosis.'],
        minimum_defensible_next_action='Read-only source/operand review of the original relaxation cap and constrained rotational/tangential update during sustained support, keeping the failed selector immutable; any numerical experiment requires its own prospective review and existing authority limits.')
    estimated = len(json.dumps(body, sort_keys=True, indent=2, allow_nan=False).encode('utf-8')) + 8192
    body['resource_check_before_seal'] = bound(authorization, estimated)
    api.require(not DESTINATION.exists(), 'No existing diagnosis overwritten')
    DESTINATION.mkdir(parents=True, exist_ok=False)
    s.seal(DESTINATION, body)
    api.require(sealed(DESTINATION / 'results.json')['original_metrics_reproduced'], 'Created diagnosis seal authenticates')
    print(json.dumps(dict(passed=True, source_sha256=s.sha(SELF), results_sha256=s.sha(DESTINATION / 'results.json'),
        controls=controls, dominant_absolute_time_band=dominant, overlapping_records=list(EXPECTED_OVERLAPPING),
        new_transport_steps=0, core_case_admission=False), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
