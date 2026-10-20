"""Create-only, authenticated fixed-outer-contact replay inputs; no solver imports.

Reads the sealed Stage222 segment247 payload and Stage223/224 reviews only.
It does not call an integrator, optimizer, old prepare/run or expired-clock API.
Captured JSON does not preserve original ndarray dtype, strides or bindings:
all inferred float64 fingerprints are explicitly reconstruction identities.
Definitive same-helper-request identity must be observed by the replay runner.
"""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import lzma
import math
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = 'exhausted_failure_replay_20261007'
OUT = ROOT/'stage226_evaluations'/BASE/'fixtures_01'
AUTHORIZATION = ROOT/'stage226_designs'/BASE/'authorization_01.json'
FOLDER = ROOT/'stage222_runs/overnight_coarser_20261007/run_01/s2_i0_fibre_f0p125/segment_00247'
SAVED_DESIGN = ROOT/'stage222_designs/overnight_coarser_20261007/design_01.json'
DECISION_DESIGN = ROOT/'stage224_designs/contact_cost_screen_20261007/decision_01.json'
DECISION = ROOT/'stage224_evaluations/contact_cost_screen_20261007/decision_01/results.json'
PROFILE = ROOT/'stage223_evaluations/overnight_contact_profile_20261007/review_01/results.json'
END = datetime.fromisoformat('2026-10-07T16:30:34+00:00')
SCHEMA = 'stage226-outer-replay-fixtures-v1'
INNER_FIELDS = ('vfree', 'mobility', 'jacobian', 'gaps_m', 'dt_s', 'friction',
                'tolerance', 'maxiter', 'accepted', 'velocity', 'health', 'error')
