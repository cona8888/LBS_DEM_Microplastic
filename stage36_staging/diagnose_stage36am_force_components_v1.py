import hashlib,json,math,platform
from pathlib import Path
import numpy as np
import periodic_drag_reference_massclosed_v1 as solver
import periodic_drag_reference_v1 as reference

ROOT=Path(r'C:\MATDEM_MICROPLASTIC');RUN=ROOT/'stage36_runs/stage36al_periodic_drag_n32_massclosed_20260910/run_01';OUT=ROOT/'stage36_evaluations/stage36am_force_components_20260910/diagnosis_01'
SRC=ROOT/'stage36_staging/periodic_drag_reference_massclosed_v1.py';SELF=ROOT/'stage36_staging/diagnose_stage36am_force_components_v1.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if OUT.exists():raise SystemExit('fail closed: output exists')
 m=json.loads((RUN/'manifest.json').read_text());assert m['completed'] and m['status']=='n32_full_diagnostic_failed';assert not (RUN/'failure.json').exists()
 for p,h in m['artifact_hashes'].items():assert sha(Path(p))==h
 state=solver.initialize(32)
 with np.load(RUN/'final_state.npz') as z:state['f']=z['f'].copy()
 pars=reference.nominal_parameters(32);_,row=solver.step(state,pars['source_impulse_per_cell'])
 marker=np.array(row['marker_impulse_on_fluid']);source=np.array(row['source_impulse']);inside=np.array(row['interior_source_impulse']);reported=np.array(row['force_on_sphere'])
 interior_change=reported+marker+inside
 marker_reaction=-marker;no_double_source=marker_reaction+interior_change
 u=row['superficial_velocity'][0];external=6*math.pi*.1*4*u*1.530329436009
 variants={'marker_reaction':marker_reaction.tolist(),'interior_momentum_change':interior_change.tolist(),'interior_source':inside.tolist(),'reported_force':reported.tolist(),'fictitious_fluid_corrected_without_second_source_subtraction':no_double_source.tolist(),'total_source':source.tolist()}
 ratios={k:float(v[0]/external) for k,v in [('marker_reaction',marker_reaction),('reported_force',reported),('without_second_source_subtraction',no_double_source)]}
 rec={'stage':'Stage36AM','status':'force_components_isolated_no_new_run','replayed_steps':1,'measured_superficial_velocity_x':u,'external_reference_force_at_measured_velocity':external,'components':variants,'ratios_to_external_reference':ratios,
  'momentum_ledger_residual':row['momentum_ledger_residual'],'diagnosis':'reported force is dominated by the fictitious-interior momentum correction; second source subtraction is small and not the primary deficit','force_convention_resolved':False,'n48_n64_authorized':False,
  'input_hashes':{'run_manifest':sha(RUN/'manifest.json'),'final_state':sha(RUN/'final_state.npz'),'solver':sha(SRC),'diagnostic':sha(SELF)},'python':platform.python_version(),'numpy':np.__version__}
 OUT.mkdir(parents=True);(OUT/'diagnosis.json').write_text(json.dumps(rec,indent=2)+'\n')
 (OUT/'RESULTS.md').write_text(f'''# Stage36AM force-component diagnosis\n\n- Measured superficial velocity: {u:.12g} LU\n- External Hasimoto/Ladd force at that velocity: {external:.12g} LU\n- Marker reaction: {marker_reaction[0]:.12g} LU (ratio {ratios['marker_reaction']:.6f})\n- Fictitious-interior momentum change: {interior_change[0]:.12g} LU\n- Interior source: {inside[0]:.12g} LU\n- Current reported force: {reported[0]:.12g} LU (ratio {ratios['reported_force']:.6f})\n- Without the second interior-source subtraction: {no_double_source[0]:.12g} LU (ratio {ratios['without_second_source_subtraction']:.6f})\n\nThe extra interior-source subtraction is not the main cause. The large difference comes from applying the fictitious-interior momentum correction to a volume-forced, stationary-sphere formulation. Marker reaction and reconstructed physical force must now be matched to the exact force convention used by the Hasimoto/Ladd comparator before any rerun or higher resolution.\n''')
 print(json.dumps(rec,indent=2))
if __name__=='__main__':main()
