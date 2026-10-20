"""Seal the failed campaign, evaluate the completed window, capture one failed solve.

No retry, advancement, tolerance change or repaired contact solve is performed.
"""
from pathlib import Path
import sys
import numpy as np
import verify_nonsmooth_windows_v1 as job

api,old,diag=job.api,job.old,job.diag
OUT=job.OUT.parent/'failure_audit_01'


def closure_details(args):
    v,M,J,f,z,A,g,dt,mu,steps,iterations,solver,extra=args
    reaction=J.T@f
    increment=M@reaction
    # Preserve the production order M@J.T@f as well; don't silently use a new
    # association of matrix multiplication when reconstructing the failure.
    production_increment=M@J.T@f
    velocity=v+production_increment
    restored=np.linalg.solve(M,velocity-v)
    error=np.linalg.norm(restored-reaction)
    denominator=max(np.linalg.norm(reaction),1e-30)
    B=np.linalg.inv(M)
    # Descriptive scale, NOT a replacement acceptance tolerance or certificate.
    subtraction_ulp_scale=np.linalg.norm(np.abs(B)@(np.spacing(np.abs(velocity))+np.spacing(np.abs(v))))
    stable_error=np.linalg.norm(np.linalg.solve(M,production_increment)-reaction)
    return {'solver':solver,'dt_s':float(dt),'contacts':len(g),'reaction_load_norm_N':float(np.linalg.norm(reaction)),
            'recovered_load_error_N':float(error),'old_relative_force_closure':float(error/denominator),
            'direct_increment_relative_closure':float(stable_error/denominator),
            'velocity_correction_norm_m_s':float(np.linalg.norm(production_increment)),
            'free_velocity_norm_m_s':float(np.linalg.norm(v)),
            'velocity_subtraction_ulp_load_scale_N':float(subtraction_ulp_scale),
            'error_over_descriptive_ulp_scale':float(error/max(subtraction_ulp_scale,1e-300)),
            'mobility_condition_number':float(np.linalg.cond(M)),
            'frozen_system':api.normalized({'free_velocity':v,'mobility':M,'jacobian':J,'reaction':f,'gaps':g,
                                          'dt_s':dt,'friction':mu,'tangential_steps':steps}),
            'no_acceptance_change':True}


def main():
    d=api.read(job.DESIGN);job.verify(d)
    api.require((job.RUN/'failure.json').exists(),'expected preserved campaign failure')
    inputs={str(p):api.sha(p) for p in job.RUN.rglob('*') if p.is_file()}
    inputs[str(job.DESIGN)]=api.sha(job.DESIGN)
    OUT.mkdir(parents=True,exist_ok=False)
    api.write(OUT/'manifest.json',{'scope':'read-only failed-run audit; at most one frozen-pose failed replay; no advancement or changed acceptance',
              'inputs':inputs,'auditor_sha256':api.sha(__file__)})
    prefix=[]
    for wi,w in enumerate(d['windows']):
        spec,binding,before=job.setup(d,wi)
        paths=sorted((job.RUN/w['id']).glob('segment_[0-9][0-9].json'))
        for n,p in enumerate(paths,1):
            api.require(p.name==f'segment_{n:02d}.json','contiguous segment ledger')
            r=api.read(p);seal=api.read(p.with_suffix('.seal.json'))
            api.require(seal['record_sha256']==api.sha(p) and seal['design_sha256']==api.sha(job.DESIGN),'record seal')
            api.require(r['input_checkpoint_sha256']==api.digest(before) and r['spec']==spec,'record lineage')
            check=old.parent.prior.s.check_record(r,before,spec,job.model.binding_for(binding,True))
            api.require(check['passed'],'accepted prefix integrity')
            api.require(r['result']['rejected']==before['state']['rejected'],'no new rejected trials')
            prefix.append({'window':w['id'],'segment':n,'accepted_steps':len(r['rows']),'status':r['result']['status'],
                           'reason':r['result']['reason'],'time_s':r['result']['time_s'],'accepted_prefix_checks':check})
            before=r['result']['checkpoint']
        if wi==1:
            failed=r;failed_spec=spec
            api.require(r['result']['status']=='numerical_failure' and r['result']['reason']=='direct contact force closure failed','specific terminal failure')
        else:api.require(r['result']['status']=='present_at_horizon','engagement completed')
    old.parent.configure();spec=d['base_spec'];field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    recs=job.records(d,0);impulses=job.collect_impulses(d,0,recs,field,geometry)
    engagement=job.summary(d,0,recs,impulses)
    api.write(OUT/'completed_engagement_impulses.json',impulses,raw=True)
    original=old.hot.s50._finish
    original_compiled=old.hot.PRIMARY.__globals__['_finish']
    captured=[]
    def observe(*args,**kwargs):
        detail=closure_details(args)
        try:return original(*args,**kwargs)
        except RuntimeError as e:
            detail['raised']=str(e);captured.append(detail)
            raise
    old.hot.s50._finish=observe
    old.hot.PRIMARY.__globals__['_finish']=observe
    failure=None
    try:
        with old.hot.scope(),old.engine.runtime.repair_scope():
            diag.replay(field,geometry,failed_spec,failed['result']['checkpoint']['state'],failed['rows'][-1]['dt_s'])
    except RuntimeError as e:failure=str(e)
    finally:
        old.hot.s50._finish=original
        old.hot.PRIMARY.__globals__['_finish']=original_compiled
    api.require(failure=='direct contact force closure failed' and captured,'failed frozen pose reproduced')
    api.verify_mapping(inputs);job.verify(d)
    result={'audit_integrity_passed':True,'campaign_passed':False,'completed_windows':1,'required_windows':2,
            'completed_engagement':engagement,'accepted_prefix_ledger':prefix,'failed_solve_reproduced':True,
            'captured_failures':captured,'failure_time_s':failed['result']['time_s'],
            'interpretation':'The force-closure test subtracts two nearly equal velocities and normalizes by the disappearing contact reaction. Compare the recorded roundoff scales before designing a prospective numerical certificate; this audit does not change the gate or accept the failed step.',
            'no_restart':True,'no_changed_tolerance':True,'no_advancement':True,'production_promotion':False,
            'design_sha256':api.sha(job.DESIGN),'auditor_sha256':api.sha(__file__),
            'inputs':inputs,'impulse_artifact_sha256':api.sha(OUT/'completed_engagement_impulses.json')}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'audit_integrity_passed':True,'campaign_passed':False})
    print('FAILED CAMPAIGN AUDIT PASS; ENGAGEMENT',engagement['passed'],engagement['checks'],flush=True)
    print('CLOSURE DIAGNOSTIC',[{k:v for k,v in c.items() if k!='frozen_system'} for c in captured],flush=True)


if __name__=='__main__':main()
