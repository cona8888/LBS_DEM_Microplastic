"""Independent immutable chain audit and raw cross-phase comparison."""
import numpy as np
import phase_grid_probe_v1 as v


def main():
    api=v.api;d=api.read(v.DESIGN);v.verify(d);r=api.read(v.OUT/'results.json')
    api.require(api.read(v.OUT/'completion.json')['results_sha256']==api.sha(v.OUT/'results.json'),'completion seal')
    api.verify_mapping(r['artifacts']);api.require(not (v.RUN/'failure.json').exists(),'no failure')
    f=d['factors'][0];spec,binding,cp=v.setup(d,f,1.,'identity');identity=v.read(v.RUN/'identity.json')
    v.v.check(identity,cp,spec,binding)
    original=v.v.joined(api.read(v.v.DESIGN),0,f)
    api.require(identity['rows']==original['rows'][:100],'identity')
    phase=v.PHASES[0];spec,binding,cp=v.setup(d,f,phase,'restart')
    full,first,last=[v.read(v.RUN/f'restart_{x}.json') for x in ['full','first','last']]
    v.v.check(full,cp,spec,binding);v.v.check(first,cp,spec,binding);v.v.check(last,first['result']['checkpoint'],spec,binding)
    api.require(len(full['rows'])==100 and len(first['rows'])==37 and len(last['rows'])==63,'restart counts')
    api.require(full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state'],'exact restart')
    saved=v.model.original.INTEGRATE
    try:
        with v.phase_scope(cp['state']['steps'],phase):raise RuntimeError('scope test')
    except RuntimeError:pass
    api.require(v.model.original.INTEGRATE is saved,'phase scope restoration')
    all_cases=[{**v.v.joined(api.read(v.v.DESIGN),0,f),'factor':f,'phase':1.} for f in d['factors']]
    reference=all_cases[-1];reference_imp=api.read(v.v.OUT/'engagement_impulses.json');reports=[]
    v.old.parent.configure();spec=d['base_spec'];field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=v.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    for f in d['factors']:
        for phase in v.PHASES:
            rec=v.joined(d,f,phase);imp=api.read(v.OUT/(v.case_id(f,phase)+'_impulses.json'))
            api.require(v.impulse(d,rec,field,geometry)==imp,'independent impulse replays')
            totals=np.array([sum(s['impulse_generalized'][k]*s['overlap_s']/s['dt_s'] for s in imp['samples']) for k in range(6)])
            api.require(np.allclose(totals,imp['total_impulse'],rtol=1e-13,atol=1e-30),'independent component impulse sum')
            reports.append(v.case_metrics(d,rec,reference,imp,reference_imp));all_cases.append(rec)
    api.require(reports==r['new_cases'] and all(x['passed'] for x in reports),'recomputed primary checks')
    cfg=d['base_spec']['config'];checks={}
    for key,label,scale in [('position_m','position_over_b',cfg['prolate_semiaxes_m'][1]),('orientation','axis_vector_norm',1.),('velocity_generalized','generalized_velocity_relative',cfg['target_mean_interstitial_velocity_m_s'])]:
        groups=[[np.array(rec['rows'][-1][key]) for rec in all_cases if rec['factor']==f] for f in d['factors']]
        within=[max(float(np.linalg.norm(x-y)/scale) for x in group for y in group) for group in groups]
        cross=[max(float(np.linalg.norm(x-y)/scale) for x in a for y in b) for a,b in zip(groups,groups[1:])]
        expected=r['endpoint_phase_envelopes'][label]
        api.require(np.allclose(within,expected['within_level_diameters'],rtol=1e-5,atol=1e-12) and np.allclose(cross,expected['adjacent_cross_phase_envelopes'],rtol=1e-5,atol=1e-12),'independent raw envelope')
        checks[label]={'cross_phase_envelopes':cross,'ratio':cross[1]/cross[0],'contracts':cross[1]<=.8*cross[0]}
    v.verify(d)
    out=v.OUT.parent/'independent_audit_01';out.mkdir(exist_ok=False)
    result={'audit_integrity_passed':True,'all_primary_budgets_passed':True,'independent_envelopes':checks,
            'all_endpoint_envelopes_contract':all(x['contracts'] for x in checks.values()),
            'evaluation_sha256':api.sha(v.OUT/'results.json'),'auditor_sha256':api.sha(__file__),
            'prior_stage159_passed':False,'production_promotion':False,'full_window_accuracy':False}
    api.write(out/'results.json',result);api.write(out/'completion.json',{'results_sha256':api.sha(out/'results.json'),'audit_integrity_passed':True})
    print('PHASE AUDIT PASS',result,flush=True)


if __name__=='__main__':main()
