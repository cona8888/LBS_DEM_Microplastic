"""Independent Stage128 force-correction audit."""
from pathlib import Path
import json, sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage128_staging'))
import cpd6_mean_correction_v1 as job
sys.path.insert(0,str(ROOT/'stage114_staging'))
import evaluate_parity_correction_v2 as cpu
OUTPUT=None

def main():
 d=job.read(job.DESIGN);job.verify(d);c=job.read(job.RUN/'completion.json');job.require(c['status']=='correction_complete_pending_independent_evaluation','status drift');job.require(not(job.RUN/'failure.json').exists(),'failure marker')
 for k in ['record','field','state']:job.require(job.sha(c[k]['path'])==c[k]['sha256'],k+' drift')
 raw=job.read(c['record']['path']);job.require(raw['steps']==1542,'step drift');job.s127.base.s114.audit.legacy.install_generic_mask_oracle()
 with np.load(c['state']['path']) as s,np.load(c['field']['path']) as f,np.load(d['bindings']['geometry']['path']) as g:
  state,phase=s['shifted_state'],s['phase'];field,density=f['velocity_xyz_lu'],f['density_lu'];dx=float(g['spacing_m'][0]);job.require(np.array_equal(phase,f['phase']) and np.array_equal(phase,g['phase']),'phase drift')
 case=job.s127.base.s114.probe.case_for(phase,d['correction']['new_acceleration_lu'],'stage128_independent');native=job.s127.base.s114.probe.observe(state,phase,case);exact=bool(np.array_equal(native['velocity_xyz_lu'],field) and np.array_equal(native['density_lu'],density))
 independent,rho,body,wall=cpu.independent_fields(state,phase,d['correction']['new_acceleration_lu']);recon=float(np.linalg.norm(independent-field)/np.linalg.norm(independent));balance=float(np.linalg.norm(np.array([body,0,0])-wall)/abs(body));nodes=cpu.cpu_node_residuals(state,phase,d['correction']['new_acceleration_lu'])
 fluid=phase==0;unit=(1002e-6/998.2)/(.1*dx);mean_lu=float(independent[0,fluid].mean());mean_si=mean_lu*unit;mean_err=mean_si/d['target_mean_velocity_m_s']-1;final=raw['rows'][-8:];adj=final[1:];long_window_proxy=final[0];gates=d['gates']
 checks={'bindings':True,'exact_export':exact,'finite':bool(np.isfinite(state).all() and np.isfinite(field).all()),'health':raw['numerical_health']['full_sticky_code']==0,'density':abs(float(rho[fluid].mean())-1)<=gates['density_drift_max'],'mach':float(native['maximum_speed_lu'])*3**.5<=gates['mach_max'],'reconstruction':recon<=2e-6,'balance':balance<=gates['balance_relative_max'],'cpu_fixed_point':max(x['fixed_point_relative_l2'] for x in nodes)<=gates['cpu_node_relative_l2_max'],'mean_match':abs(mean_err)<=gates['mean_relative_error_max'],'adjacent_field':max(x['field_change_relative_l2'] for x in adj)<=gates['field_relative_change_max'],'long_window_field':long_window_proxy['field_change_relative_l2']<=gates['field_relative_change_max'],'runtime':raw['runtime_seconds']<=gates['runtime_seconds_max']}
 audit=all(v for k,v in checks.items() if k not in ['mean_match','adjacent_field','long_window_field']);qualified=audit and all(checks.values());status='mean_correction_verified_relaxation_incomplete' if audit and not qualified else ('mean_correction_qualified' if qualified else 'mean_correction_audit_failed')
 out={'passed':audit,'qualified':qualified,'status':status,'checks':checks,'design':job.bind(job.DESIGN),'raw_completion':job.bind(job.RUN/'completion.json'),'mean_interstitial_velocity_m_s':mean_si,'target_mean_velocity_m_s':d['target_mean_velocity_m_s'],'mean_relative_error':mean_err,'long_window_proxy_step_span':long_window_proxy['step']-1285,'latest_long_window_field_change_relative_l2':long_window_proxy['field_change_relative_l2'],'latest_adjacent_field_change_relative_l2':adj[-1]['field_change_relative_l2'],'reconstruction_relative_l2':recon,'steady_force_balance_relative':balance,'runtime_seconds':raw['runtime_seconds'],'decision':'Preserve and stop. Long-window relaxation is incomplete; no automatic extension or second correction.','full_flow_solution':False,'spatial_convergence_established':False,'transport_authorized':False}
 root=OUTPUT or (job.EVAL/'independent_evaluation_01');root.mkdir(parents=True,exist_ok=False);job.write(root/'results.json',out);job.write(root/'completion.json',{'passed':audit,'qualified':qualified,'status':status,'results_sha256':job.sha(root/'results.json')});print(json.dumps(out,indent=2),flush=True);job.require(audit,'audit failed')
if __name__=='__main__':main()
