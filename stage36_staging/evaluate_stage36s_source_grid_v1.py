import json,sys,platform
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import verify_stage36q_nonzero_reference_v1 as ref
import refined_ib_sphere_v1 as m
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
def dump(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')
def source(x):
    r=np.linalg.norm(x,axis=1);mask=(r>ref.R)&(r<ref.L);b=np.zeros_like(x);g,lap=ref.derivatives(x[mask]);b[mask]=np.einsum('nij,nj->ni',g,ref.field(x[mask]))-.1*lap;return b
def interior(b,n,c,levels):
    pts,w=m.ib.sphere_quadrature(.2*n,*levels);return w@m.trilinear(b,pts+c,n)/n**3
def main():
    parent=ROOT/'stage36_evaluations/stage36r_manufactured_flow_20260908/verification_01/manifest.json';v=json.loads(parent.read_text());assert v['completed'] and not v['analytical_passed'];checked={str(parent):sha(parent)}
    for group in ('source_hashes','parent_hashes','artifact_hashes'):
        for p,h in v[group].items():assert sha(p)==h;checked[p]=h
    grid=np.indices((16,16,16)).reshape(3,-1).T+.5;pts=np.array([[4.13,5.2,6.7],[8.1,9.2,10.3]])
    np.testing.assert_allclose(m.trilinear(np.ones((4096,3)),pts,16),1,atol=1e-12,rtol=0);np.testing.assert_allclose(m.trilinear(grid,pts,16),pts,atol=1e-12,rtol=0)
    F=np.array([4*np.pi/3*.1*.2**3*2*.01/.2**2,0,0]);scale=F[0];rows=[]
    for n in (16,24,32,48,64):
        nodes=np.indices((n,n,n)).reshape(3,-1).T+.5
        for phase in (0,.13,.37):
            c=n*.5+phase*np.array([1,.7,.3]);b=source((nodes-c)/n);total=b.sum(axis=0)/n**3;coarse=interior(b,n,c,(8,16,32));fine=interior(b,n,c,(16,32,64))
            row={'N':n,'phase':phase,'source_integral':total.tolist(),'source_error':float(np.linalg.norm(total-F)/scale),'interior_leakage':fine.tolist(),'leakage_relative':float(np.linalg.norm(fine)/scale),'quadrature_difference':float(np.linalg.norm(fine-coarse)/scale)}
            row['screen_passed']=row['source_error']<=.02 and row['leakage_relative']<=.02 and row['quadrature_difference']<=.002
            if n==16 and phase==0:
                original=interior(b,n,c,(4,8,16));hist=json.loads((parent.parent/'s1_history.json').read_text());np.testing.assert_allclose(original,hist[-1]['interior_source_force'],atol=scale*1e-9,rtol=0);row['stage36r_original_quadrature_reproduced']=True;row['original_leakage_relative']=float(np.linalg.norm(original)/scale)
            rows.append(row)
    out=ROOT/'stage36_evaluations/stage36s_source_grid_20260908/analysis_01';out.mkdir(parents=True,exist_ok=False);dump(out/'grid_audit.json',{'cases':rows,'new_flow_solves':0,'trilinear_tests_passed':2,'analytical_force':F.tolist()})
    fig,ax=plt.subplots(1,2,figsize=(10,4.5));fig.subplots_adjust(bottom=.22,top=.8,wspace=.3)
    for phase in (0,.13,.37):
        rs=[r for r in rows if r['phase']==phase]
        ax[0].plot([r['N'] for r in rs],[100*r['source_error'] for r in rs],'o-',label=f'phase {phase}')
        ax[1].plot([r['N'] for r in rs],[100*r['leakage_relative'] for r in rs],'o-',label=f'phase {phase}')
    for a in ax:a.axhline(2,color='gray',ls=':');a.set_xlabel('Grid points per side');a.legend(frameon=False,fontsize=8)
    ax[0].set_ylabel('Total source integral error (%)');ax[1].set_ylabel('Interior leakage / reference force (%)');fig.suptitle('Stage36S | Spatial source audit (no flow solves)');fig.text(.08,.05,'Same analytical source at every grid and phase. Diagnostic screens do not establish flow or drag accuracy.',fontsize=9);fig.savefig(out/'source_grid.png',dpi=160);plt.close(fig)
    table='\n'.join(f"| {r['N']} | {r['phase']} | {100*r['source_error']:.3f}% | {100*r['leakage_relative']:.3f}% | {100*r['quadrature_difference']:.3f}% | {r['screen_passed']} |" for r in rows)
    (out/'RESULTS.md').write_text('# Stage36S — source integration versus spatial grid\n\nFifteen static source evaluations completed; no flow simulations. Two trilinear reproduction tests passed, all parent hashes checked, and original centred N16 interior correction reproduced from saved Stage36R history.\n\n| N | Cell phase | Total source error | Interior leakage | Quadrature difference | Screen pass |\n|---|---|---|---|---|---|\n'+table+'\n\nAll percentages use the analytical steady force as denominator. The exact interior source is zero. Phase variation reveals grid alignment sensitivity. Small total-source error alone cannot certify local source accuracy or force accuracy. The interpolation and finite spherical quadrature are separately exposed; no correction factor was fitted.\n\nThe Stage36R flow failure remains. Next: use a cell-integrated source representation and a consistent interior-volume treatment, verify them against this unchanged reference before another flow comparison. Passing static screens does not authorize production or release predictions.\n',encoding='utf-8')
    sources={}
    for mod in list(sys.modules.values()):
        p=getattr(mod,'__file__',None)
        if p and Path(p).parent==ROOT/'stage36_staging' and Path(p).suffix=='.py':sources[str(Path(p).resolve())]=sha(p)
    p=ROOT/'stage36_staging/STAGE36S_SOURCE_GRID_CONTRACT.md';sources[str(p)]=sha(p)
    dump(out/'manifest.json',{'completed':True,'source_hashes':sources,'input_hashes':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'python':platform.python_version(),'numpy':np.__version__,'new_flow_solves':0,'release_qualified':False})
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
