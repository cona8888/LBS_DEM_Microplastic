"""Read-only Stage233 two-contact fixtures for an original-baseline profile.

No authorization, output writer, solver or trajectory entry point is provided.
Parent histories come only from the sealed final FULL checkpoint and the sealed
all-record reconstruction/retirement proof. The original storage decoder then
reconstructs and hashes each selected complete logical record again.
"""
from pathlib import Path
from types import FunctionType
import copy, hashlib, importlib.util, json, sys

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BASE = 'sample124_fibre_20261009'
CASE = ROOT/'stage233_runs'/BASE/'run_01/s2_i124_fibre_f0p125'
EVAL = ROOT/'stage233_evaluations'/BASE
DESIGN = ROOT/'stage233_designs'/BASE/'design_01.json'
AUTH = DESIGN.with_name('authorization_01.json')
FINAL = EVAL/'final_disposition_01/results.json'
RETIREMENT = EVAL/'retirement_01/results.json'
CHECKPOINT = EVAL/'final_disposition_01/recoverable/checkpoint.json'
EXTRACTOR = ROOT/'stage226_staging/extract_replay_fixtures_v1.py'
READER = ROOT/'stage231_staging/verified_history_reader_v2.py'
PINS = {
    str(RETIREMENT): '538a9dec4d41a00ec5bcfd82c964c8bf0f1c74e957b2ee969dc66a245ced2e5b',
    str(FINAL): '4838ebe085a059a78f6d5ab99bb7d1aee4f5cbb6dd5fef4a5c1bc86748d2d995',
    str(DESIGN): '63eb2a1705ee15471a1ac91be8f31b83bbd7581550d5d1c9e699cd1490c2a31d',
    str(AUTH): 'daf3e8b5ce03e911c733e08ab185d31a916e4ffc412a8b04cc2c943318d8b756',
    str(READER): '3440cc0c282912ebf8a870adb5831db8b5f70f3f785b06d747a72bc84c1df3ec',
    str(EXTRACTOR): '6d8aa7c524f19c19fca6186abf210df193082f4a790e964c539286158d9e969d',
}
SELECTION = ((103, 9653), (114, 1))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify(mapping, bound):
    for path, expected in mapping.items():
        bound()
        require(sha(path) == expected, 'Immutable source/input/artifact changed: '+path)


def sealed(path):
    data = read(path)
    require(read(path.parent/'completion.json')['results_sha256'] == sha(path)
            and data['passed'] is True, 'Sealed passing receipt: '+str(path))
    return data


def fixture_function(original, folder):
    """Exact original pure fixture/resolution code in a per-folder namespace."""
    namespace = {**vars(original), 'FOLDER': folder}
    for name in ('resolve_inner', 'identity', 'fixture'):
        source = getattr(original, name)
        namespace[name] = FunctionType(source.__code__, namespace, source.__name__,
                                      source.__defaults__, source.__closure__)
        require(namespace[name].__code__ is source.__code__, 'Exact fixture code: '+name)
    return namespace['fixture']


def first_difficult(payload):
    trials = payload['contact_trial_trace']['detailed_trials']
    require([t['trial_index'] for t in trials] == sorted({t['trial_index'] for t in trials}),
            'Unique original detailed-trial order')
    matches = [t for t in trials if t.get('accepted') is True
               and len(t['outer_inputs'][6]) == 2
               and t['fallback_range'][0] < t['fallback_range'][1]]
    require(matches, 'Saved accepted two-contact fallback fixture required')
    return matches[0], len(matches)


