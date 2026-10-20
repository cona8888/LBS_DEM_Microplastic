"""Freeze and run one bounded CPD4-initialized CPD6 relaxation diagnostic."""
from __future__ import annotations

import argparse
import gc
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage125_staging'))
import spatial_cost_v1 as s125
sys.path.insert(0, str(ROOT/'stage114_staging'))
import requalify_stationary_flows_v1 as s114

STUDY='cpd6_bounded_relaxation_20260916'
DESIGN=ROOT/'stage126_designs'/STUDY/'design_01.json'
RUN=ROOT/'stage126_runs'/STUDY/'gpu_relaxation_01'
EVAL=ROOT/'stage126_evaluations'/STUDY
read,write,require,bind,sha=s114.audit.read,s114.write,s114.require,s114.bind,s114.audit.sha


def verify(d):
    s114.verify_bindings(d['bindings'])
    require(d['controls']=={'tau':.8,'nu_lu':.1,'threads':256,'steps':4096,'sample_interval':257,'final_consecutive':8},'controls changed')
    require(d['authority']['bounded_gpu_relaxation'] and not d['authority']['full_flow_solution'] and not d['authority']['transport'],'authority drift')


def prepare():
    require(not DESIGN.parent.exists(),'immutable design exists')
    stage125=ROOT/'stage125_evaluations/third_grid_cost_20260916/completion.json'
    c125=read(stage125)
    require(c125['status']=='geometry_and_cost_verified_full_spatial_solve_still_gated','Stage125 absent')
    for p,h in c125['artifacts'].items():require(sha(p)==h,'Stage125 drift '+p)
    d114=read(s114.DESIGN);s114.verify_design(d114)
    e114=ROOT/'stage114_evaluations/stationary_flow_requalification_20260915/independent_evaluation_01/results.json'
    r114=read(e114);require(r114['passed'],'Stage114 failed')
    spec4=next(x for x in d114['cases'] if x['cpd']==4)
    row4=next(x for x in r114['cases'] if x['cpd']==4)
    s114.verify_bindings(row4['bundle'])
    geometry=ROOT/'stage125_designs/third_grid_cost_20260916/geometry_cpd6.npz'
    with np.load(geometry) as g: dx6=float(g['spacing_m'][0]); length=float(g['cell_length_m'][0])
    dx4=float(row4['spacing_m']); target_si=float(row4['mean_interstitial_velocity_m_s'])
    nu_si=d114['physical_fluid']['dynamic_viscosity_Pa_s']/d114['physical_fluid']['density_kg_m3']
    speed6=nu_si/(.1*dx6); target_lu=target_si/speed6
    accel=float(np.float32(spec4['acceleration_lu']*(dx6/dx4)**3))
    field4=Path(row4['bundle']['final_fields.npz']['path'])
    bindings={'stage125_seal':bind(stage125),'stage125_design':bind(ROOT/'stage125_designs/third_grid_cost_20260916/design_01.json'),
      'geometry_cpd6':bind(geometry),'stage114_design':bind(s114.DESIGN),'stage114_evaluation':bind(e114),
      'cpd4_field':bind(field4),'cpd4_state':row4['bundle']['final_shifted_state.npz'],
      'runner':bind(__file__),'probe':bind(s114.probe.__file__),'steady_gate':bind(s114.gate.__file__),
      'audit':bind(s114.audit.__file__),'cuda_source':d114['lineage']['cuda_source']}
    design={'schema':'matdem.stage126.cpd6-bounded-relaxation.v1','created_utc':datetime.now(timezone.utc).isoformat(),
      'question':'Does a CPD4-initialized CPD6 field approach the qualified stationary gates within a bounded 4096-step diagnostic?',
      'claim_boundary':'Convergence-rate diagnostic only. Passing does not establish spatial convergence, matched-mean particle response, permeability validation or release.',
      'bindings':bindings,'qualified_ptx_sha256':d114['lineage']['qualified_ptx_sha256'],
      'geometry':{'cpd':6,'path':str(geometry),'shape_zyx':[279]*3,'spacing_m':dx6,'cell_length_m':length},
      'forcing':{'acceleration_lu':accel,'rule':'accepted CPD4 acceleration times (dx6/dx4)^3','target_mean_velocity_m_s':target_si,
                 'target_mean_velocity_lu':target_lu,'allowed_relative_mean_error_for_full_protocol':.0005},
      'initializer':{'mode':'resampled CPD4 local equilibrium; initialization only','field':bind(field4),
                     'velocity_scale':target_lu/float(row4['mean_interstitial_velocity_lu']),
                     'density_deviation_scale':accel/spec4['acceleration_lu']},
      'controls':{'tau':.8,'nu_lu':.1,'threads':256,'steps':4096,'sample_interval':257,'final_consecutive':8},
      'gates':{'field_relative_change_max':5e-5,'balance_relative_max':.005,'density_drift_max':5e-6,'mach_max':.05,
               'independent_field_relative_l2_max':2e-6,'cpu_node_relative_l2_max':5e-5,
               'wall_budget_s':1800,'cost_prediction_s':4096*.29911353898048354,'cost_prediction_factor_max':1.35},
      'decision':{'pass':'Eligible for separate force correction/full solve design; not transport.',
                  'fail':'Preserve and stop; do not extend automatically.','incomplete':'Preserve and stop.'},
      'authority':{'bounded_gpu_relaxation':True,'full_flow_solution':False,'force_correction':False,'transport':False,
                   'population':False,'empirical_validation':False}}
    verify(design);DESIGN.parent.mkdir(parents=True);write(DESIGN,design)
    print(json.dumps({'design':str(DESIGN),'sha256':sha(DESIGN),'predicted_minutes':design['gates']['cost_prediction_s']/60}),flush=True)


