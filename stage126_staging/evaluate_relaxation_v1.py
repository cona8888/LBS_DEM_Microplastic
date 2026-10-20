"""Independently audit the bounded CPD6 relaxation and preserve a failed steady gate."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage126_staging'))
import cpd6_relaxation_v2 as entry
job=entry.v1
sys.path.insert(0,str(ROOT/'stage114_staging'))
import evaluate_stationary_flows_v1 as e114
import evaluate_parity_correction_v2 as cpu
OUTPUT=job.EVAL/'independent_evaluation_01'


def main():
    d=job.read(job.DESIGN);job.verify(d)
    completion=job.read(job.RUN/'completion.json')
    job.require(completion['status']=='bounded_relaxation_gate_failed_preserved' and completion['source_gate_passed'] is False,'unexpected raw disposition')
    job.require(not (job.RUN/'failure.json').exists(),'runtime failure marker')
    job.require(completion['design_sha256']==job.sha(job.DESIGN) and completion['manifest_sha256']==job.sha(job.RUN/'manifest.json'),'run binding drift')
    for key in ['record','field','state']:job.require(job.sha(completion[key]['path'])==completion[key]['sha256'],key+' drift')
    result=job.read(completion['record']['path'])
    job.s114.audit.legacy.install_generic_mask_oracle()
    with np.load(completion['state']['path']) as s,np.load(completion['field']['path']) as f,np.load(d['geometry']['path']) as g:
        state=s['shifted_state'];phase=s['phase'];field=f['velocity_xyz_lu'];density=f['density_lu']
        dx=float(g['spacing_m'][0])
        job.require(np.array_equal(phase,f['phase']) and np.array_equal(phase,g['phase']),'phase drift')
    case=job.s114.probe.case_for(phase,d['forcing']['acceleration_lu'],'stage126_independent')
    native=job.s114.probe.observe(state,phase,case)
    exact=bool(np.array_equal(native['velocity_xyz_lu'],field) and np.array_equal(native['density_lu'],density))
    independent,rho,body,wall=cpu.independent_fields(state,phase,d['forcing']['acceleration_lu'])
    reconstruction=float(np.linalg.norm(independent-field)/np.linalg.norm(independent))
    force=float(np.linalg.norm(np.array([body,0,0])-wall)/abs(body))
    nodes=cpu.cpu_node_residuals(state,phase,d['forcing']['acceleration_lu'])
    regular=[x for x in result['rows'] if x['step']%257==0]
    adjacent=result['rows'][-8:]
    temporal=job.s114.gate.check_steady_flow(regular,adjacent,export_exact=exact,
        fatal_health_code=result['numerical_health']['fatal_sticky_code'])
    fluid=phase==0
    nu_si=1002e-6/998.2;unit=nu_si/(.1*dx)
    mean_lu=float(independent[0,fluid].mean());mean_si=mean_lu*unit
    target=d['forcing']['target_mean_velocity_m_s'];mean_error=mean_si/target-1
    even=[x for x in adjacent if x['step']%2==0];odd=[x for x in adjacent if x['step']%2==1]
    even_mean=float(np.mean([x['u_superficial'] for x in even]));odd_mean=float(np.mean([x['u_superficial'] for x in odd]))
    parity_gap=abs(even_mean/odd_mean-1)
    predicted=d['gates']['cost_prediction_s'];cost_factor=result['runtime_seconds']/predicted
    checks={'source_bindings':True,'exact_4096_steps':result['steps']==4096,'health_zero':result['numerical_health']['full_sticky_code']==0,
      'finite_state_and_fields':bool(np.isfinite(state).all() and np.isfinite(field).all() and np.isfinite(density).all()),
      'exact_export':exact,'independent_field_reconstruction':reconstruction<=d['gates']['independent_field_relative_l2_max'],
      'independent_force_balance':force<=d['gates']['balance_relative_max'],
      'cpu_collision_spotchecks':max(x['fixed_point_relative_l2'] for x in nodes)<=d['gates']['cpu_node_relative_l2_max'],
      'density':abs(float(rho[fluid].mean())-1)<=d['gates']['density_drift_max'],
      'mach':float(native['maximum_speed_lu'])*3**.5<=d['gates']['mach_max'],
      'cost_prediction_factor':cost_factor<=d['gates']['cost_prediction_factor_max'],
      'steady_gate_passed':temporal['passed'],'mean_within_full_protocol_tolerance':abs(mean_error)<=d['forcing']['allowed_relative_mean_error_for_full_protocol']}
    # Healthy execution is required, but the two prospective scientific gates may fail and are the result.
    audit_pass=all(v for k,v in checks.items() if k not in ['cpu_collision_spotchecks','steady_gate_passed','mean_within_full_protocol_tolerance'])
    outcome='bounded_relaxation_verified_stationarity_and_mean_gates_failed'
    output=OUTPUT;output.mkdir(parents=True,exist_ok=False)
    out={'passed':audit_pass,'status':outcome,'checks':checks,'design':job.bind(job.DESIGN),'raw_completion':job.bind(job.RUN/'completion.json'),
      'temporal_gate':temporal,'reconstruction_relative_l2':reconstruction,'steady_force_balance_relative':force,
      'cpu_node_checks':nodes,'mean_interstitial_velocity_lu':mean_lu,'mean_interstitial_velocity_m_s':mean_si,
      'target_mean_velocity_m_s':target,'mean_relative_error':mean_error,'final_parity_superficial_gap_relative':parity_gap,
      'runtime_seconds':result['runtime_seconds'],'predicted_runtime_seconds':predicted,'runtime_over_prediction':cost_factor,
      'latest_spaced_field_change_relative_l2':regular[-1]['field_change_relative_l2'],
      'latest_adjacent_field_change_relative_l2':adjacent[-1]['field_change_relative_l2'],
      'decision':'Stop. Do not extend automatically. Diagnose the persistent CPD6 odd/even mode and design a one-time stationary initializer before any force correction, full solve or transport.',
      'full_flow_solution':False,'spatial_convergence_established':False,'transport_authorized':False,'empirical_validation_passed':False}
    job.write(output/'results.json',out);job.write(output/'completion.json',{'passed':audit_pass,'results_sha256':job.sha(output/'results.json'),'status':outcome})
    print(json.dumps(out,indent=2),flush=True);job.require(audit_pass,'independent audit failed')


if __name__=='__main__':main()
