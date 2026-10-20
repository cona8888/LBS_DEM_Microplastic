"""Read-only recomputation of local decisions, then one immutable handoff."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
import probe_signed_gap_systems_v1 as probe
import verify_roundoff_candidate_v1 as primitive
import verify_short_replays_v1 as short
import verify_common_time_v1 as common
api, parent = probe.api, probe.parent
OUT = ROOT/'stage142_evaluations/sphere_roundoff_contract_20260919/handoff_01'


def main():
    pd = api.read(parent.DESIGN); parent.verify(pd)
    bindings = {str(Path(__file__)): api.sha(__file__)}; evidence = {}
    for name, folder in [('exact_gap_probe', probe.OUT), ('primitive', primitive.OUT), ('strict_replay', short.OUT), ('common_time', common.OUT)]:
        result = api.read(folder/'results.json'); seal = api.read(folder/'completion.json'); protocol = api.read(folder/'protocol.json')
        api.require(seal['results_sha256'] == api.sha(folder/'results.json'), name+' seal')
        if 'protocol_sha256' in seal:
            api.require(seal['protocol_sha256'] == api.sha(folder/'protocol.json'), name+' protocol seal')
        for field in ['sources', 'inputs']:
            if field in protocol: api.verify_mapping(protocol[field])
        if 'artifacts' in result: api.verify_mapping(result['artifacts'])
        for filename in ['results.json', 'completion.json', 'protocol.json']:
            p = folder/filename; bindings[str(p)] = api.sha(p)
        evidence[name] = result
    api.require(evidence['primitive']['passed'], 'primitive gate')
    failed = [r['id'] for r in evidence['strict_replay']['reference_replays'] if not r['passed']]
    api.require(not evidence['strict_replay']['passed'] and failed == ['sphere_08'], 'preserve strict-equivalence failure')
    comparisons = []
    for c in pd['cases']:
        if len(set(c['spec']['config']['prolate_semiaxes_m'])) != 1: continue
        p = common.OUT/('reference_'+c['id']+'.json'); r = api.read(p)
        ref = api.read(parent.OUT/(c['id']+'.json'))['result']
        cmp = parent.old.prior.compare_results(ref, r['result'], c['spec'], pd['limits'])
        api.require(cmp['passed'] and r['passed'], 'common-time state '+c['id'])
        elapsed = sum(row['dt_s'] for row in r['rows'])
        source = api.read(r['source'])['result']
        api.require(api.sha(r['source']) == r['source_sha256'] and abs(elapsed-(r['result']['time_s']-source['time_s'])) <= 1e-15, 'source and integrated clock')
        comparisons.append({'id': c['id'], **cmp})
        bindings[str(p)] = api.sha(p)
    endpoint_audit = []
    for segment in [2, 9]:
        p = short.OUT/f'endpoint_{segment:02d}.json'; rec = api.read(p); r = rec['result']
        source = api.read(rec['source'])['result']; rows = rec['rows']
        api.require(rec['source_sha256'] == api.sha(rec['source']), 'endpoint source')
        api.require(r['status'] == 'present_at_horizon' and r['time_s'] == 1.3 and len(rows) == 2, 'endpoint status')
        api.require(abs(sum(row['dt_s'] for row in rows)-(r['time_s']-source['time_s'])) <= 1e-15, 'endpoint integrated time')
        api.require(r['checkpoint']['state_sha256'] == api.digest(r['checkpoint']['state']), 'endpoint state')
        api.require(short.engine.prior.reference.independent_health(r, rec['spec']) == rec['health'] and rec['health']['passed'], 'endpoint health')
        endpoint_audit.append({'segment': segment, 'time_s': r['time_s'], 'accepted_steps': 2, 'runtime_s': r['runtime_seconds'], 'elapsed_s': r['time_s']-source['time_s']})
        bindings[str(p)] = api.sha(p)
    common_result = evidence['common_time']
    api.require(common_result['passed'] and len(common_result['common_time_refinement']) == 6 and all(r['passed'] for r in common_result['common_time_refinement']), 'common-time refinements')
    strict = evidence['strict_replay']
    api.require(all(r['passed'] and r['restart_exact_state'] for r in strict['short_refinements']), 'restart')
    api.require(all(r['passed'] for r in strict['guard_tests']), 'dispatch guard tests')
    api.require(all(r['passed'] and r['non_sphere_exactly_unchanged'] for r in strict['reference_replays'] if r['id'].startswith('fibre')), 'fibre unchanged')
    certificates = strict['contact_certificates']+common_result['contact_certificates']
    api.require(all(r['passed'] for r in certificates), 'candidate checks')
    corrections = [r['health'] for r in certificates if r['health'].get('geometric_contract') == 'sphere_local_roundoff_budget_v1']
    api.require(corrections and all(h['maximum_geometric_backward_error_m'] <= h['gap_budget_m'] for h in corrections), 'bounded geometric corrections')
    OUT.mkdir(parents=True, exist_ok=False)
    result = {'stage': 'Stage142', 'status': 'sphere_roundoff_revision_locally_verified_not_production_promoted',
        'drop_in_solver_equivalence': False, 'preserved_strict_failure': failed,
        'common_time_reference_comparisons': comparisons, 'short_common_time_refinements_passed': True,
        'exact_restart_at_three_step_levels': True, 'endpoint_audit': endpoint_audit,
        'independently_checked_candidate_calls': len(certificates), 'roundoff_corrected_calls': len(corrections),
        'max_required_gap_perturbation_m': max(h['maximum_geometric_backward_error_m'] for h in corrections),
        'max_raw_signed_gap_residual': max(h['raw_signed_gap_residual'] for h in corrections),
        'max_effective_gap_residual': max(h['residual'] for h in corrections),
        'important_contract_distinction': 'Raw signed gaps are preserved. Static sphere candidates are checked against explicitly nearby effective gaps inside a fixed floating-point-scale spatial budget. This is a numerical-method revision, not satisfaction of the original raw-gap tolerance in every call. Force/cone/energy thresholds are unchanged.',
        'guard_status': 'Implemented and unit-tested for the next dispatcher; immutable old dispatchers were not modified.',
        'fibre_solver_unchanged': True, 'fibre_contact_branch_uncertainty_resolved': False,
        'full_dwell_refinement_complete': False, 'population_release_fraction': None,
        'no_long_trajectory_or_gpu_job_launched': True,
        'next': ['Resolve the two frozen fibre contact-mode/tolerance systems without selecting a branch for a desired outcome.',
                 'Then freeze one short longer-duration three-level sphere refinement using the tested no-progress guard; no repeat of stalled dispatch loops.',
                 'Only after local numerical uncertainties are bounded resume the unchanged sphere/fibre release objective.'],
        'claim': 'Local numerical repair of saved sphere states; no irreversible trapping, population release, absolute permeability or experimental validation claim.',
        'binding_hashes': bindings}
    api.write(OUT/'results.json', result)
    api.write(OUT/'completion.json', {'results_sha256': api.sha(OUT/'results.json')})
    print({k:v for k,v in result.items() if k not in ['binding_hashes', 'common_time_reference_comparisons']}, flush=True)


if __name__ == '__main__':
    main()
