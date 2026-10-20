"""Stage129: one fixed-force CPD6 continuation to test long-window stationarity."""
from __future__ import annotations
import argparse, json, sys, traceback
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'stage128_staging'))
import cpd6_mean_correction_v1 as s128
STUDY='cpd6_stationarity_continuation_20260916';DESIGN=ROOT/'stage129_designs'/STUDY/'design_01.json';RUN=ROOT/'stage129_runs'/STUDY/'gpu_continuation_01';EVAL=ROOT/'stage129_evaluations'/STUDY
read,write,require,bind,sha=s128.read,s128.write,s128.require,s128.bind,s128.sha
def verify(d):
 s128.s127.base.s114.verify_bindings(d['bindings']);require(d['controls']=={'tau':.8,'nu_lu':.1,'threads':256,'steps':514},'controls drift');require(d['authority']=={'fixed_force_continuation':True,'force_correction':False,'transport':False},'authority drift')
def prepare():
 require(not DESIGN.parent.exists(),'immutable design exists');seal=ROOT/'stage128_evaluations/cpd6_mean_correction_20260916/completion_v2.json';c=read(seal);require(c['status']=='mean_correction_verified_relaxation_incomplete','Stage128 absent')
 for p,h in c['artifacts'].items():require(sha(p)==h,'Stage128 drift '+p)
 d128=read(s128.DESIGN);state=ROOT/'stage128_runs/cpd6_mean_correction_20260916/gpu_correction_01/stage128_cpd6_mean_corrected/final_shifted_state.npz';geometry=ROOT/'stage125_designs/third_grid_cost_20260916/geometry_cpd6.npz'
 d={'schema':'matdem.stage129.cpd6-stationarity-continuation.v1','created_utc':datetime.now(timezone.utc).isoformat(),'question':'Does the already mean-matched corrected CPD6 state satisfy the unchanged long-window stationarity gate after one bounded fixed-force continuation?','claim_boundary':'Stationarity continuation only; no new force correction, spatial-convergence claim, permeability validation or transport.',
 'bindings':{'stage128_seal':bind(seal),'stage128_design':bind(s128.DESIGN),'source_state':bind(state),'geometry':bind(geometry),'runner':bind(__file__),'probe':bind(s128.s127.base.s114.probe.__file__),'cuda_source':d128['bindings']['cuda_source']},'qualified_ptx_sha256':d128['qualified_ptx_sha256'],'acceleration_lu':d128['correction']['new_acceleration_lu'],'target_mean_velocity_m_s':d128['target_mean_velocity_m_s'],'controls':{'tau':.8,'nu_lu':.1,'threads':256,'steps':514},'gates':{'mean_relative_error_max':.0005,'field_relative_change_max':5e-5,'cpu_node_relative_l2_max':5e-5,'balance_relative_max':.005,'density_drift_max':5e-6,'mach_max':.05,'runtime_seconds_max':400},'decision':{'pass':'Accept the stationary mean-matched CPD6 field for later numerical response comparison design only; not transport.','fail':'Preserve and stop; no automatic extension.'},'authority':{'fixed_force_continuation':True,'force_correction':False,'transport':False}}
 verify(d);DESIGN.parent.mkdir(parents=True);write(DESIGN,d);print(json.dumps({'design':str(DESIGN),'sha256':sha(DESIGN)}),flush=True)
def preflight():
 d=read(DESIGN);verify(d)
 with np.load(d['bindings']['source_state']['path']) as s,np.load(d['bindings']['geometry']['path']) as g:state,phase=s['shifted_state'],s['phase'];checks={'shape':state.shape==(19,279,279,279),'phase_match':np.array_equal(phase,g['phase']),'finite':np.isfinite(state).all(),'solids_zero':all(not np.any(state[q][phase!=0]) for q in range(19)),'force_unchanged':d['acceleration_lu']==read(d['bindings']['stage128_design']['path'])['correction']['new_acceleration_lu'],'no_transport':not d['authority']['transport']};digest=s128.s127.base.s114.audit.digest(state)
 out=EVAL/'preflight_01';out.mkdir(parents=True,exist_ok=False);r={'passed':bool(all(checks.values())),'checks':{k:bool(v) for k,v in checks.items()},'source_state_array_sha256':digest,'design':bind(DESIGN)};write(out/'results.json',r);write(out/'completion.json',{'passed':r['passed'],'results_sha256':sha(out/'results.json')});require(r['passed'],'preflight failed');print(r,flush=True)
def run():
 d=read(DESIGN);verify(d);p=read(EVAL/'preflight_01/results.json');require(p['passed'],'preflight absent');require(not RUN.exists(),'immutable run exists');RUN.mkdir(parents=True);write(RUN/'manifest.json',{'design':bind(DESIGN),'preflight':bind(EVAL/'preflight_01/results.json'),'created_utc':datetime.now(timezone.utc).isoformat()});driver=None
 try:
  with np.load(d['bindings']['source_state']['path']) as s:state,phase=s['shifted_state'],s['phase']
  require(s128.s127.base.s114.audit.digest(state)==p['source_state_array_sha256'],'source drift');s128.s127.base.s114.audit.legacy.install_generic_mask_oracle();adapter={'lineage':{'cuda_source':d['bindings']['cuda_source']['path'],'qualified_ptx_sha256':d['qualified_ptx_sha256']}};driver,build=s128.s127.base.s114.audit.legacy.create_driver(adapter,Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin'),0);case=s128.s127.base.s114.probe.case_for(phase,d['acceleration_lu'],'stage129_cpd6_stationarity');result,_,_=s128.s127.base.s114.probe.relax(driver,state,phase,case,RUN,'stage129_cpd6_stationarity',514);write(RUN/'completion.json',{'status':'continuation_complete_pending_independent_evaluation','design':bind(DESIGN),'record':bind(RUN/'stage129_cpd6_stationarity/result.json'),'field':bind(RUN/'stage129_cpd6_stationarity/final_fields.npz'),'state':bind(RUN/'stage129_cpd6_stationarity/final_shifted_state.npz'),'build':build,'transport_authorized':False});print('CONTINUATION COMPLETE',result['runtime_seconds'],flush=True)
 except Exception as exc:write(RUN/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
 finally:
  if driver is not None:driver.close()
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','preflight','run']);x=a.parse_args();{'prepare':prepare,'preflight':preflight,'run':run}[x.mode]()
