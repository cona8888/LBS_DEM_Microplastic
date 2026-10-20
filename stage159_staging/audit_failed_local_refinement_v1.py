"""Seal the failed local experiment without restarting or extending it."""
import numpy as np
import local_impact_refinement_v1 as v
from audit_local_refinement_v1 import l1_merge


def main():
    api=v.api;d=api.read(v.DESIGN);v.verify(d)
    api.require(api.read(v.RUN/'failure.json')['error']=="RuntimeError('local scientific gate failed')",'specific scientific stop')
    api.require(not (v.RUN/'release').exists(),'second window not dispatched after failure')
    artifacts={str(p):api.sha(p) for folder in [v.RUN,v.OUT] for p in folder.rglob('*') if p.is_file()}
    out=v.OUT.parent/'failure_audit_01';out.mkdir(exist_ok=False)
    api.write(out/'manifest.json',{'inputs':artifacts,'design_sha256':api.sha(v.DESIGN),
                                 'auditor_sha256':api.sha(__file__),'time_advancement':False})
    wi=0;w=d['windows'][wi];folder=v.RUN/w['id']
    spec,binding,cp=v.seed_setup(d,wi);seed=v.read(folder/'seed.json');v.check(seed,cp,spec,binding)
    expected=api.read(v.source_path(w,w['next_segment']))['rows'][:d['entries'][wi]['steps']]
    api.require(seed['rows']==expected,'exact entry prefix')
    spec,binding,cp=v.setup(d,wi,v.FACTORS[-1],'preflight')
    full,first,last=[v.read(folder/f'preflight_{x}.json') for x in ['full','first','last']]
    v.check(full,cp,spec,binding);v.check(first,cp,spec,binding);v.check(last,first['result']['checkpoint'],spec,binding)
    api.require(len(full['rows'])==100 and len(first['rows'])==37 and len(last['rows'])==63,'restart counts')
    api.require(full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state'],'exact restart')
    recs=[v.joined(d,wi,f) for f in v.FACTORS]
    v.old.parent.configure();spec=d['base_spec'];field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=v.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    imp=api.read(v.OUT/'engagement_impulses.json');repeat=v.impulses(d,wi,recs,field,geometry)
    api.require(repeat==imp,'repeated independent frozen-pose replay')
    raw_totals=[]
    for level in imp['levels']:
        total=np.array([sum(s['impulse_generalized'][k]*s['overlap_s']/s['dt_s'] for s in level['samples']) for k in range(6)])
        api.require(np.allclose(total,level['total_impulse'],rtol=1e-13,atol=1e-30),'independent component impulse sum')
        raw_totals.append(total)
    errors=[float(np.linalg.norm(np.linalg.solve(np.array(imp['mass_at_entry']),x-raw_totals[-1]))/imp['U']) for x in raw_totals[:-1]]
    api.require(np.allclose(errors,imp['to_finest'],rtol=1e-10,atol=1e-13),'independent impulse metric')
    summary=v.summary(d,wi,recs,imp);api.require(summary==api.read(v.OUT/'engagement_summary.json'),'recomputed failed outcome')
    independent=[l1_merge(x['rows'],recs[-1]['rows'],seed['result']['time_s'],w['horizon_s'],imp['U']) for x in recs[:-1]]
    api.require(np.allclose(independent,summary['whole_L1_to_finest'],rtol=1e-12,atol=1e-14),'independent interval integration')
    metrics={}
    for key,limit in d['accuracy']['limits'].items():
        coarse,fine=[x[key] for x in summary['endpoint_errors']]
        metrics[key]={'coarse_adjacent_error':coarse,'fine_adjacent_error':fine,'fine_over_coarse':fine/coarse,
                      'absolute_limit':limit,'fine_error_over_limit':fine/limit,'absolute_limit_pass':fine<=limit,
                      'refinement_pass':fine<=d['accuracy']['error_reduction_ratio_max']*coarse or max(coarse,fine)<d['accuracy']['noise_floor']}
    api.require(not summary['passed'] and not summary['checks']['endpoints'] and all(x['absolute_limit_pass'] for x in metrics.values()),'specific refinement failure')
    api.verify_mapping(artifacts);v.verify(d)
    result={'audit_integrity_passed':True,'scientific_gates_passed':False,'completed_cases':3,'planned_cases':6,
            'failure_kind':'Endpoint adjacent-error reduction, not an absolute-error or runtime-health failure.',
            'endpoint_details':metrics,'completed_engagement':summary,'independent_L1':independent,
            'independent_impulse_errors':errors,'impulse_replay_calls':repeat['calls'],
            'field_and_initial_state_conditional':True,'time_advancement':False,'production_promotion':False,
            'next':'Keep the failed verdict. Assess phase-sensitive convergence and a prospective state-based local refinement rule before another campaign; do not repeatedly decrease global dt or relax the failed protocol.',
            'artifacts':artifacts,'design_sha256':api.sha(v.DESIGN),'auditor_sha256':api.sha(__file__)}
    api.write(out/'results.json',result,raw=True);api.write(out/'completion.json',{'results_sha256':api.sha(out/'results.json'),'audit_integrity_passed':True,'scientific_gates_passed':False})
    print('FAILED EXPERIMENT AUDIT PASS',metrics,flush=True)


if __name__=='__main__':main()
