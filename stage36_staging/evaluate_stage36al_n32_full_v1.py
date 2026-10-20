import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(r'C:\MATDEM_MICROPLASTIC');RUN=ROOT/'stage36_runs/stage36al_periodic_drag_n32_massclosed_20260910/run_01';OUT=ROOT/'stage36_evaluations/stage36al_n32_full_20260910/evaluation_01'
PARENT=ROOT/'stage36_evaluations/stage36ak_mass_correction_20260910/verification_01/verification.json';SOLVER=ROOT/'stage36_staging/periodic_drag_reference_massclosed_v1.py';LAUNCHER=ROOT/'stage36_staging/run_stage36al_n32_massclosed_full_v1.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if OUT.exists():raise SystemExit('fail closed: output exists')
 m=json.loads((RUN/'manifest.json').read_text());assert m['completed'] and m['status']=='n32_full_diagnostic_failed';assert not (RUN/'failure.json').exists()
 for p,h in m['input_hashes'].items():
  q={'parent':PARENT,'solver':SOLVER,'launcher':LAUNCHER}[p];assert sha(q)==h
 for p,h in m['artifact_hashes'].items():assert sha(Path(p))==h
 assert len(m['windows'])==6 and len(m['assessment_velocity_drifts'])==4 and len(m['assessment_force_drifts'])==4
 w=m['windows'];u=np.array([x['mean_u_x'] for x in w]);f=np.array([x['mean_force_x'] for x in w]);mu=.1;a=4.;drag_ratio_ref=1.530329436009
 dynamic_ref=6*np.pi*mu*a*u[-1]*drag_ratio_ref;dynamic_ratio=f[-1]/dynamic_ref
 OUT.mkdir(parents=True)
 fig,ax=plt.subplots(1,2,figsize=(9.5,3.8));x=np.arange(1,7)
 ax[0].plot(x,u,'o-',label='mean velocity');ax[0].axhline(.000625,color='k',ls='--',label='nominal target');ax[0].set(xlabel='viscous window',ylabel='superficial velocity (LU)',title='N32 convergence history');ax[0].legend()
 ax[1].plot(x,f,'o-',label='reconstructed sphere force');ax[1].plot(x,6*np.pi*mu*a*u*drag_ratio_ref,'--',label='Hasimoto/Ladd at measured U');ax[1].set(xlabel='viscous window',ylabel='force (LU)',title='External drag comparison');ax[1].legend()
 fig.tight_layout();fig.savefig(OUT/'n32_full_diagnostic.png',dpi=180);plt.close(fig)
 checks={'lineage_hashes':True,'artifact_hashes':True,'six_windows':True,'five_assessment_windows':True,'no_failure_marker':True,
   'health':m['checks']['health'],'frozen_velocity_drift':m['checks']['velocity_drift'],'frozen_force_drift':m['checks']['force_drift'],'frozen_force_error':m['checks']['force_error']}
 rec={'stage':'Stage36AL-evaluation','status':'n32_failed_convergence_and_drag_gates','checks':checks,'manifest_force_ratio_to_nominal_target_reference':m['final_force_ratio'],
   'force_ratio_to_reference_at_measured_velocity':dynamic_ratio,'reference_force_at_measured_velocity':dynamic_ref,'final_mean_velocity':u[-1],'final_mean_force':f[-1],
   'last_window_velocity_drift':m['assessment_velocity_drifts'][-1],'last_window_force_drift':m['assessment_force_drifts'][-1],
   'maximum_frozen_assessment_velocity_drift':max(m['assessment_velocity_drifts']),'maximum_frozen_assessment_force_drift':max(m['assessment_force_drifts']),
   'n48_n64_authorized':False,'figure_sha256':sha(OUT/'n32_full_diagnostic.png'),'run_manifest_sha256':sha(RUN/'manifest.json')}
 (OUT/'evaluation.json').write_text(json.dumps(rec,indent=2)+'\n')
 (OUT/'RESULTS.md').write_text(f'''# Stage36AL N32 full diagnostic\n\n- Run status: `{m['status']}`\n- Six windows and all lineage/artifact hashes: verified.\n- Numerical health: passed.\n- Maximum assessment velocity drift: {max(m['assessment_velocity_drifts']):.6f} (gate 0.002).\n- Maximum assessment force drift: {max(m['assessment_force_drifts']):.6f} (gate 0.002).\n- Last-window drifts: {m['assessment_velocity_drifts'][-1]:.3e} velocity, {m['assessment_force_drifts'][-1]:.3e} force.\n- Stored nominal-target force ratio: {m['final_force_ratio']:.6f}.\n- Force ratio to the external comparator evaluated at the measured velocity: {dynamic_ratio:.6f}.\n\nThe run reached a stationary late response, but it fails the frozen five-window drift rule because the first assessment transition remained slightly above 0.002. More importantly, the reconstructed physical-sphere force is about {100*(1-dynamic_ratio):.2f}% below the Hasimoto/Ladd comparator at the measured velocity. N48/N64 remain blocked. The force-reconstruction convention must be diagnosed; no tolerance retuning or production claim is permitted.\n''')
 print(json.dumps(rec,indent=2))
if __name__=='__main__':main()
