"""Independent terminal audit for the Stage196 runtime-gate blocker; zero steps."""
from pathlib import Path
from collections import Counter
import os, psutil, shutil, traceback
import probe_compiled_contact_v1 as probe
job,api,q=probe.job,probe.api,probe.q
ROOT=probe.ROOT;OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/work_window_close_02'


def semismooth_counts(rec):
    values=[]
    def visit(node):
        if isinstance(node,dict):
            if 'semismooth_nfev' in node:values.append(int(node['semismooth_nfev']))
            for value in node.values():
                if isinstance(value,(dict,list)):visit(value)
        elif isinstance(node,list):
            for value in node:
                if isinstance(value,(dict,list)):visit(value)
    visit(rec)
    return {'metadata_occurrences_including_repeated_evidence':len(values),'maximum':max(values) if values else None,
        'frequency':dict(sorted(Counter(values).items())),'caveat':'Repeated evidence may duplicate the same solve; these are not unique solver-call counts.'}


def run():
    w=api.read(probe.inherited.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'authorized final audit clock')
    d=api.read(probe.PROTOCOL);probe.verify(d)
    r=api.read(probe.OUT/'results.json');api.require(api.read(probe.OUT/'completion.json')['results_sha256']==api.sha(probe.OUT/'results.json'),'compiled measurement seal')
    api.verify_mapping(r['artifacts'])
    info=probe.inherited.affinity.bind(14);OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'source_sha256':api.sha(__file__),'new_trajectory_steps':0,'owned_affinity':info})
    try:
        api.require(not r['passed'] and r['new_accepted_steps']==5185 and r['window_new_accepted_steps']==35426,'compiled incomplete accounting')
        path=probe.RUN/'record.json.xz';record=q.independent_file(path,api.sha(probe.PROTOCOL))
        decoded,state=job.codec.read_record(path,api.sha(probe.PROTOCOL))
        api.require(job.codec.base.raw_bytes(decoded)==job.codec.base.raw_bytes(record),'independent compressed, raw, full history and logical seals')
        case=next(c for c in d['cases'] if c['id']==d['stress_case'])
        seed=q.independent_file(Path(d['stress_seed_raw']),api.sha(d['stress_seed_design']))
        before=job.parent.model.checkpoint(case['spec'],job.binding(d,case),seed['result']['checkpoint'],True)
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            import qualify_repaired_stack_v1 as prior
            summary=job.kernel.evaluate(record,case['spec'],job.binding(d,case),before,prior.geometry(),api.sha(probe.PROTOCOL),d['minimum_gap_semantics'])
        trim=lambda x:{k:v for k,v in x.items() if k!='audit_seconds'}
        api.require(summary['passed'] and not summary['complete_observation'] and trim(summary)==trim(r['audit']),'independent exact health, clock, balance and step summary')
        api.require(record['step_cap']==10000 and record['result']['status']=='incomplete_budget' and record['result']['rejected']==0 and len(record['rows'])==5185,'retain incomplete requested observation')
        previous=q.independent_file(Path(d['earlier_incomplete_probe']),api.sha(probe.inherited.job.DESIGN))
        api.require(record['rows'][:4915]==previous['rows'],'all prior 4915 accepted rows exactly unchanged')
        steps={'instrumented_profile_incomplete':326,'combined_exact_segments':8000,'performance_core_full_stack':17000,
            'original_long_contact_incomplete':4915,'compiled_contact_incomplete':5185}
        api.require(sum(steps.values())==35426<w['maximum_new_qualification_accepted_steps'],'resolved accepted-step ledger')
        roots=[ROOT/'stage196_runs/deadline_recovery_20260925/segment_profile_01',
            Path('D:/MATDEM_MICROPLASTIC/stage196_runs/deadline_recovery_20260925/combined_segments_01'),
            probe.inherited.job.PREFLIGHT,Path(d['earlier_incomplete_probe']).parent,probe.RUN]
        owned=[]
        for root in roots:
            launch=root/'launch.json'
            if launch.exists():owned.append(api.read(launch)['pid'])
        api.require(not any(psutil.pid_exists(x) for x in owned),'all diagnostic/preflight supervisors retired')
        other=[]
        for process in psutil.process_iter(['pid','name','cmdline']):
            if process.pid!=os.getpid() and 'python' in (process.info['name'] or '').lower() and 'matdem_microplastic' in ' '.join(process.info['cmdline'] or []).lower():other.append(process.info)
        api.require(not other,'no owned simulation/audit workers remain except this zero-step closure')
        api.require(not probe.inherited.job.RUN.exists(),'no Stage196 production output')
        inputs=[probe.PROTOCOL,probe.OUT/'results.json',probe.OUT/'completion.json',Path(__file__),
            ROOT/'stage196_evaluations/performance_stack_20260925/independent_readiness_01/results.json',
            OUT.parent/'deadline_blocker_01/results.json',OUT.parent/'compiled_pair_02/results.json',OUT.parent/'compiled_pair_03/results.json',
            probe.inherited.WORK,path,path.with_suffix('.seal.json'),OUT.parent/'work_window_close_01/failure.json']
        for item in inputs[4:8]:
            seal=item.parent/'completion.json'
            api.require(api.read(seal)['results_sha256']==api.sha(item),'each prior closure sealed')
        horizon=case['spec']['horizon_s'];margin=w['preserve_runtime_margin'];sim=r['simulated_seconds']
        available=(job.policy.utc(w['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
        compute_h=r['compute_seconds']/sim*horizon*margin/3600
        transaction_h=r['transaction_seconds']/sim*horizon*margin/3600
        result={'closure_audit_passed':True,'campaign_ready':False,'deadline_gate_passed':False,'new_trajectory_steps':0,
            'stop_reason':'Both long repaired-contact calls remain incomplete at the original per-call runtime budget; no independently qualified full-campaign deadline fit.',
            'preserved_closure_v1_failure':'Zero-step audit indexing included the work contract in the result/completion-seal loop. v2 checks the four result/completion pairs explicitly; no raw evidence or numerical gate changed.',
            'window_steps':steps,'window_accepted_steps':35426,'unused_step_budget':w['maximum_new_qualification_accepted_steps']-35426,
            'unresolved_reservations':[],'compiled_accepted_prefix_numerical_audit':summary,'exact_original_prefix_rows':4915,
            'compiled_compute_only_hours_if_measured_regime_persists_with_margin':compute_h,
            'compiled_transaction_hours_if_measured_regime_persists_with_margin':transaction_h,'remaining_simulation_hours':available,
            'forecast_caveat':'Measured-regime conservative extrapolation, not a hard runtime lower bound or a complete production resource qualification.',
            'solver_effort_metadata':semismooth_counts(record),'all_owned_workers_retired':True,'production_launched':False,
            'physics_timesteps_horizons_numerical_gates_unchanged':True,'full_path_observations':0,
            'compiled_v3_status':'462 held-call and 3696 bitwise checks only; no trajectory/full-stack qualification, not adopted',
            'isolated_new_numba_packages':'Retained unused; original solver compiler versions were used, existing environment not replaced.',
            'free_disk_bytes':{'C':shutil.disk_usage(ROOT).free,'D':shutil.disk_usage(probe.RUN).free},
            'final_audit_deadline_unchanged':w['final_audit_deadline_utc'],'stop_utc':job.utc().isoformat(),
            'old_failed_evidence_preserved':True,'master_plan_not_updated':True,'inputs':{str(x):api.sha(x) for x in inputs},
            'next_decision':'Review a separately qualified solver-strategy change or obtain a deadline extension; do not reduce the six cases or horizons, relax gates, or promote incomplete runs.'}
        api.verify_mapping(result['inputs']);probe.verify(d)
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('STAGE196_TERMINAL_CLOSURE',35426,'no_workers','compute_h',compute_h,'transaction_h',transaction_h,'remaining_h',available,flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise


if __name__=='__main__':run()
