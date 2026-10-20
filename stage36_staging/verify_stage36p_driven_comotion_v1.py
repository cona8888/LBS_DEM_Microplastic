import json,time,sys,platform
from pathlib import Path
import numpy as np
import refined_ib_sphere_v1 as m
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
def dump(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')
def main():
    parent=ROOT/'stage36_evaluations/stage36o_force_localization_20260908/analysis_01/manifest.json';v=json.loads(parent.read_text());assert v['completed'];checked={str(parent):sha(parent)}
    for group in ('input_hashes','source_hashes','artifact_hashes'):
        for p,h in v[group].items():assert sha(p)==h;checked[p]=h
    out=ROOT/'stage36_evaluations/stage36p_driven_comotion_20260908/verification_01';out.mkdir(parents=True,exist_ok=False)
    sources={str(ROOT/'stage36_staging/STAGE36P_DRIVEN_COMOTION_CONTRACT.md'):sha(ROOT/'stage36_staging/STAGE36P_DRIVEN_COMOTION_CONTRACT.md')}
    for mod in list(sys.modules.values()):
        p=getattr(mod,'__file__',None)
        if p and Path(p).parent==ROOT/'stage36_staging' and Path(p).suffix=='.py':sources[str(Path(p).resolve())]=sha(p)
    rows=[];begin=time.monotonic();V=4*np.pi*3.2**3/3;Fscale=4*np.pi*.2**3/3*.08/.25
    try:
        for s in (1,2,4):
            f=m.equilibrium(np.ones(4096),np.zeros((3,4096))).reshape(19,16,16,16);initial=f.copy();centre=np.array([8.13,8.17,8.19]);Uold=np.zeros(3);hist=[]
            for j in range(1,64*s+1):
                if time.monotonic()-begin>120:raise TimeoutError('CPU cap')
                q=j/(64*s);U=np.array([.005/s*(3*q*q-2*q*q*q),0,0]);du=U-Uold
                a=f.reshape(19,-1);rho=a.sum(axis=0);u=m.C.T@a/rho;Pold=(m.C.T@a).sum(axis=1);_,piold=m.interior(f,centre,3.2)
                forced=(a+m.equilibrium(rho,u+du[:,None])-m.equilibrium(rho,u)).reshape(f.shape)
                source=(m.C.T@(forced-f).reshape(19,-1)).sum(axis=1)
                f,r,_=m.step(forced,centre,3.2,U,56,tau={1:.8,2:.65,4:.575}[s]);centre=centre+U
                ib=np.array(r['force_on_fluid']);delta=np.array(r['interior_momentum_after'])-piold;uncorrected=-ib+delta;corrected=uncorrected-V*du
                residual=np.array(r['momentum_after'])-Pold-source-ib
                row={'time':j/(256*s),'velocity_lu':U.tolist(),'external_impulse_inside':(V*du).tolist(),'uncorrected_force':(uncorrected*s*s).tolist(),'corrected_force':(corrected*s*s).tolist(),'momentum_residual':residual.tolist(),'density_error':r['density_error'],'velocity_error':r['velocity_error_from_comotion']};hist.append(row);Uold=U
                assert np.max(abs(residual))/4096<1e-12 and r['density_error']<1e-10 and r['velocity_error_from_comotion']<1e-10
            err=max(np.linalg.norm(r['corrected_force']) for r in hist)/Fscale;bad=max(np.linalg.norm(r['uncorrected_force']) for r in hist)/Fscale
            assert err<1e-8 and bad>1e-2
            row={'s':s,'steps':64*s,'corrected_normalized_peak':float(err),'omitted_source_normalized_peak':float(bad),'passed':True};rows.append(row)
            dump(out/f's{s}_history.json',hist);np.savez_compressed(out/f's{s}_states.npz',initial=initial,final=f,centre_final=centre);print(row,flush=True)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
    for p,h in sources.items():assert sha(p)==h
    for p,h in checked.items():assert sha(p)==h
    (out/'RESULTS.md').write_text('# Stage36P — uniform driven co-motion\n\nThree manufactured CPU flow tests passed at factors1,2,4. Analytical net traction is zero because pressure is spatially constant and velocity gradients vanish. The sphere is prescribed to follow the uniform fluid.\n\n'+json.dumps(rows,indent=2)+'\n\nOmitting external forcing inside fictitious fluid gives a false nonzero force. Subtracting that impulse recovers zero traction. This is a source-accounting limiting-case verification, not nonzero drag validation. Previous unforced runs had no external source, so this is not a correction to their3.68% discrepancy. No prior regression suite was rerun; only the three manufactured flow tests and their per-step assertions ran.\n\nNext gate remains a nonuniform relative-motion force benchmark with independently matched boundary conditions. No release prediction is qualified.\n',encoding='utf-8')
    dump(out/'manifest.json',{'completed':True,'cases':rows,'new_cpu_flows':3,'physical_drag_validated':False,'release_prediction_qualified':False,'source_hashes':sources,'parent_hashes':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'python':platform.python_version(),'numpy':np.__version__,'elapsed_seconds':time.monotonic()-begin})
if __name__=='__main__':main()
