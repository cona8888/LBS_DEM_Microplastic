"""Read-only, authenticated cost attribution from the frozen contact profile."""
from pathlib import Path
import pstats, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage222_staging'))
import overnight_campaign_v1 as n


def run():
    folder=n.RUN/'s2_i0_fibre_f0p125/segment_00247'
    row=n.sealed(folder/'results.json');n.api.verify_mapping(row['artifacts'])
    n.api.require(row['passed'] and row['transaction_profiled'],'Passing declared profiled transaction')
    path=folder/'transaction_profile.pstats'
    stats=pstats.Stats(str(path))
    functions=[dict(file=k[0],line=k[1],function=k[2],primitive_calls=v[0],calls=v[1],
                    self_seconds=v[2],cumulative_seconds=v[3]) for k,v in stats.stats.items()]
    def exactly(suffix,name):
        matches=[x for x in functions if x['file'].endswith(suffix) and x['function']==name]
        n.api.require(len(matches)==1,'Unambiguous profiled phase '+name)
        return matches[0]
    phases=dict(
        contact_outer=exactly('stage189_staging\\contact_trial_trace_v1.py','outer'),
        contact_solve=exactly('stage104_staging\\trajectory_failure_only_rescue_v1.py','solve'),
        early_attempt=exactly('stage172_staging\\reduced_contact_fast_v1.py','early'),
        fallback_branch=exactly('stage183_staging\\capture_fallback_systems_v1.py','observed'),
        nonlinear_trf=exactly('exact_trf_helpers_v1.py::fixed_shape_helpers','trf_no_bounds'),
        raw_write=exactly('stage214_staging\\normal_gap_stack_preflight_v1.py','write_record'),
        decode=exactly('stage199_staging\\owned_decode_storage_v1.py','read_envelope'),
        independent_kernel=exactly('stage216_staging\\same_policy_stack_preflight_v1.py','kernel'))
    summary=row['summary'];steps=row['new_saved_steps']
    n.api.require(phases['fallback_branch']['calls']==summary['fallback_force_systems']==66,
                  'Profile call count matches independent solver-use ledger')
    result=dict(passed=True,utc=n.job.utc().isoformat(),new_trajectory_steps=0,
        profiled_steps=steps,start_s=summary['start_s'],stop_s=summary['stop_s'],first_dwell_s=summary['first_dwell_s'],
        producer_transaction_seconds=row['transaction_seconds'],recorded_physics_audit_seconds=summary['audit_seconds'],
        profiler_total_seconds=stats.total_tt,profiler_total_calls=stats.total_calls,
        nonlinear_calls_per_saved_step=phases['nonlinear_trf']['calls']/steps,
        fallback_saved_step_fraction=summary['fallback_force_systems']/steps,
        fallback_branch_fraction_of_contact_solve_profile=phases['fallback_branch']['cumulative_seconds']/phases['contact_solve']['cumulative_seconds'],
        phases=phases,top_self_time=sorted(functions,key=lambda x:x['self_seconds'],reverse=True)[:20],
        timing_limit='One instrumented segment; profiling overhead changes accepted work before the fixed call budget. Nested cumulative rows overlap and must not be added. Scope excludes launch/checkpoint copying before profiling and final receipt publication after profiling. Not a full-case speedup or unprofiled throughput estimate.',
        next_decision='Target contact iteration and Python dispatch cost with separately qualified equation-preserving candidates. Retain signed gaps, original residual checks and actual trajectory/event gates; no change to the active overnight run.',
        sources={str(Path(__file__).resolve()):n.api.sha(__file__)},
        inputs={str(folder/'results.json'):n.api.sha(folder/'results.json'),str(path):n.api.sha(path),str(n.PLAN):n.api.sha(n.PLAN)})
    out=ROOT/'stage223_evaluations/overnight_contact_profile_20261007/review_01'
    n.job.commit(out/'results.json',result);n.job.commit(out/'completion.json',dict(passed=True,results_sha256=n.api.sha(out/'results.json')))
    print('PROFILE_REVIEW',result['nonlinear_calls_per_saved_step'],result['fallback_saved_step_fraction'],result['fallback_branch_fraction_of_contact_solve_profile'],flush=True)


if __name__=='__main__':run()
