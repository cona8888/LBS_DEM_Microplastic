"""Stage128: one bounded CPD6 linear force correction from the verified stationary state."""
from __future__ import annotations
import argparse, gc, json, sys, traceback
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage127_staging'))
import parity_initializer_diagnosis_v1 as s127

STUDY='cpd6_mean_correction_20260916'
DESIGN=ROOT/'stage128_designs'/STUDY/'design_01.json'
RUN=ROOT/'stage128_runs'/STUDY/'gpu_correction_01'
EVAL=ROOT/'stage128_evaluations'/STUDY
read,write,require,bind,sha=s127.read,s127.write,s127.require,s127.bind,s127.sha

def verify(d):
    s127.base.s114.verify_bindings(d['bindings'])
    require(d['controls']=={'tau':.8,'nu_lu':.1,'threads':256,'steps':1542},'controls drift')
    require(d['correction']['rule']=='new acceleration = old acceleration * target mean / independently reconstructed achieved mean','rule drift')
    require(d['authority']=={'one_force_correction':True,'full_flow_solution':False,'transport':False},'authority drift')

def prepare():
    require(not DESIGN.parent.exists(),'immutable design exists')
    seal=ROOT/'stage127_evaluations/cpd6_parity_initializer_diagnosis_20260916/completion.json'
    c=read(seal);require(c['status']=='parity_initializer_mechanism_verified_cost_gate_failed','Stage127 absent')
    for p,h in c['artifacts'].items():require(sha(p)==h,'Stage127 drift '+p)
    ev=ROOT/'stage127_evaluations/cpd6_parity_initializer_diagnosis_20260916/independent_evaluation_01/results.json'
    r=read(ev);require(r['initializer_mechanism_verified'],'initializer not qualified')
    d126=read(ROOT/'stage126_designs/cpd6_bounded_relaxation_attempt02_20260916/design_01.json')
    target=float(d126['forcing']['target_mean_velocity_m_s'])
    old=float(d126['forcing']['acceleration_lu']);factor=float(target/r['mean_interstitial_velocity_m_s']);new=float(np.float32(old*factor))
    state=ROOT/'stage127_runs/cpd6_parity_initializer_diagnosis_20260916/gpu_diagnosis_01/stage127_cpd6_parity_average/final_shifted_state.npz'
    geometry=ROOT/'stage125_designs/third_grid_cost_20260916/geometry_cpd6.npz'
    d={'schema':'matdem.stage128.cpd6-mean-correction.v1','created_utc':datetime.now(timezone.utc).isoformat(),
      'question':'Does one linear force correction bring the verified stationary CPD6 flow within 0.05% of the accepted CPD4 mean while preserving stationarity and numerical health?',
      'claim_boundary':'One bounded force-correction verification only; not spatial convergence, permeability validation or transport.',
      'bindings':{'stage127_seal':bind(seal),'stage127_evaluation':bind(ev),'source_state':bind(state),'geometry':bind(geometry),'runner':bind(__file__),
                  'probe':bind(s127.base.s114.probe.__file__),'steady_gate':bind(s127.base.s114.gate.__file__),'cuda_source':d126['bindings']['cuda_source']},
      'qualified_ptx_sha256':d126['qualified_ptx_sha256'],'target_mean_velocity_m_s':target,
      'correction':{'rule':'new acceleration = old acceleration * target mean / independently reconstructed achieved mean','old_acceleration_lu':old,
                    'achieved_mean_velocity_m_s':r['mean_interstitial_velocity_m_s'],'factor':factor,'new_acceleration_lu':new},
      'controls':{'tau':.8,'nu_lu':.1,'threads':256,'steps':1542},
      'gates':{'mean_relative_error_max':.0005,'field_relative_change_max':5e-5,'cpu_node_relative_l2_max':5e-5,'balance_relative_max':.005,
               'density_drift_max':5e-6,'mach_max':.05,'runtime_seconds_max':1100},
      'decision':{'pass':'Eligible for a separately frozen CPD4/CPD6 response comparison; not transport.','fail':'Preserve and stop; no automatic second correction or extension.'},
      'authority':{'one_force_correction':True,'full_flow_solution':False,'transport':False}}
    require(.95<factor<1.05,'correction outside bounded range');verify(d);DESIGN.parent.mkdir(parents=True);write(DESIGN,d)
    print(json.dumps({'design':str(DESIGN),'sha256':sha(DESIGN),'factor':factor,'new_acceleration_lu':new}),flush=True)

def preflight():
    d=read(DESIGN);verify(d)
    with np.load(d['bindings']['source_state']['path']) as s,np.load(d['bindings']['geometry']['path']) as g:
        state,phase=s['shifted_state'],s['phase']
        checks={'shape':state.shape==(19,279,279,279),'phase_match':np.array_equal(phase,g['phase']),'finite':np.isfinite(state).all(),
                'solids_zero':all(not np.any(state[q][phase!=0]) for q in range(19)),'bounded_factor':.95<d['correction']['factor']<1.05,
                'force_changed_once':d['correction']['new_acceleration_lu']!=d['correction']['old_acceleration_lu'],'no_transport':not d['authority']['transport']}
        digest=s127.base.s114.audit.digest(state)
    out=EVAL/'preflight_01';out.mkdir(parents=True,exist_ok=False);r={'passed':bool(all(checks.values())),'checks':{k:bool(v) for k,v in checks.items()},'source_state_array_sha256':digest,'design':bind(DESIGN)}
    write(out/'results.json',r);write(out/'completion.json',{'passed':r['passed'],'results_sha256':sha(out/'results.json')});require(r['passed'],'preflight failed');print(r,flush=True)

def run():
    d=read(DESIGN);verify(d);p=read(EVAL/'preflight_01/results.json');require(p['passed'],'preflight absent');require(not RUN.exists(),'immutable run exists')
    RUN.mkdir(parents=True);write(RUN/'manifest.json',{'design':bind(DESIGN),'preflight':bind(EVAL/'preflight_01/results.json'),'created_utc':datetime.now(timezone.utc).isoformat()})
    driver=None
    try:
      with np.load(d['bindings']['source_state']['path']) as s:state,phase=s['shifted_state'],s['phase']
      require(s127.base.s114.audit.digest(state)==p['source_state_array_sha256'],'source drift')
      s127.base.s114.audit.legacy.install_generic_mask_oracle();adapter={'lineage':{'cuda_source':d['bindings']['cuda_source']['path'],'qualified_ptx_sha256':d['qualified_ptx_sha256']}}
      driver,build=s127.base.s114.audit.legacy.create_driver(adapter,Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin'),0)
      case=s127.base.s114.probe.case_for(phase,d['correction']['new_acceleration_lu'],'stage128_cpd6_mean_corrected')
      result,_,_=s127.base.s114.probe.relax(driver,state,phase,case,RUN,'stage128_cpd6_mean_corrected',d['controls']['steps'])
      write(RUN/'completion.json',{'status':'correction_complete_pending_independent_evaluation','design':bind(DESIGN),'record':bind(RUN/'stage128_cpd6_mean_corrected/result.json'),
        'field':bind(RUN/'stage128_cpd6_mean_corrected/final_fields.npz'),'state':bind(RUN/'stage128_cpd6_mean_corrected/final_shifted_state.npz'),'build':build,
        'full_flow_solution':False,'transport_authorized':False});print('CORRECTION COMPLETE',result['runtime_seconds'],flush=True)
    except Exception as exc:write(RUN/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
    finally:
      if driver is not None:driver.close()

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','preflight','run']);x=a.parse_args();{'prepare':prepare,'preflight':preflight,'run':run}[x.mode]()