def prepare_fixtures(codec=None, fresh_bound=lambda: None):
    """Return (inventory, sources, inputs); pure authenticated file reads only.

    A caller may supply its actual qualified original job.codec. No codec or
    model namespace is altered. The default is the original qualified storage
    alias, not the separately repaired reader or an expired campaign context.
    """
    fresh_bound()
    verify(PINS, fresh_bound)
    original = load(EXTRACTOR, '_stage235_original_fixture_extractor')
    reader = load(READER, '_stage235_storage_qualifier')
    codec = reader.qualified.codec if codec is None else codec
    storage_identity = reader.qualified_bindings(codec)
    retirement, final = sealed(RETIREMENT), sealed(FINAL)
    require(retirement['all117_selected_raw_records_independently_reconstructed_by_final_accountant']
            and retirement['all_exact_launch_identities_retired']
            and retirement['accounting_authenticated'] and final['accounting_authenticated']
            and retirement['known_unaccepted_saved_steps'] == 0
            and retirement['unknown_saved_steps_reservation_upper_bound'] == 0
            and not retirement['prototype_promoted'], 'Closed original ancestry/accounting required')
    require(retirement['final_disposition_sha256'] == sha(FINAL)
            and retirement['design_sha256'] == sha(DESIGN)
            and retirement['authorization_sha256'] == sha(AUTH), 'Final retirement bindings')
    design, authorization = read(DESIGN), read(AUTH)
    require(design['authorization_sha256'] == sha(AUTH), 'Original design authorization')
    sources = {**authorization['source_files'], **design['source_files'],
               str(EXTRACTOR): sha(EXTRACTOR), str(READER): PINS[str(READER)], str(SELF): sha(SELF)}
    for relative, expected in reader.SOURCE_SHA.items():
        require(sources.get(str(ROOT/relative), expected) == expected, 'Original storage source binding')
        sources[str(ROOT/relative)] = expected
    inputs = {**authorization['inputs'], **design['inputs'], **PINS,
              **retirement['closure_artifacts'], **retirement['closed_logs']}
    # Sources remain a separate family in the returned frozen consumer maps.
    for path in (SELF, EXTRACTOR, READER):
        inputs.pop(str(path), None)
    for path in (FINAL, RETIREMENT):
        inputs[str(path.parent/'completion.json')] = sha(path.parent/'completion.json')
    require(final['artifacts'][str(CHECKPOINT)] == retirement['last_full_checkpoint_file_sha256'],
            'FULL checkpoint file identity in both sealed receipts')
    inputs[str(CHECKPOINT)] = final['artifacts'][str(CHECKPOINT)]
    verify(sources, fresh_bound); verify(inputs, fresh_bound)
    checkpoint = read(CHECKPOINT)
    history = checkpoint['state']['history']
    require(len(history) == retirement['history_rows']
            and hashlib.sha256(codec.packed_history(history)).hexdigest() == retirement['history_sha256'],
            'Authenticated complete original terminal history')
    fixtures, evidence = [], []
    common = None
    for number, expected_trial in SELECTION:
        fresh_bound()
        folder = CASE/f'segment_{number:05d}'
        parent_folder = CASE/f'segment_{number-1:05d}'
        for item_folder in (parent_folder, folder):
            receipt = sealed(item_folder/'results.json')
            for name in ('results.json', 'completion.json', 'call.json.xz', 'call.json.seal.json'):
                path = item_folder/name
                require(str(path) in final['artifacts'], 'Ancestry receipt contains selected original artifact')
                inputs[str(path)] = final['artifacts'][str(path)]
            inputs.update(receipt['artifacts'])
        verify({p: h for p, h in inputs.items() if str(folder) in p or str(parent_folder) in p}, fresh_bound)
        receipt = sealed(folder/'results.json')
        selected = [r for r in final['records'] if Path(r['folder']) == folder]
        require(len(selected) == 1 and selected[0]['status'] == 'accepted'
                and selected[0]['independently_decoded'] is True
                and selected[0]['receipt_sha256'] == sha(folder/'results.json'), 'Independently accepted selected record')
        require(receipt['summary']['passed'] and receipt['summary']['trial_audit']['passed']
                and receipt['summary']['normal_gap_operand_policy_verified'], 'Original independent physical gates')
        path = folder/'call.json.xz'
        envelope = codec.base.read_record(path, design['physical_design_sha256'])
        reference = envelope['history']['prefix']
        require(reference is not None and Path(reference['path']) == parent_folder/'call.json.xz'
                and reference['design_sha256'] == design['physical_design_sha256'], 'Exact immediate original parent')
        prefix = codec.HistoryState(**reference,
            history_bytes=codec.packed_history(history[:reference['history_length']]))
        # Original read_record -> original unpack, prefix validation, decode,
        # history/hash and full original canonical logical-byte checks.
        payload, state = codec.read_record(path, design['physical_design_sha256'], prefix)
        require(state.history_bytes == codec.packed_history(history[:state.history_length]),
                'Selected full logical history equals authenticated terminal prefix')
        if number == 114:
            require(payload['result']['checkpoint'] == checkpoint, 'Exact terminal FULL checkpoint')
        require(payload['input_checkpoint_sha256'] == receipt['input_checkpoint_sha256']
                and payload['numerical_policy_contract_sha256'] == design['numerical_policy_contract_sha256'],
                'Original physical/policy record identity')
        require(len(payload['rows']) == receipt['new_saved_steps'] == selected[0]['saved_steps']
                and payload['result']['rejected'] == 0, 'Original accepted row/trial association')
        trial, available = first_difficult(payload)
        require(trial['trial_index'] == expected_trial, 'Prospective first-trial selection changed')
        make_fixture = fixture_function(original, folder)
        row = make_fixture(trial, payload, 'recorded_fallback')
        row['fixture_id'] = f'segment_{number:05d}_'+row['fixture_id']
        fl, fh = trial['fallback_range']
        require(trial['early_range'] == [0, 0] and fh == fl+2
                and len(row['resolved_inner_systems']) == 2, 'Original two-inner scalar fallback route')
        for item in row['resolved_inner_systems']:
            lo, hi = item['fallback_range']
            require(hi == lo+1 and item['early_range'] == [0, 0]
                    and original.tagged(item['gaps_m']) == original.tagged(row['saved_physical_certificates']['normal_gap_prepare']['raw_gaps_m'])
                    and payload['result']['stage119_repair_calls'][lo]['original_exception'] == 'direct contact residual nonconvergence'
                    and item['health']['solver'] == 'stage201_primary_failure_two_contact_scalar_v3',
                    'Genuine original primary-failure two-contact scalar evidence')
        row['associated_target'] = dict(segment=number, trial_index=trial['trial_index'],
            saved_record_receipt_sha256=sha(folder/'results.json'),
            independent_trial_audit=copy.deepcopy(receipt['summary']['trial_audit']),
            selected_fallback_audits=copy.deepcopy(receipt['summary']['fallback_audits'][fl:fh]),
            original_logical_sha256=state.original_sha256,
            original_history_sha256=state.history_sha256,
            parent_reference=copy.deepcopy(reference), available_two_contact_fallback_trials=available,
            selection='First accepted actual two-contact fallback detailed trial in original saved order')
        require(all(x['passed'] and x['contacts'] == 2 for x in row['associated_target']['selected_fallback_audits']),
                'Saved independent selected fallback physical audits')
        metadata = dict(saved_binding=payload['effective_binding'],
            saved_numerical_policy_contract_sha256=payload['numerical_policy_contract_sha256'],
            saved_spec=copy.deepcopy(payload['spec']),
            saved_minimum_gap_semantics=copy.deepcopy(payload['minimum_gap_semantics']),
            saved_trace_structural_identity=copy.deepcopy(payload['contact_trial_trace']['structural_identity']),
            normal_gap_policy_contract={k:copy.deepcopy(v) for k,v in payload['normal_gap_operand_policy'].items() if k!='prepare_calls'})
        if common is None:
            common = metadata
        else:
            require(common == metadata, 'Same original physical/policy/observer context')
        fixtures.append(row)
        evidence.append(dict(segment=number, trial_index=trial['trial_index'], original_logical_record_reconstructed=True,
                             original_logical_sha256=state.original_sha256, first_fallback_saved_time_s=payload['rows'][trial['trial_index']]['time_s']))
        del payload, envelope
    verify(sources, fresh_bound); verify(inputs, fresh_bound)
    inventory = dict(schema='stage235-original-two-contact-fixed-pose-fixtures-v1', **common,
        fixtures=fixtures, counts=dict(fixtures=2, recorded_fallbacks=2),
        sources=sources, inputs=inputs, original_storage_identity=storage_identity,
        selected_complete_logical_records=evidence,
        full_history_ancestry_authority_sha256=PINS[str(RETIREMENT)],
        original_runtime_input_byte_identity_qualified=False,
        new_trajectory_steps=0, new_saved_transport_steps=0, force_calls=0,
        production_authorized=False, prototype_promoted=False, timing_claim=False,
        claim='Two authenticated genuine original two-contact fallback fixed poses only; no force run, new trajectory, speedup or full-path claim.')
    return inventory, sources, inputs


