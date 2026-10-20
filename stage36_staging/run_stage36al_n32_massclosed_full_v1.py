import hashlib,json,os,platform,time
from pathlib import Path
import numpy as np
import periodic_drag_reference_massclosed_v1 as solver
import periodic_drag_reference_v1 as reference

ROOT=Path(r'C:\MATDEM_MICROPLASTIC')
OUT=ROOT/'stage36_runs/stage36al_periodic_drag_n32_massclosed_20260910/run_01'
PARENT=ROOT/'stage36_evaluations/stage36ak_mass_correction_20260910/verification_01/verification.json'
SRC=ROOT/'stage36_staging/periodic_drag_reference_massclosed_v1.py';SELF=ROOT/'stage36_staging/run_stage36al_n32_massclosed_full_v1.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def atomic(p,x):
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(x,indent=2)+'\n');os.replace(q,p)
def main():
 if OUT.exists():raise SystemExit('fail closed: immutable run exists')
 parent=json.loads(PARENT.read_text());assert parent['rerun_authorized'] and not parent['n48_n64_authorized'];assert sha(SRC)==parent['input_hashes']['candidate']
 OUT.mkdir(parents=True);pars=reference.nominal_parameters(32);window=pars['viscous_window_steps'];total=6*window
 state=solver.initialize(32);samples=[];windows=[];acc=[0.,0.,0];t0=time.monotonic();maxima={'ledger':0.,'mass':0.,'density':0.,'slip':0.,'correction':0.}
 try:
  for step in range(1,total+1):
   state,row=solver.step(state,pars['source_impulse_per_cell']);u=row['superficial_velocity'][0];force=row['force_on_sphere'][0];acc[0]+=u;acc[1]+=force;acc[2]+=1
   maxima['ledger']=max(maxima['ledger'],max(abs(x) for x in row['momentum_ledger_residual']));maxima['mass']=max(maxima['mass'],row['mass_relative_drift']);maxima['density']=max(maxima['density'],row['density_error']);maxima['slip']=max(maxima['slip'],row['marker_slip']);maxima['correction']=max(maxima['correction'],abs(row['mass_restoration_lu']))
   if row['minimum_population']<=0 or maxima['density']>=.01 or maxima['mass']>1e-12 or maxima['ledger']>1e-11 or maxima['slip']>1e-8 or maxima['correction']>1e-9:raise RuntimeError('online health gate failed')
   if step%64==0:samples.append({'step':step,'u_x':u,'force_x':force,'density_error':row['density_error'],'marker_slip':row['marker_slip'],'mass_restoration_lu':row['mass_restoration_lu']})
   if step%window==0:
    windows.append({'window':step//window,'mean_u_x':acc[0]/acc[2],'mean_force_x':acc[1]/acc[2]});acc=[0.,0.,0];np.savez_compressed(OUT/f'checkpoint_window_{step//window}.npz',f=state['f'])
   if step%256==0:atomic(OUT/'progress.json',{'status':'running','pid':os.getpid(),'step':step,'total_steps':total,'fraction':step/total,'elapsed_seconds':time.monotonic()-t0,'maxima':maxima,'completed_windows':windows})
  assessment=windows[1:];ud=[abs(assessment[i]['mean_u_x']/assessment[i-1]['mean_u_x']-1) for i in range(1,5)];fd=[abs(assessment[i]['mean_force_x']/assessment[i-1]['mean_force_x']-1) for i in range(1,5)];ratio=assessment[-1]['mean_force_x']/pars['reference_force_lu']
  checks={'five_assessment_windows':len(assessment)==5,'velocity_drift':max(ud)<=.002,'force_drift':max(fd)<=.002,'force_error':abs(ratio-1)<=.03,'health':maxima['density']<.01 and maxima['mass']<=1e-12 and maxima['ledger']<=1e-11 and maxima['slip']<=1e-8 and maxima['correction']<=1e-9}
  (OUT/'samples.json').write_text(json.dumps(samples,indent=2)+'\n');np.savez_compressed(OUT/'final_state.npz',f=state['f'])
  m={'stage':'Stage36AL','status':'n32_full_diagnostic_passed' if all(checks.values()) else 'n32_full_diagnostic_failed','completed':True,'pid':os.getpid(),'steps':total,'window_steps':window,'windows':windows,'assessment_velocity_drifts':ud,'assessment_force_drifts':fd,'final_force_ratio':ratio,'checks':checks,'maxima':maxima,'elapsed_seconds':time.monotonic()-t0,'input_hashes':{'parent':sha(PARENT),'solver':sha(SRC),'launcher':sha(SELF)},'python':platform.python_version(),'numpy':np.__version__,'n48_n64_authorized':False}
  m['artifact_hashes']={str(p):sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ('progress.json','manifest.json')};atomic(OUT/'manifest.json',m);atomic(OUT/'progress.json',{'status':'complete','passed':all(checks.values()),'step':total,'total_steps':total});print(json.dumps(m,indent=2))
 except Exception as e:
  atomic(OUT/'failure.json',{'error':repr(e),'step':step,'maxima':maxima,'completed_windows':windows});raise
if __name__=='__main__':main()
