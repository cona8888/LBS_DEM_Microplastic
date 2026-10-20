"""Reconcile only authenticated Stage228 disposition into the mutable plans."""
from pathlib import Path
import verification_common_v1 as c
def update():
    c.bound();p=c.OUT/'final_disposition_01/results.json';r=c.sealed(p);c.verify(r['artifacts'])
    master=c.ROOT/'MASTER_PLAN.md';current=c.ROOT/'CURRENT_PLAN.md'
    prior={str(x):c.sha(x) for x in (master,current)}
    boundary='Equations, original physical gates and route order remain unchanged. These are saved fixed-pose implementation tests, with zero new transport steps; production, transfer, transitions, exact restart and full-path/event qualification remain open. No population shape/flow trend is established.'
    if r['full_fixed_pose_equivalence_qualified']:
        f=r['strata']['recorded_fallback'];h=r['strata']['healthy_early_success']
        cost=(f"Fallback outer calls use {100*f['runtime_gain_fraction']:.2f}% less time; healthy outer calls take {h['candidate_to_original_runtime_ratio']:.3f}× the baseline time. "
              f"Including context setup, telemetry capture and exit, fallback scoped transactions change by {100*f['scoped_transaction_runtime_gain_fraction']:.2f}% less time and healthy transactions take {h['scoped_transaction_candidate_to_original_runtime_ratio']:.3f}× the baseline time. ")
        qualification='All 98 saved poses and 294 broader paired scientific comparisons are exact, including residuals and retained route records; all 588 original independent physical/association audits pass.'
        decision='Keep the prototype unpromoted; the healthy cost gate remains unresolved.' if not r['all_strata_scoped_transaction_material_gain_passed'] else 'Local scoped-transaction cost gates pass; retain the prototype until independent transfer, transition, restart and full-path gates are completed.'
    else:
        cost='No broader unprofiled cost result is qualified. '
        qualification='The repaired four-call tiny gate passes an actual fallback reuse and zero healthy reuse, exact scientific outputs, original independent physical audits, all32 evidence-corruption controls and22 live-binding controls. The independent receipt also passes8 immutable/terminal-leaf controls and19 native-attribute controls. The98-pose cost screen is prepared but not started because the remaining bounded window is reserved for authentication.'
        decision='Keep the prototype unpromoted; broader cost qualification remains pending under a new bounded authorization.'
    headline=f"**Contact optimization:** Stage228 closes with {r['shared_outer_calls_attempted']}/640 attempted outer calls and {r['reused_requests']} audited reuse hits. {cost}{decision}  "
    paragraph=(f"**Closed Stage228 verification-overhead gate:** the [authenticated final disposition](stage228_evaluations/verification_overhead_20261007/final_disposition_01/results.json) records **{r['shared_outer_calls_attempted']}/640 calls**, **zero new transport steps**, and retired exact process identities under the separate 19:03:18–19:33:18 UTC authorization. {qualification} {cost}{decision}\n\n"
        "**Guard corrections and retained negatives:** the diagnostic profile separates 0.0073161 profiled seconds of repeated healthy request/origin disassembly from 0.0051179 s of excluded scope setup; nested profile timings are not pooled with ordinary timings. Baseline pure controls expose two inherited in-place closure-content misses. The frozen v2 tiny attempt preserves exact mechanics but fails its required actual reuse hit because SciPy BLAS/LAPACK tuple-keyed memo dictionaries cannot be represented. Frozen v3 pure fixtures pass, while passive real-scope qualification identifies conservative depth rejection of terminal leaves. Separately versioned repairs must preserve every typed memo key/value/order and fresh mutable/native attributes, retain the recursive cap and unknown/cycle safe misses, and verify immutable code by strongly retained actual identity. Pure synthetic guard tests do not establish actual reuse or physical results; only passing tiny and broader saved gates do. All prior source versions and negatives remain preserved.\n\n"
        f"**Timing scope and next gate:** report force-call costs and complete scoped transaction costs separately; setup cannot disappear from a total-cost claim. The 66 fallback/32 healthy fixture mixture deliberately oversamples 66 of 1,931 saved steps and cannot establish representative segment or campaign affordability. {boundary} Next, obtain a new bounded authorization and re-freeze the prepared98-pose unprofiled cost screen against that new deadline before any force dispatch. Measure both strata and actual scope lifetime; if healthy overhead remains material, profile remaining live-key/serialization and evidence costs before any dynamic transfer or production proposal. The overnight campaign remains closed and its heartbeat paused.\n\n")
    text=master.read_text(encoding='utf-8');lines=text.splitlines()
    lines=[headline if line.startswith('**Contact optimization:**') else line for line in lines]
    text='\n'.join(lines)+'\n'
    marker='## Immediate decision and next gates — 7 October 2026\n\n'
    assert marker in text;text=text.replace(marker,marker+paragraph,1)
    text=text.replace('**Next numerical gate — Stage228 proposal only:**','**Historical Stage228 antecedent proposal:**',1)
    text='\n'.join(("2. **Stage228 metadata/guard review completed; prototype remains unpromoted:** follow the current disposition and cost decision above. Preserve exact fresh live-key, certificate and physical checks while resolving remaining verification and serialization costs; measure both strata and actual scope lifetime before transfer, transition, exact restart or full-path promotion. Keep geometry membership, signed-gap, momentum, dissipation and event gates unchanged." if line.startswith('2. **Stage227 same-inner reuse') else line) for line in text.splitlines())+'\n'
    master.write_text(text,encoding='utf-8',newline='\n')
    text=current.read_text(encoding='utf-8').replace('**Stage227 current decision:**','**Historical Stage227 decision:**',1)
    marker='## Historical bottleneck plan — 12 September 2026'
    text=text.replace(marker,f"**Stage228 current decision:** [Final disposition](stage228_evaluations/verification_overhead_20261007/final_disposition_01/results.json): {r['shared_outer_calls_attempted']}/640 attempted calls, zero transport steps and {r['reused_requests']} audited reuse hits. {cost}{decision} Closure guard negatives and each failed/versioned repair remain preserved. {boundary} Follow MASTER_PLAN.md for the next numerical gates.\n\n"+marker,1)
    current.write_text(text,encoding='utf-8',newline='\n')
    out=c.OUT/'plan_update_01';paths=[master,current,p,p.parent/'completion.json',c.AUTH,Path(__file__).resolve()]
    c.commit(out/'results.json',dict(passed=True,utc=c.utc(),prior_mutable_plan_sha256=prior,inputs={str(p):c.sha(p),str(c.AUTH):c.sha(c.AUTH)},artifacts={str(x):c.sha(x) for x in paths},new_trajectory_steps=0,production_authorized=False))
    c.commit(out/'completion.json',dict(passed=True,results_sha256=c.sha(out/'results.json')))
    print('STAGE228_PLAN_UPDATED',c.sha(out/'results.json'),flush=True)
if __name__=='__main__':update()
