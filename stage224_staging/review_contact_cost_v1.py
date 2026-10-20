"""Authenticate bottleneck evidence and freeze the next optimization decision.

No integration, solver installation or process mutation. Negative/incomplete
screens remain preserved. Evidence supports a proposed per-call optimization,
not a measured speedup or authorization to alter the active frozen campaign.
"""
from pathlib import Path
from datetime import datetime, timezone
import pstats, sys, time
import check_split_pair_v1 as point

ROOT=point.ROOT
OUT=ROOT/'stage224_evaluations/contact_cost_screen_20261007/decision_01'
DESIGN=ROOT/'stage224_designs/contact_cost_screen_20261007/decision_01.json'
OPT=point.OUT.with_name('inner_optimizer_01')/'results.json'


def sealed(path):
    row=point.read(path)
    assert point.read(path.parent/'completion.json')['results_sha256']==point.sha(path)
    return row


def run():
    assert time.time()<point.DEADLINE
    payload=point.authenticate()
    arithmetic=sealed(point.OUT/'results.json')
    optimizer=sealed(OPT)
    profile_path=point.FOLDER/'transaction_profile.pstats'
    stats=pstats.Stats(str(profile_path))
    found=[(k,v) for k,v in stats.stats.items() if k[0].endswith('stage194_staging\\semismooth_rejected_seed_v1.py') and k[2]=='solve']
    assert len(found)==1
    _,entry=found[0]
    early=[v for k,v in entry[4].items() if k[2]=='early_candidate']
    repeated=[v for k,v in entry[4].items() if k[2]=='preferred']
    assert len(early)==len(repeated)==1
    contact=next(v for k,v in stats.stats.items() if k[0].endswith('stage104_staging\\trajectory_failure_only_rescue_v1.py') and k[2]=='solve')
    projection=next(v for k,v in stats.stats.items() if k[0].endswith('stage194_staging\\sliding_projection_repair_v3.py') and k[2]=='solve')
    related=[]
    for trial_index,trial in enumerate(payload['contact_trial_trace']['detailed_trials']):
        for inner in trial['inner_systems']:
            ea,eb=inner['early_range'];fa,fb=inner['fallback_range']
            if eb-ea==fb-fa==1:
                a=payload['early_attempts'][ea];b=payload['fallback_systems'][fa]
                if not a['accepted'] and a.get('error')=='direct contact residual nonconvergence':
                    assert a['dt_s']==b['dt_s'] and a['gaps_m']==b['gaps_m']
                    related.append(dict(trial_index=trial_index,inner_index=inner['inner_index'],
                                        early_index=ea,fallback_index=fa,dt_and_gaps_match=True,
                                        projection_seed_index=b['health']['projection_seed_index']))
    assert len(related)==repeated[0][1]==66
    # The frozen first inner screen accidentally included cold specialization
    # in its initial timed pair. Preserve it and explicitly disqualify that
    # aggregate from performance inference; this correction is diagnostic.
    ordinary=[r for r in optimizer['reports'] if r['subset']=='early_attempts']
    diagnostic={m:sum(sum(r['timings'][m][1:] if i==0 else r['timings'][m])
                     for i,r in enumerate(ordinary)) for m in ('baseline','split')}
    controls=dict(primary_hypothesis='Reuse an exhausted analytic failure only inside the SAME inner contact solve, before the second identical semismooth attempt.',
                  exact_key=['vfree bytes','mobility bytes','ordered Jacobian bytes','signed gaps bytes','dt bits','friction bits','tol bits','maxiter','solver/seed/operand-policy identity'],
                  scope='Fresh empty cache at each inner solver entry; discard in finally. No reuse across poses, timesteps, inner sweeps, contact ordering or policy changes.',
                  cacheable_outcome='Only demonstrably exhaustive, deterministic nonconvergence; never deadlines, nonfinite input, exceptions, interrupted or partially recorded searches.',
                  safety='Recheck deadline at every request. Preserve original failures/seed-route evidence and logical accounting; do not fabricate optimizer evaluations or suppress audits.',
                  dispatch='Original primary, reduced, projection and final force gates retain their existing order and outputs.',
                  prerequisites=['Instrument exact input/seed-function identity on all 66 associated fallback systems and existing difficult fixtures.',
                                 'Bounded paired full outer-solve replay: exact velocity, selected forces, branch/health fields; independent original signed-gap, residual, cone, force-balance and dissipation audits.',
                                 'Unprofiled alternating timing with full warmup outside measured scope; ordinary and fallback strata separately; confirm at least the existing material 5% gain gate.',
                                 'Representative transition trajectory, exact serial/split full checkpoint qualification, then unchanged complete-path/event gates before production.'],
                  secondary_hypothesis='Split residual/Jacobian callbacks only if a repaired timing screen shows material gain.',
                  secondary_status='392 pointwise checks and 64 inner optimizer calls exact; no credible gain established; not promoted.',
                  active_campaign_changed=False,new_trajectory_steps=0,production_authorized=False,
                  campaign_deadline_utc='2026-10-07T12:10:57+00:00',
                  deadline_rule='No simulation or other campaign work after deadline; these proposed gates create no automatic later dispatch.')
    sources=[Path(__file__).resolve(),Path(point.__file__),ROOT/'stage224_staging/split_analytic_pair_v1.py',
             ROOT/'stage224_staging/check_split_optimizer_v1.py',ROOT/'stage194_staging/early_semismooth_dispatch_v1.py',
             ROOT/'stage194_staging/semismooth_rejected_seed_v1.py',ROOT/'stage194_staging/sliding_projection_repair_v3.py']
    inputs=[point.OUT/'results.json',point.OUT/'completion.json',OPT,OPT.parent/'completion.json',
            point.FOLDER/'results.json',point.FOLDER/'completion.json',point.FOLDER/'call.json.xz',
            point.FOLDER/'call.json.seal.json',profile_path]
    design=dict(stage='Stage224 contact-cost decision, analysis and prospective gates only',
                utc=datetime.now(timezone.utc).isoformat(),controls=controls,
                sources={str(p):point.sha(p) for p in sources},inputs={str(p):point.sha(p) for p in inputs})
    point.commit(DESIGN,design)
    result=dict(passed=True,analysis_authentication_passed=True,design_sha256=point.sha(DESIGN),
                new_trajectory_steps=0,arithmetic_points=arithmetic['exact_points'],optimizer_calls=optimizer['optimizer_calls'],
                contact_solve_profile_seconds=contact[3],early_semismooth_calls=early[0][1],early_semismooth_profile_seconds=early[0][3],
                fallback_semismooth_calls=repeated[0][1],fallback_semismooth_profile_seconds=repeated[0][3],
                projection_profile_seconds=projection[3],associated_failed_early_and_fallback_systems=related,
                full_attempt_identity_qualified=False,
                repeated_search_fraction_of_contact_profile=repeated[0][3]/contact[3],
                optimistic_contact_speedup_if_all_second_search_removed=contact[3]/(contact[3]-repeated[0][3]),
                optimistic_profile_speedup_if_all_second_search_removed=stats.total_tt/(stats.total_tt-repeated[0][3]),
                ceilings_limit='Hypothetical local profiled ceilings only; do not imply exact identity, eligibility, zero replay overhead, full-route gain or production speedup.',
                split_timing_disposition=dict(initial_aggregate_disqualified='Initial measured pair contains cold JIT specialization despite intended warmup. Frozen attempt retained.',
                                              posthoc_diagnostic_ordinary_totals=diagnostic,
                                              posthoc_diagnostic_ordinary_speedup=diagnostic['baseline']/diagnostic['split'],
                                              fallback_zero_seed_inner_speedup=optimizer['summaries']['fallback_systems']['provisional_inner_speedup'],
                                              fallback_limit='Zero-seed development probes all reached unchanged max_nfev; they do not replay the recorded successful projection path.',
                                              production_promoted=False),
                controls=controls,claim='A better optimization target identified and a lower-priority prototype screened. No actual speedup or new physical/trajectory qualification established.')
    point.commit(OUT/'results.json',result)
    point.commit(OUT/'completion.json',dict(passed=True,results_sha256=point.sha(OUT/'results.json')))
    print('DECISION_SEALED',len(related),'fallback associations',result['repeated_search_fraction_of_contact_profile'],'contact fraction; no promotion')


if __name__=='__main__':run()