def controls():
    """Pure selection/type/signed-zero/namespace controls, no archived reads."""
    original = load(EXTRACTOR, '_stage235_pure_fixture_extractor')
    fn = fixture_function(original, Path('pure-folder'))
    require(fn.__code__ is original.fixture.__code__
            and fn.__globals__['resolve_inner'].__code__ is original.resolve_inner.__code__
            and fn.__globals__ is not vars(original)
            and original.FOLDER != Path('pure-folder'), 'Private exact original fixture helpers')
    require(original.tagged([-0.0]) != original.tagged([0.0]), 'Signed zero cannot be silently changed')
    rejected = 0
    for trials in ([], [dict(accepted=False, outer_inputs=[None]*6+[[], None], fallback_range=[0,1], trial_index=0)],
                   [dict(accepted=True, outer_inputs=[None]*6+[[1,2,3], None], fallback_range=[0,1], trial_index=0)]):
        try:
            first_difficult(dict(contact_trial_trace=dict(detailed_trials=trials)))
        except RuntimeError:
            rejected += 1
    require(rejected == 3, 'Unavailable/rejected/wrong-contact-count fixtures rejected')
    return dict(passed=True, pure_controls=5, force_calls=0, new_trajectory_steps=0,
                artifact_writes=0, original_fixture_code_objects_retained=True)
