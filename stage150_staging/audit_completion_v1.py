"""Independent seal, bundle and operational-budget audit; no trajectory writes."""
from pathlib import Path
import sys
import full_horizon_sensitivity_v1 as run

api=run.api
OUT=run.ROOT/'stage150_evaluations'/run.BASE/'independent_audit_01'


def main():
    d=api.read(run.DESIGN);run.verify(d)
    ev=api.read(run.OUT/'results.json');seal=api.read(run.OUT/'completion.json')
    api.require(ev['passed'] and seal['passed'] and api.sha(run.OUT/'results.json')==seal['results_sha256'],'evaluation seal')
    api.verify_mapping(ev['artifact_hashes'])
    dispatch=api.read(run.RUN/'dispatch_completion.json')
    api.require(dispatch['all_workers_exited'] and dispatch['return_codes']==[0,0,0,0],'worker completion')
    api.require(not list(run.RUN.rglob('failure.json')),'failure marker')
    segments=[];counts={}
    for c in d['cases']:
        folder=run.RUN/c['id'];worker=api.read(folder/'results.json')
        api.require(worker['passed'] and worker['completed_horizon'] and not worker['failure'],'case completion')
        api.require((run.RUN/(c['id']+'.stderr.txt')).stat().st_size==0,'stderr not empty')
        api.require(worker['wall_s']<=d['budget']['case_wall_s'],'case budget')
        total=0
        for item in worker['segments']:
            p=Path(item['path']);r=api.read(p);result=r['result']
            api.require(api.sha(p)==item['sha256']==api.read(p.parent/'completion.json')['record_sha256'],'record seal')
            api.require(r['design_sha256']==api.sha(run.DESIGN),'record design')
            api.require(result['checkpoint']['state_sha256']==api.digest(result['checkpoint']['state']),'checkpoint state')
            api.require(r['checks']['passed'] and r['checks']['contact_certificates']['all_passed'],'segment checks')
            api.require(r['checks']['contact_certificates']['legacy_energy_gate_violations']==0,'legacy energy allowance')
            total+=r['checks']['contact_certificates']['count']
            segments.append({'case':c['id'],'record':str(p),'runtime_s':result['runtime_seconds'],
                             'within_declared_40s':result['runtime_seconds']<=d['budget']['segment_wall_s'],
                             'within_effective_45s':result['runtime_seconds']<=45.})
        api.require(result['time_s']==c['spec']['horizon_s'] and result['status']=='present_at_horizon','exact horizon')
        counts[c['id']]=total
    # The pre-existing observer wrapper literally passes 45 s; do not rewrite
    # its frozen source or pretend the Stage150 declaration of 40 was applied.
    wrapper=Path(run.engine.runtime.previous.__file__)
    effective_source=wrapper.read_text(encoding='utf-8')
    api.require('api.execute(spec, bound, 45.' in effective_source,'effective budget diagnosis drift')
    OUT.mkdir(parents=True,exist_ok=False)
    result={'scientific_checks_passed':True,'sources_and_bundles_unchanged':True,'no_failures':True,
            'all_new_cases_horizon_s':d['cases'][0]['spec']['horizon_s'],'contact_certificate_counts':counts,
            'operational_protocol_exact':all(s['within_declared_40s'] for s in segments),
            'budget_discrepancy':'The design says 40-s segments but the inherited observer wrapper passes 45 s. This is an implementation discrepancy, not a physical acceptance-limit change. Original records and design preserved; no rerun or retrospective relabelling.',
            'effective_runtime_wrapper':{'path':str(wrapper),'sha256':api.sha(wrapper),'effective_cooperative_wall_budget_s':45.},
            'all_segments_within_effective_45s':all(s['within_effective_45s'] for s in segments),
            'segments':segments,'claim':d['claim_boundary'],'design_sha256':api.sha(run.DESIGN),
            'evaluation_sha256':api.sha(run.OUT/'results.json'),'audit_source_sha256':api.sha(__file__)}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')})
    print('SCIENTIFIC_PASS',True,'OPERATIONAL_PROTOCOL_EXACT',result['operational_protocol_exact'],'CERTIFICATES',counts,flush=True)


if __name__=='__main__':main()
