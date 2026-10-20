"""Stage130: final 257-step fixed-force CPD6 stationarity confirmation."""
import argparse,json,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'stage129_staging'));import cpd6_stationarity_continuation_v1 as s129
STUDY='cpd6_final_stationarity_20260916';DESIGN=ROOT/'stage130_designs'/STUDY/'design_01.json';RUN=ROOT/'stage130_runs'/STUDY/'gpu_confirmation_01';EVAL=ROOT/'stage130_evaluations'/STUDY
read,write,require,bind,sha=s129.read,s129.write,s129.require,s129.bind,s129.sha
def verify(d):s129.s128.s127.base.s114.verify_bindings(d['bindings']);require(d['controls']=={'tau':.8,'nu_lu':.1,'threads':256,'steps':257},'controls drift');require(not d['authority']['force_correction'] and not d['authority']['transport'],'authority drift')
def prepare():
 require(not DESIGN.parent.exists(),'design exists');seal=ROOT/'stage129_evaluations/cpd6_stationarity_continuation_20260916/completion.json';c=read(seal);require(c['status']=='stationarity_continuation_verified_narrow_long_window_miss','Stage129 absent')
 for p,h in c['artifacts'].items():require(sha(p)==h,'Stage129 drift '+p)
 d129=read(s129.DESIGN);state=ROOT/'stage129_runs/cpd6_stationarity_continuation_20260916/gpu_continuation_01/stage129_cpd6_stationarity/final_shifted_state.npz'
 d={'schema':'matdem.stage130.cpd6-final-stationarity.v1','created_utc':datetime.now(timezone.utc).isoformat(),'question':'Does one final fixed-force 257-step window clear the unchanged CPD6 stationarity threshold after the 2.84% narrow miss?','claim_boundary':'Flow solution verification only; not spatial convergence, permeability validation or transport.','bindings':{'stage129_seal':bind(seal),'source_state':bind(state),'geometry':d129['bindings']['geometry'],'runner':bind(__file__),'probe':d129['bindings']['probe'],'cuda_source':d129['bindings']['cuda_source']},'qualified_ptx_sha256':d129['qualified_ptx_sha256'],'acceleration_lu':d129['acceleration_lu'],'target_mean_velocity_m_s':d129['target_mean_velocity_m_s'],'controls':{'tau':.8,'nu_lu':.1,'threads':256,'steps':257},'gates':d129['gates']|{'runtime_seconds_max':250},'decision':{'pass':'Accept stationary mean-matched CPD6 field for later numerical comparison design only.','fail':'Stop and revise the plan; no further continuation.'},'authority':{'final_stationarity_confirmation':True,'force_correction':False,'transport':False}}
 verify(d);DESIGN.parent.mkdir(parents=True);write(DESIGN,d);print(json.dumps({'design':str(DESIGN),'sha256':sha(DESIGN)}))
def preflight():
 d=read(DESIGN);verify(d)
 with np.load(d['bindings']['source_state']['path']) as s,np.load(d['bindings']['geometry']['path']) as g:state,phase=s['shifted_state'],s['phase'];checks={'shape':state.shape==(19,279,279,279),'phase_match':np.array_equal(phase,g['phase']),'finite':np.isfinite(state).all(),'solids_zero':all(not np.any(state[q][phase!=0]) for q in range(19)),'force_unchanged':d['acceleration_lu']==read(s129.DESIGN)['acceleration_lu'],'no_transport':not d['authority']['transport']};digest=s129.s128.s127.base.s114.audit.digest(state)
 out=EVAL/'preflight_01';out.mkdir(parents=True,exist_ok=False);r={'passed':bool(all(checks.values())),'checks':{k:bool(v) for k,v in checks.items()},'source_state_array_sha256':digest,'design':bind(DESIGN)};write(out/'results.json',r);write(out/'completion.json',{'passed':r['passed'],'results_sha256':sha(out/'results.json')});require(r['passed'],'preflight failed');print(r)
def run():
 d=read(DESIGN);verify(d);p=read(EVAL/'preflight_01/results.json');require(p['passed'],'preflight absent');require(not RUN.exists(),'run exists');RUN.mkdir(parents=True);write(RUN/'manifest.json',{'design':bind(DESIGN),'preflight':bind(EVAL/'preflight_01/results.json'),'created_utc':datetime.now(timezone.utc).isoformat()});driver=None
 try:
  with np.load(d['bindings']['source_state']['path']) as s:state,phase=s['shifted_state'],s['phase']
  s129.s128.s127.base.s114.audit.legacy.install_generic_mask_oracle();adapter={'lineage':{'cuda_source':d['bindings']['cuda_source']['path'],'qualified_ptx_sha256':d['qualified_ptx_sha256']}};driver,build=s129.s128.s127.base.s114.audit.legacy.create_driver(adapter,Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin'),0);case=s129.s128.s127.base.s114.probe.case_for(phase,d['acceleration_lu'],'stage130_cpd6_final_stationarity');result,_,_=s129.s128.s127.base.s114.probe.relax(driver,state,phase,case,RUN,'stage130_cpd6_final_stationarity',257);write(RUN/'completion.json',{'status':'confirmation_complete_pending_independent_evaluation','design':bind(DESIGN),'record':bind(RUN/'stage130_cpd6_final_stationarity/result.json'),'field':bind(RUN/'stage130_cpd6_final_stationarity/final_fields.npz'),'state':bind(RUN/'stage130_cpd6_final_stationarity/final_shifted_state.npz'),'build':build,'transport_authorized':False});print('CONFIRMATION COMPLETE',result['runtime_seconds'])
 except Exception as exc:write(RUN/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
 finally:
  if driver is not None:driver.close()
if __name__=='__main__':a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','preflight','run']);x=a.parse_args();{'prepare':prepare,'preflight':preflight,'run':run}[x.mode]()
