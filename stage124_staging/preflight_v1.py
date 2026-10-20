"""Bounded adapter tests, including actual identity integration and fail-closed guards."""
import copy
import hashlib
import numpy as np
import mean_offset_diagnostic_v1 as job
api=job.api
def main():
    d=api.read(job.DESIGN);job.verify(d);tests={}
    f,g,m=job.ORIGINAL_LOAD(2,1.,2);scaled,gs,ms=job.diagnostic_load(2,1.,2)
    ratio=ms['stage124_diagnostic']['scale'];before=hashlib.sha256(f.u.tobytes()).hexdigest()
    tests['mask_unchanged']=np.array_equal(f.fluid,scaled.fluid)
    tests['geometry_unchanged']=all(np.array_equal(g[k],gs[k]) for k in g)
    tests['native_velocity_exactly_scaled']=np.array_equal(scaled.u,f.u*ratio)
    tests['mean_matched']=abs(scaled.u[0,scaled.fluid].mean()/ms['achieved_mean_interstitial_velocity_m_s']-1)<1e-12
    tests['solid_velocity_zero']=not np.any(scaled.u[:,~scaled.fluid])
    points=[c['spec']['initial_state']['position_m'] for c in d['cases']]+[[0.,0.,0.],list(np.asarray(f.u.shape[1:])*f.dx)]
    tests['interpolated_velocity_scaled']=all(np.allclose(scaled.sample(p)[0],f.sample(p)[0]*ratio,rtol=1e-12,atol=1e-18) for p in points)
    tests['interpolated_gradient_scaled']=all(np.allclose(scaled.sample(p)[1],f.sample(p)[1]*ratio,rtol=1e-12,atol=1e-14) for p in points)
    for name,args in [('seed',(1,1.,2)),('cpd',(2,1.,4)),('flow',(2,2.,2))]:
        try:job.diagnostic_load(*args);tests[name+'_guard']=False
        except RuntimeError:tests[name+'_guard']=True
    try:
        with job.loader_scope():raise ValueError('test restoration')
    except ValueError:tests['loader_restored_on_exception']=api.fields.load is job.ORIGINAL_LOAD
    original=copy.deepcopy(job.inherited_cases()[0]['spec'])
    bound='Stage124 identity test; no production contract'
    r0,rows0=job.repaired.execute(original,bound,pause=3)
    with job.loader_scope(job.ORIGINAL_LOAD):r1,rows1=job.repaired.execute(original,bound,pause=3)
    tests['identity_integration_checkpoint_exact']=r0['checkpoint']==r1['checkpoint']
    tests['identity_integration_intervals_exact']=rows0==rows1
    tests['source_array_unchanged']=hashlib.sha256(f.u.tobytes()).hexdigest()==before
    tests['metadata_declares_counterfactual']=ms['normalization_to_target_applied'] and not ms['particle_transport_authorized'] and ms['stage124_diagnostic']['role']=='mean_speed_offset_attribution_only'
    try:job.execute(original,bound,pause=1);tests['explicit_opt_in_guard']=False
    except RuntimeError:tests['explicit_opt_in_guard']=True
    out=job.PREFLIGHT.parent;out.mkdir(parents=True,exist_ok=False)
    api.write(out/'identity_records.json',{'original':r0,'identity_adapter':r1,'original_intervals':rows0,'identity_intervals':rows1},raw=True)
    result={'passed':all(tests.values()),'tests':tests,'design_sha256':api.sha(job.DESIGN),'scale':ratio,'identity_records_sha256':api.sha(out/'identity_records.json')}
    api.write(job.PREFLIGHT,result);api.write(out/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(job.PREFLIGHT)})
    print('PREFLIGHT',result['passed'],len(tests),'checks',ratio,flush=True)
    return 0 if result['passed'] else 4
if __name__=='__main__':raise SystemExit(main())