def preflight():
    d=read(DESIGN);verify(d)
    with np.load(d['geometry']['path']) as g: phase=g['phase']
    with np.load(d['initializer']['field']['path']) as f:
        rho=f['density_lu'];velocity=f['velocity_xyz_lu']
    target=phase.shape
    resampled_rho=s114.audit.legacy.resample_cell_centered_field(rho,target)
    resampled_velocity=np.stack([s114.audit.legacy.resample_cell_centered_field(velocity[i],target) for i in range(3)])
    resampled_velocity*=np.float32(d['initializer']['velocity_scale'])
    resampled_rho=np.float32(1)+np.float32(d['initializer']['density_deviation_scale'])*(resampled_rho-np.float32(1))
    initial=s114.audit.legacy.local_equilibrium_shifted_state(phase,resampled_rho,resampled_velocity,d['forcing']['acceleration_lu'])
    case=s114.probe.case_for(phase,d['forcing']['acceleration_lu'],'stage126_preflight')
    obs=s114.probe.observe(initial,phase,case);fluid=phase==0
    checks={'shape':initial.shape==(19,*target),'finite':np.isfinite(initial).all(),'solids_zero':all(not np.any(initial[q][~fluid]) for q in range(19)),
      'positive_initial_mean':float(obs['velocity_xyz_lu'][0,fluid].mean())>0,
      'initial_mach':float(obs['maximum_speed_lu'])*3**.5<d['gates']['mach_max'],
      'target_scale_exact':abs(float(resampled_velocity[0].mean(dtype=np.float64))/float(velocity[0].mean(dtype=np.float64))-d['initializer']['velocity_scale'])<2e-6,
      'gpu_memory':s125.gpu_snapshot()['free_bytes']>=s125.device_bytes(279)+3*1024**3,
      'host_memory':s125.available_ram()['available_bytes']>=12*1024**3,
      'no_broadened_authority':not any(d['authority'][x] for x in ['full_flow_solution','force_correction','transport','population','empirical_validation'])}
    out=EVAL/'preflight_01';out.mkdir(parents=True,exist_ok=False)
    result={'passed':all(checks.values()),'checks':{k:bool(v) for k,v in checks.items()},'design':bind(DESIGN),
      'initial_mean_lu':float(obs['velocity_xyz_lu'][0,fluid].mean()),'initial_maximum_speed_lu':float(obs['maximum_speed_lu']),
      'initial_state_array_sha256':s114.audit.digest(initial),'pilot_authorized':all(checks.values())}
    write(out/'results.json',result);write(out/'completion.json',{'passed':result['passed'],'results_sha256':sha(out/'results.json')})
    print(result,flush=True);require(result['passed'],'preflight failed')


def run():
    d=read(DESIGN);verify(d)
    p=read(EVAL/'preflight_01/results.json');pc=read(EVAL/'preflight_01/completion.json')
    require(p['pilot_authorized'] and pc['results_sha256']==sha(EVAL/'preflight_01/results.json'),'preflight absent')
    require(not RUN.exists(),'immutable run exists')
    RUN.mkdir(parents=True)
    write(RUN/'manifest.json',{'design':bind(DESIGN),'preflight':bind(EVAL/'preflight_01/results.json'),
      'case_order':['stage126_s2_f1p0_cpd6_bounded'],'created_utc':datetime.now(timezone.utc).isoformat()})
    driver=None
    try:
      with np.load(d['geometry']['path']) as g:phase=g['phase']
      with np.load(d['initializer']['field']['path']) as f:rho=f['density_lu'];velocity=f['velocity_xyz_lu']
      target=phase.shape
      rr=s114.audit.legacy.resample_cell_centered_field(rho,target)
      rv=np.stack([s114.audit.legacy.resample_cell_centered_field(velocity[i],target) for i in range(3)])
      rr=np.float32(1)+np.float32(d['initializer']['density_deviation_scale'])*(rr-np.float32(1));rv*=np.float32(d['initializer']['velocity_scale'])
      initial=s114.audit.legacy.local_equilibrium_shifted_state(phase,rr,rv,d['forcing']['acceleration_lu'])
      require(s114.audit.digest(initial)==p['initial_state_array_sha256'],'initializer drift')
      s114.audit.legacy.install_generic_mask_oracle()
      adapter={'lineage':{'cuda_source':d['bindings']['cuda_source']['path'],'qualified_ptx_sha256':d['qualified_ptx_sha256']}}
      driver,build=s114.audit.legacy.create_driver(adapter,Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin'),0)
      case=s114.probe.case_for(phase,d['forcing']['acceleration_lu'],'stage126_s2_f1p0_cpd6_bounded')
      result,field,density=s114.probe.relax(driver,initial,phase,case,RUN,'stage126_s2_f1p0_cpd6_bounded',d['controls']['steps'])
      status='bounded_relaxation_gate_passed_pending_independent_evaluation' if result['passed'] else 'bounded_relaxation_gate_failed_preserved'
      completion={'status':status,'source_gate_passed':result['passed'],'design_sha256':sha(DESIGN),'manifest_sha256':sha(RUN/'manifest.json'),
        'record':bind(RUN/'stage126_s2_f1p0_cpd6_bounded/result.json'),'field':bind(RUN/'stage126_s2_f1p0_cpd6_bounded/final_fields.npz'),
        'state':bind(RUN/'stage126_s2_f1p0_cpd6_bounded/final_shifted_state.npz'),'build':build,
        'full_flow_solution':False,'transport_authorized':False}
      write(RUN/'completion.json',completion);print(status,flush=True)
    except Exception as exc:
      write(RUN/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
    finally:
      if driver is not None:driver.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','preflight','run']);args=parser.parse_args()
    {'prepare':prepare,'preflight':preflight,'run':run}[args.mode]()
