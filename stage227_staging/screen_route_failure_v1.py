"""Conditional full fixed-pose equivalence/cost screen; zero transport steps."""
from pathlib import Path
from datetime import datetime
import os, sys, time, traceback
import replay_route_failure_v1 as b

c=b.c
DESIGN=c.DESIGNS/'full_replay_01.json'
OUT=c.OUT/'full_replay_01'


def prepare():
    a=c.bound();c.environment()
    tiny=c.sealed(b.OUT/'results.json')
    assert tiny['passed'] and tiny['tiny_qualified'] and tiny['actual_hit_mutation_controls']['passed']
    c.verify(tiny['artifacts'])
    prior=c.used_outer_calls();assert prior+588<=a['maximum_nonadvancing_outer_calls']
    inventory=c.read(b.FIXTURE_DIR/'fixtures.json');c.verify(inventory['inputs']);c.verify(inventory['sources'])
    assert len(inventory['fixtures'])==98 and inventory['counts']['all_recorded_fallbacks']==66
    inputs=[c.AUTH,b.DESIGN,b.OUT/'results.json',b.OUT/'completion.json',b.FIXTURE_DIR/'fixtures.json',b.FIXTURE_DIR/'results.json',b.FIXTURE_DIR/'completion.json']
    c.commit(DESIGN,dict(stage='Stage227 separately frozen conditional full fixed-pose cost screen',utc=c.utc(),
        authorization_sha256=c.sha(c.AUTH),end_utc=a['end_utc'],prior_outer_calls_attempted=prior,
        maximum_outer_calls=588,qualification_pairs=98,timing_repetitions=2,
        minimum_material_gain_fraction=a['minimum_material_gain_fraction'],modes=['original','reuse'],
        inputs={str(p):c.sha(p) for p in inputs},sources={**inventory['sources'],**{str(p):c.sha(p) for p in [*b.source_files(),Path(__file__).resolve()]}},
        strict_paired_scientific_fields_including_residuals=True,unchanged_original_physical_gates=True,
        declared_timing_field_exclusions=sorted(b.TIMING_FIELDS),
        timed_scope='Unobserved current Stage194 baseline versus entire candidate outer-call cost including exact bindings, trace, witness and append verification; all pairs qualified/warmed before two alternating timing repetitions. Scope construction, auditing, serialization and warmup excluded.',
        domain='All66fallback poses plus32healthy controls from one saved fibre segment; deliberately fallback-heavy sample, no representative campaign-cost inference.',
        production_authorized=False,new_trajectory_steps=0,new_saved_transport_steps=0,simulation_dispatch=False))
    print('PREPARED_CONDITIONAL_FULL_SCREEN',c.sha(DESIGN),'max588calls',flush=True)


def run():
    a=c.bound();c.environment();d=c.read(DESIGN);c.verify(d['inputs']);c.verify(d['sources'])
    assert d['authorization_sha256']==c.sha(c.AUTH) and c.used_outer_calls()==d['prior_outer_calls_attempted']
    p=b.psutil.Process();p.cpu_affinity([a['logical_cpu']])
    c.commit(OUT/'launch.json',dict(utc=c.utc(),pid=os.getpid(),created=p.create_time(),argv=sys.argv,command=p.cmdline(),
        design_sha256=c.sha(DESIGN),python=sys.version,platform=b.platform.platform(),affinity=p.cpu_affinity(),
        threads={k:os.environ[k] for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')},numpy_version=b.np.__version__,new_trajectory_steps=0))
    reports=[];calls=0
    try:
        inventory=c.read(b.FIXTURE_DIR/'fixtures.json');rows=inventory['fixtures']
        b.JOB.parent.b.old.parent.configure();b.STACK.candidate.warm()
        for phase,repeat in [('qualification',None),('timing',0),('timing',1)]:
            for index,row in enumerate(rows):
                paired=None;mode_order=d['modes'] if (index+(repeat or 0))%2==0 else list(reversed(d['modes']))
                for mode in mode_order:
                    c.bound();assert calls<d['maximum_outer_calls'] and calls+d['prior_outer_calls_attempted']<a['maximum_nonadvancing_outer_calls'];calls+=1
                    item=b.call(inventory,row,mode,d['end_utc'])
                    now=b.scientific(item['force_audit_fixture'])
                    if paired is None:paired=now
                    else:assert c.digest(paired)==c.digest(now),'Strict paired full scientific fixture including residuals and original route records'
                    name=f'{index:03d}_{mode}.json' if repeat is None else f'{repeat}_{index:03d}_{mode}.json'
                    path=OUT/phase/name;c.commit(path,item)
                    log=item['reuse_log']
                    reports.append(dict(phase=phase,repeat=repeat,fixture_id=row['fixture_id'],stratum=row['stratum'],mode=mode,
                        seconds=item['seconds'],path=str(path),sha256=c.sha(path),
                        reused_requests=0 if log is None else log['reused_requests'],archival_residual_differences=item['archival_residual_differences']))
                if index%16==0:print('FULL_EXACT_PAIRS',phase,repeat,index+1,'calls',calls,flush=True)
        assert calls==588
        c.bound();c.verify(d['inputs']);c.verify(d['sources'])
        strata={}
        for stratum in sorted({x['stratum'] for x in rows}):
            times={mode:sum(x['seconds'] for x in reports if x['phase']=='timing' and x['stratum']==stratum and x['mode']==mode) for mode in d['modes']}
            gain=1-times['reuse']/times['original']
            strata[stratum]=dict(seconds=times,runtime_gain_fraction=gain,local_material_gain_passed=gain>=d['minimum_material_gain_fraction'])
        first=sum(x['seconds']['original'] for x in strata.values());second=sum(x['seconds']['reuse'] for x in strata.values())
        gain=1-second/first
        c.commit(OUT/'results.json',dict(passed=True,utc=c.utc(),design_sha256=c.sha(DESIGN),outer_calls_attempted=calls,
            qualification_fixtures=len(rows),reports=reports,artifacts={x['path']:x['sha256'] for x in reports},
            exact_paired_all_scientific_outputs=True,unchanged_independent_physics_association_audits=True,
            reused_requests=sum(x['reused_requests'] for x in reports),strata=strata,overall_runtime_gain_fraction=gain,
            local_material_gain_passed=gain>=d['minimum_material_gain_fraction'],minimum_material_gain_fraction=d['minimum_material_gain_fraction'],
            archived_residual_differences=[v for x in reports for v in x['archival_residual_differences']],
            actual_hit_mutation_controls_source=str(b.OUT/'results.json'),new_trajectory_steps=0,new_saved_transport_steps=0,
            production_authorized=False,difficult_placement_transfer_qualified=False,transition_qualified=False,restart_qualified=False,full_path_qualified=False,
            claim='Exact fixed-pose implementation screen and local unprofiled costs only, conditioned on tiny actual-hit adversarial qualification. Sample is deliberately fallback-heavy. No campaign affordability, complete-path accuracy or shape/flow inference.'))
        c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))
        print('FULL_SCREEN_COMPLETE',calls,'gain',gain,c.sha(OUT/'results.json'),flush=True)
    except Exception as error:
        observed=b.failure_output(error);extra={}
        if observed is not None:
            path=OUT/'failed_call.json';c.commit(path,observed);extra[str(path)]=c.sha(path)
        c.commit(OUT/'failure.json',dict(passed=False,utc=c.utc(),error=repr(error),traceback=traceback.format_exc(),
            outer_calls_attempted=calls,completed=reports,artifacts=extra,new_trajectory_steps=0,production_authorized=False))
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
