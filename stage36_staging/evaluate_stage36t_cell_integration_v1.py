import json,time,sys,platform
from pathlib import Path
import numpy as np
from evaluate_stage36s_source_grid_v1 import source
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
def dump(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')
def main():
    parent=ROOT/'stage36_evaluations/stage36s_source_grid_20260908/analysis_01/manifest.json';v=json.loads(parent.read_text());assert v['completed'];checked={str(parent):sha(parent)}
    for group in ('source_hashes','input_hashes','artifact_hashes'):
        for p,h in v[group].items():assert sha(p)==h;checked[p]=h
    out=ROOT/'stage36_evaluations/stage36t_cell_integration_20260908/analysis_01';out.mkdir(parents=True,exist_ok=False)
    cells=np.indices((16,16,16)).reshape(3,-1).T;F=np.array([4*np.pi/3*.1*.2**3*2*.01/.2**2,0,0]);V=4*np.pi*.2**3/3;rows=[];begin=time.monotonic()
    try:
        for phase in (0,.13,.37):
            centre=8+phase*np.array([1,.7,.3])
            for k in (2,4,8):
                offsets=(np.indices((k,k,k)).reshape(3,-1).T+.5)/k
                np.testing.assert_allclose(offsets.mean(axis=0),.5,rtol=0,atol=1e-12)
                avg=np.zeros((4096,3));chi=np.zeros(4096);joint=np.zeros((4096,3));total=np.zeros(3)
                for offset in offsets:
                    if time.monotonic()-begin>120:raise TimeoutError('static CPU cap')
                    x=(cells+offset-centre)/16;b=source(x);inside=np.linalg.norm(x,axis=1)<.2;avg+=b/len(offsets);chi+=inside/len(offsets);joint+=b*inside[:,None]/len(offsets);total+=b.sum(axis=0)/len(offsets)/4096
                np.testing.assert_allclose(avg.sum(axis=0)/4096,total,rtol=0,atol=1e-12);assert np.all((chi>=0)&(chi<=1));assert np.max(abs(joint))==0
                product=np.sum(chi[:,None]*avg,axis=0)/4096;row={'phase':phase,'subdivisions':k,'source_error':float(np.linalg.norm(total-F)/F[0]),'sphere_volume_error':float(abs(chi.mean()-V)/V),'product_interior_relative':float(np.linalg.norm(product)/F[0]),'product_interior_vector':product.tolist(),'joint_interior_vector':joint.sum(axis=0).tolist(),'cut_cells':int(np.sum((chi>0)&(chi<1)))};row['screen_passed']=row['source_error']<=.02 and row['product_interior_relative']<=.02;rows.append(row)
                np.savez_compressed(out/f'phase{phase}_k{k}.npz',cell_source=avg,solid_fraction=chi,joint_interior_source=joint);print(row,flush=True)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
    dump(out/'audit.json',{'cases':rows,'new_flow_runs':0,'checks':'midpoint linear moments; aggregation; bounded fractions; zero joint support'})
    table='\n'.join(f"| {r['phase']} | {r['subdivisions']} | {100*r['source_error']:.4f}% | {100*r['sphere_volume_error']:.4f}% | {100*r['product_interior_relative']:.3f}% |" for r in rows)
    (out/'RESULTS.md').write_text('# Stage36T — cell integration is not sufficient by itself\n\nNine static integrations completed; no solver run or prior regression-suite rerun. Local midpoint moments, aggregation, fraction bounds and source support checks passed.\n\n| Phase | Subcells per axis | Total source error | Sphere volume error | Product-of-means interior forcing / reference |\n|---|---|---|---|---|\n'+table+'\n\nJoint integration of indicator times source is exactly zero by the prescribed support. Multiplying the separately averaged indicator and source is not zero in cut cells. Thus improving total-source quadrature alone does not remove the interior forcing introduced by a constant cell-average representation. Zero joint integral is a construction property, NOT proof that an LBM population received zero interior impulse.\n\nDo not replace the actual discrete interior impulse by the analytical zero while retaining the same cell-average injection: that would break consistency. A verified subcell/phase-resolved transfer or another boundary-compatible source representation is needed before applying this correction to a flow solve. Prior flow failures and2% thresholds remain unchanged; no physical drag or release prediction is qualified.\n\nNext: design and unit-test a source-transfer/restriction pair that preserves the same discrete impulse accounting, then return to the frozen manufactured-flow comparison.\n',encoding='utf-8')
    sources={}
    for mod in list(sys.modules.values()):
        p=getattr(mod,'__file__',None)
        if p and Path(p).parent==ROOT/'stage36_staging' and Path(p).suffix=='.py':sources[str(Path(p).resolve())]=sha(p)
    contract=ROOT/'stage36_staging/STAGE36T_CELL_INTEGRATION_CONTRACT.md';sources[str(contract)]=sha(contract)
    for p,h in checked.items():assert sha(p)==h
    dump(out/'manifest.json',{'completed':True,'source_hashes':sources,'input_hashes':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'new_flow_runs':0,'release_qualified':False,'python':platform.python_version(),'numpy':np.__version__,'elapsed_seconds':time.monotonic()-begin})
if __name__=='__main__':main()