ARRAY_FIELDS = ('vfree', 'mobility', 'jacobian', 'gaps_m')
SOURCE_GUIDES = (
    'stage194_staging/qualify_projection_auditor_v1.py',
    'stage194_staging/qualify_semismooth_outer_v1.py',
    'stage189_staging/contact_trial_trace_v1.py',
    'stage198_staging/qualify_direct_trf_v1.py',
    'stage208_staging/cone_feasibility_stack_preflight_v1.py',
    'stage202_staging/contact_repaired_stack_preflight_v1.py',
    'stage200_staging/revised_stack_preflight_v1.py',
    'stage213_staging/normal_gap_scope_v1.py',
    'stage213_staging/audit_normal_gap_v1.py',
    'stage214_staging/normal_gap_stack_preflight_v1.py',
    'stage216_staging/same_policy_stack_preflight_v1.py',
    'stage219_staging/normal_gap_campaign_v1.py',
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def clock():
    require(datetime.now(timezone.utc) < END, 'new Stage226 extraction window closed')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def verify(mapping):
    for path, expected in mapping.items():
        clock()
        require(sha(path) == expected, 'frozen artifact changed: '+path)


def sealed(path):
    path = Path(path)
    row = read(path)
    require(read(path.parent/'completion.json')['results_sha256'] == sha(path),
            'completion seal: '+str(path))
    require(row['passed'] is True, 'passing authenticated source: '+str(path))
    return row


def bits(value):
    value = float(value)
    require(math.isfinite(value), 'finite captured operand')
    return struct.pack('>d', value).hex()


def tagged(value):
    """Scalar-type/signedzero-preserving identity of captured JSON, not ndarray."""
    if isinstance(value, float):
        return {'binary64': bits(value)}
    if isinstance(value, list):
        return [tagged(x) for x in value]
    if isinstance(value, dict):
        return {k: tagged(v) for k, v in value.items()}
    return value


def array_identity(value):
    def flatten(x):
        if not isinstance(x, list):
            return (), [float(x)]
        children = [flatten(z) for z in x]
        if not children:
            return (0,), []
        require(all(a[0] == children[0][0] for a in children), 'rectangular captured input')
        return (len(x), *children[0][0]), [v for a in children for v in a[1]]
    shape, values = flatten(value)
    require(all(math.isfinite(v) for v in values), 'finite reconstructed input')
    raw = b''.join(struct.pack('<d', v) for v in values)
    return {'identity_kind': 'reconstructed_json_float64_C_bytes',
            'shape': list(shape), 'reconstructed_dtype': '<f8',
            'bytes_sha256': hashlib.sha256(raw).hexdigest(),
            'original_runtime_dtype_strides_not_captured': True}


def resolve_inner(item, payload):
    base = {}
    reference = item.get('system_reference')
    if reference is not None:
        require(set(reference) == {'index', 'kind'}, 'exact saved reference fields')
        require(reference['kind'] in ('early', 'fallback'), 'recognized saved system reference')
        table = 'early_attempts' if reference['kind'] == 'early' else 'fallback_systems'
        index = reference['index']
        require(type(index) is int and 0 <= index < len(payload[table]), 'reference index')
        base = {k: copy.deepcopy(v) for k, v in payload[table][index].items() if k in INNER_FIELDS}
    base.update({k: copy.deepcopy(v) for k, v in item.items() if k != 'system_reference'})
    require(all(k in base for k in (*ARRAY_FIELDS, 'dt_s', 'friction', 'tolerance', 'maxiter')),
            'complete resolved same-inner captured input')
    require(base.get('accepted') is True and 'health' in base and 'velocity' in base,
            'accepted resolved inner output')
    base['saved_system_reference'] = copy.deepcopy(reference)
    return base


def identity(system, binding, policy):
    fields = {k: array_identity(system[k]) for k in ARRAY_FIELDS}
    fields.update({k+'_binary64': bits(system[k]) for k in ('dt_s', 'friction', 'tolerance')})
    fields.update(maxiter=system['maxiter'], effective_binding=binding,
                  numerical_policy_contract_sha256=policy)
    require(type(fields['maxiter']) is int, 'captured integer iteration cap')
    return {'fields': fields, 'sha256': digest(fields),
            'qualified_actual_helper_identity': False,
            'required_runtime_observation': 'Observe both early and fallback helper requests, seed bindings, dtype, shape and exact bytes; reconstructed equality alone is insufficient.'}


def associate(payload):
    associations = []
    for trial in payload['contact_trial_trace']['detailed_trials']:
        for inner in trial['inner_systems']:
            lo, hi = inner['fallback_range']
            if lo == hi:
                continue
            el, eh = inner['early_range']
            require(hi == lo+1 and eh == el+1, 'one associated failed early/fallback request')
            early, fallback = payload['early_attempts'][el], payload['fallback_systems'][lo]
            require(not early['accepted'] and fallback['accepted'], 'failed early followed by accepted fallback')
            require(early['error'] == 'direct contact residual nonconvergence', 'observed terminal failure category')
            require(bits(early['dt_s']) == bits(fallback['dt_s'])
                    and tagged(early['gaps_m']) == tagged(fallback['gaps_m']), 'recorded signed dt/gaps identity')
            associations.append({'dt_and_gaps_match': True, 'early_index': el,
                                 'fallback_index': lo, 'inner_index': inner['inner_index'],
                                 'projection_seed_index': fallback['health']['projection_seed_index'],
                                 'trial_index': trial['trial_index']})
    require(len(associations) == 66 and sorted(a['fallback_index'] for a in associations) == list(range(66)),
            'all66 fallback captures exactly once')
    return associations


def fixture(trial, payload, stratum, association=None):
    index = trial['trial_index']
    require(trial['accepted'] is True and len(trial['outer_inputs']) == 14, 'qualified positional outer interface')
    prepare = copy.deepcopy(payload['normal_gap_operand_policy']['prepare_calls'][index])
    require(prepare['index'] == index and tagged(prepare['contacts']) == tagged(trial['outer_inputs'][6]),
            'saved raw contacts and policy provenance association')
    # This inventory is fibre-only. No zeroing/shape policy change is introduced.
    require(all(m['classification']['sphere'] is False and not m['classification']['changed']
                for m in prepare['metadata']), 'unaltered fibre normal-gap operands')
    require(tagged(prepare['raw_gaps_m']) == tagged(prepare['effective_gaps_m']), 'unchanged signed fibre gaps')
    inner = [resolve_inner(s, payload) for s in trial['inner_systems']]
    for j, system in enumerate(inner):
        require(system['inner_index'] == j, 'complete sequential inner inventory')
        system['reconstruction_identity'] = identity(system, payload['effective_binding'],
                                                    payload['numerical_policy_contract_sha256'])
    el, eh = trial['early_range']; fl, fh = trial['fallback_range']
    early = [{'global_index': j, 'record': copy.deepcopy(payload['early_attempts'][j])} for j in range(el, eh)]
    fallback = [{'global_index': j, 'record': copy.deepcopy(payload['fallback_systems'][j])} for j in range(fl, fh)]
    reduced = [{'global_index': j, 'record': copy.deepcopy(payload['repairs'][j])} for j in range(fl, fh)]
    repairs = [{'global_index': j, 'record': copy.deepcopy(payload['result']['stage119_repair_calls'][j])} for j in range(fl, fh)]
    expected = {'accepted': trial['accepted'], 'velocity': copy.deepcopy(trial['velocity']),
                'health': copy.deepcopy(trial['health'])}
    require(tagged(expected['velocity']) == tagged(payload['rows'][index]['velocity_generalized']),
            'saved accepted row velocity association')
    call_identity = {'raw_sha256': sha(FOLDER/'call.json.xz'), 'trial_index': index,
                     'early_range': [el, eh], 'fallback_range': [fl, fh],
                     'outer_inputs_tagged_sha256': digest(tagged(trial['outer_inputs'])),
                     'binding': payload['effective_binding'],
                     'numerical_policy_contract_sha256': payload['numerical_policy_contract_sha256']}
    return {'fixture_id': f'{stratum}_trial_{index:05d}', 'stratum': stratum,
            'call_identity': call_identity, 'call_identity_sha256': digest(call_identity),
            'associated_target': copy.deepcopy(association),
            'outer_inputs': copy.deepcopy(trial['outer_inputs']),
            'expected_outer_outputs': expected, 'resolved_inner_systems': inner,
            'captured_route_evidence': {'early_attempts': early, 'fallback_systems': fallback,
                                        'reduced_repairs': reduced, 'stage119_repair_calls': repairs},
            'saved_physical_certificates': {'normal_gap_prepare': prepare,
                                           'saved_row_after_accepted_step': copy.deepcopy(payload['rows'][index]),
                                           'sweep_certificate': copy.deepcopy(payload['sweep_certificates'][index])},
            'force_audit_before': {'state': {'q': copy.deepcopy(trial['outer_inputs'][0])}},
            'saved_trajectory_association_is_reference_only': True,
            'replay_must_not_advance_position_orientation_clock_or_dwell': True}


def commit(path, value):
    clock()
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def run():
    clock()
    require(not OUT.exists(), 'exclusive create-only fixture inventory')
    authorization = read(AUTHORIZATION)
    require(authorization['end_utc'] == END.isoformat()
            and authorization['maximum_new_trajectory_steps'] == 0
            and authorization['maximum_saved_transport_steps'] == 0
            and authorization['simulation_dispatch'] is False
            and authorization['production_authorized'] is False
            and authorization['overnight_campaign_reopened'] is False, 'separately frozen zero-trajectory authority')
    verify(authorization['sources']); verify(authorization['inputs'])
    decision = sealed(DECISION)
    decision_design = read(DECISION_DESIGN)
    require(decision['design_sha256'] == sha(DECISION_DESIGN), 'frozen Stage224 decision design')
    profile = sealed(PROFILE)
    verify(decision_design['inputs']); verify(decision_design['sources'])
    verify(profile['inputs']); verify(profile['sources'])
    saved_design = read(SAVED_DESIGN)
    verify(saved_design['sources'])
    row = sealed(FOLDER/'results.json')
    require(row['transaction_profiled'] and row['new_saved_steps'] == 1931, 'original profiled1931-step saved segment')
    verify(row['artifacts'])
    require(row['design_sha256'] == sha(SAVED_DESIGN), 'saved design identity')
    seal = read(FOLDER/'call.json.seal.json')
    compressed = (FOLDER/'call.json.xz').read_bytes()
    require(hashlib.sha256(compressed).hexdigest() == seal['compressed_sha256'], 'compressed raw seal')
    raw = lzma.decompress(compressed)
    require(len(raw) == seal['uncompressed_bytes'] and hashlib.sha256(raw).hexdigest() == seal['uncompressed_sha256'],
            'full uncompressed raw seal')
    envelope = json.loads(raw)
    require(envelope['design_sha256'] == row['design_sha256'] == seal['design_sha256'], 'raw design binding')
    payload = envelope['packed_envelope']['payload']
    require(payload['design_sha256'] == row['design_sha256'], 'payload design binding')
    require(len(payload['early_attempts']) == len(payload['rows']) == len(payload['sweep_certificates'])
            == len(payload['normal_gap_operand_policy']['prepare_calls']) == 1931, 'complete profiled capture inventory')
    require(len(payload['fallback_systems']) == len(payload['repairs']) == len(payload['result']['stage119_repair_calls']) == 66,
            'complete fallback/repair capture inventory')
    associations = associate(payload)
    require(associations == decision['associated_failed_early_and_fallback_systems'], 'independent association equals frozen Stage224 decision')
    trials = {t['trial_index']: t for t in payload['contact_trial_trace']['detailed_trials']}
    healthy = [t for t in trials.values() if t['accepted']
               and t['fallback_range'][0] == t['fallback_range'][1]
               and t['early_range'][1] == t['early_range'][0]+1
               and payload['early_attempts'][t['early_range'][0]]['accepted']
               and payload['early_attempts'][t['early_range'][0]]['health']['solver'] == 'stage194_analytic_same_system_rejected_seed_v1']
    require(len(healthy) == 1865, 'all recorded healthy same-system success controls')
    positions = [j*(len(healthy)-1)//31 for j in range(32)]
    require(len(set(positions)) == 32, 'deterministic spaced control uniqueness')
    fixtures = [fixture(trials[a['trial_index']], payload, 'recorded_fallback', a) for a in associations]
    fixtures += [fixture(healthy[j], payload, 'healthy_early_success') for j in positions]
    require(len(fixtures) == len({f['fixture_id'] for f in fixtures}) == 98, 'approved fixture count and uniqueness')
    inputs = {str(p): sha(p) for p in (AUTHORIZATION, SAVED_DESIGN, DECISION_DESIGN, DECISION,
              DECISION.parent/'completion.json', PROFILE, PROFILE.parent/'completion.json',
              FOLDER/'results.json', FOLDER/'completion.json', FOLDER/'call.json.xz', FOLDER/'call.json.seal.json')}
    inputs.update(row['artifacts'])
    sources = {**saved_design['sources'], **decision_design['sources'], **profile['sources'], **authorization['sources']}
    sources.update({str(ROOT/p): sha(ROOT/p) for p in SOURCE_GUIDES})
    sources[str(Path(__file__).resolve())] = sha(__file__)
    inventory = {'schema': SCHEMA, 'utc': datetime.now(timezone.utc).isoformat(),
                 'new_bound_end_utc': END.isoformat(), 'new_trajectory_steps': 0,
                 'original_segment_steps_are_saved_reference_only': 1931,
                 'production_authorized': False, 'timing_claim': False,
                 'original_runtime_input_byte_identity_qualified': False,
                 'counts': {'fixtures': 98, 'all_recorded_fallbacks': 66, 'healthy_controls': 32,
                            'healthy_available': 1865},
                 'healthy_selection': {'method': 'floor(j*(1865-1)/31), j=0..31 in recorded trial order',
                                       'positions': positions, 'trial_indices': [healthy[j]['trial_index'] for j in positions]},
                 'inputs': inputs, 'sources': sources,
                 'saved_binding': payload['effective_binding'],
                 'saved_numerical_policy_contract_sha256': payload['numerical_policy_contract_sha256'],
                 'saved_spec': copy.deepcopy(payload['spec']),
                 'saved_minimum_gap_semantics': copy.deepcopy(payload['minimum_gap_semantics']),
                 'saved_trace_structural_identity': copy.deepcopy(payload['contact_trial_trace']['structural_identity']),
                 'normal_gap_policy_contract': {k: copy.deepcopy(v) for k,v in payload['normal_gap_operand_policy'].items() if k != 'prepare_calls'},
                 'output_comparison_rule': 'Compare scientific velocity/selected reactions/health and branch fields exactly; wall-time measurements are not numerical outputs. Keep executed optimizer counts distinct from logical route requests.',
                 'claim': 'Authenticated fixed-outer-call replay fixtures only. No solver run, new trajectory, speedup, restart or full-path qualification.',
                 'fixtures': fixtures}
    verify(inputs); verify(sources)
    OUT.mkdir(parents=True, exist_ok=False)
    commit(OUT/'fixtures.json', inventory)
    verify(inputs); verify(sources)
    result = {'passed': True, 'schema': SCHEMA, 'new_trajectory_steps': 0,
              'fixtures_sha256': sha(OUT/'fixtures.json'), 'counts': inventory['counts'],
              'input_hashes_authenticated': len(inputs), 'source_hashes_authenticated': len(sources),
              'full66_associations_match_frozen_decision': True,
              'actual_helper_identity_qualified': False,
              'production_authorized': False, 'timing_claim': False,
              'utc': datetime.now(timezone.utc).isoformat()}
    commit(OUT/'results.json', result)
    commit(OUT/'completion.json', {'passed': True, 'results_sha256': sha(OUT/'results.json'),
                                 'fixtures_sha256': result['fixtures_sha256']})
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    require(sys.argv[1:] == ['extract'], 'explicit extraction-only command')
    run()
