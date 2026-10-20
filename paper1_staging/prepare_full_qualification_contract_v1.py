"""Create-only prospective physics/policy documents; no model imports or work.

This prepares a proposal, not authority. Closed prior source/evidence records
remain untouched. Native controls are explicitly future bounded work.
"""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'paper1_designs/full_horizon_repair_20261018'
OLD = ROOT / 'paper1_designs/full_horizon_timecap_20261016/physical_cases_01.json'
EXPECTED_OLD = '8538038840008bc1b5b06b0c595f4b916cfc9601f3573fff09284dba837d742b'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def commit(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')
    return sha(path)


def build():
    assert sha(OLD) == EXPECTED_OLD, 'original complete physical definition bytes'
    old = json.loads(OLD.read_text(encoding='utf-8'))
    policy = dict(schema='paper1.full-state-stepdoubling.fixed-policy.v1',
        prepared_utc=datetime.now(timezone.utc).isoformat(),
        kind='inactive numerical-policy specification, not execution authority',
        original_nominal_factors=[.0625, .03125, .125],
        original_physical_definition_sha256=EXPECTED_OLD,
        fresh_t0_only=True, full_horizon_s=.9364396280429768,
        local_indicators=dict(position_m_at_factor0p125=1e-12,
            signed_director_norm_at_factor0p125=1e-8,
            generalized_velocity_over_original_U_at_factor0p125=5e-5,
            scaling='each local indicator multiplied by (nominal_factor/0.125)^2',
            meaning='prospective error indicators; neither global error bounds nor a convergence-order claim'),
        macro_policy=dict(new_origin='reset halving depth to zero and reconstruct the ORIGINAL selected cap at this new literal FULL physical state',
            same_origin_rejection='discard all branches and halve the requested macro interval exactly; at most eight halvings',
            maximum_halvings=8, minimum_requested_macro_h_s=1e-14,
            actual_original_substep_dt='min(original own-state selected cap, requested interval cap, literal target_time-current_time)',
            original_cap_recovery_between_new_states_permitted=True,
            nominal_factor_escalation_permitted=False,
            first_half_target='literal origin t + requested macro h/2',
            second_half_and_coarse_target='literal origin t + requested macro h',
            only_committed_state='literal original F1 then F2 chain, including original FULL history/monitor/recovery/statistics',
            exact_common_clock_required=True,
            clock_or_own_state_cap_mismatch='bounded same-origin halving; never interpolate or relabel time',
            original_physical_or_evidence_failure='terminal negative, never supplemental accuracy retry',
            exported_branch='preserve original exit truncation and stop this attempt negative; never extend or promote it',
            original_pending_trial='must remain None; separately bound new controller pending branches are allowed only at explicit checkpoints'),
        forbidden=['Richardson state extrapolation', 'signed-director alignment', 'clock shifting',
                   'smoothing', 'gap modification', 'force or friction modification',
                   'source binding edits', 'old failed/local-reset prefix credit',
                   'tolerance retuning after observed errors', 'fourth refinement level'],
        native_qualification_required_after_explicit_approval=True,
        native_qualification_completed=False, numerical_work_launched=False,
        supersedes_only_unapproved_engineering_interpretation=dict(
            file=str(FOLDER/'integration_contract_01.json'),
            clarification='No increase of the original nominal factor or own-state cap. Supplemental rejection halves only within the same origin; it does not permanently ratchet later variable timesteps.'))
    policy_path=FOLDER/'method_policy_qualification_01.json'
    policy_sha=commit(policy_path,policy)
    physical=dict(schema='paper1.full-state-stepdoubling.physical.v1',
        cases=[], minimum_gap_semantics=copy.deepcopy(old['minimum_gap_semantics']),
        original_physical_definition_file=str(OLD), original_physical_definition_sha256=EXPECTED_OLD,
        numerical_policy_file=str(policy_path), numerical_policy_sha256=policy_sha,
        physical_equation_changes=[],accuracy_gate_changes=[],gap_policy_changes=[],route_order_changes=[],
        source_only_preparation=True, dispatch_authorized=False)
    for case in old['cases']:
        new=copy.deepcopy(case)
        new['level_id']={.125:'f0p125',.0625:'f0p0625',.03125:'f0p03125'}[case['factor']]
        # The literal original physical specs, including all numerical upper
        # caps and the original full observation horizon, are copied unchanged.
        assert new['spec']==case['spec']
        physical['cases'].append(new)
    # Same original administrative binding arithmetic, with a distinct new
    # design identity. Per-case binding fields are derivatives, excluded here.
    physical['binding']=original_digest(physical)
    for case in physical['cases']:
        case['binding']=original_digest([physical['binding'],case['id']])
    physical_path=FOLDER/'physical_cases_qualification_01.json'
    physical_sha=commit(physical_path,physical)
    print(json.dumps(dict(policy_file=str(policy_path),policy_sha256=policy_sha,
        physical_file=str(physical_path),physical_sha256=physical_sha,
        original_specs_identical=True, new_native_calls=0,new_steps=0,
        authorization_created=False),sort_keys=True))


if __name__=='__main__':
    build()
