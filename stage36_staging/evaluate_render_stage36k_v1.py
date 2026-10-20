"""Independent separable-kernel audit and figure, from immutable operator evidence."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

BASE=ROOT/'stage36_evaluations/stage36k_immersed_interface_20260908'
RAW=BASE/'verification_02'
def read(p):return json.loads(p.read_text())
def dump(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')
def kernel(a):
    # Independent piecewise polynomial evaluation on dense coordinate lines.
    r=np.abs(a);b=np.zeros_like(r)
    for index in np.ndindex(r.shape):
        t=r[index]
        if t<1:b[index]=(3-2*t+(1+4*t-4*t*t)**.5)/8
        elif t<2:b[index]=(5-2*t-(-7+12*t-4*t*t)**.5)/8
    return b

def main():
    v=read(RAW/'verification.json');assert v['execution_completed'] and v['unit_tests_run']==133 and v['operator_gates_passed'] and v['quadratic_integral_convergence_passed']
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for p,h in v[group].items():assert sha(p)==h,p
    old=BASE/'verification_01'
    assert read(old/'phase_results.json')==read(RAW/'phase_results.json')
    with np.load(old/'representative_operators.npz') as a,np.load(RAW/'representative_operators.npz') as b:
        for k in a.files:np.testing.assert_array_equal(a[k],b[k])
    rows=read(RAW/'phase_results.json');assert len(rows)==27
    with np.load(RAW/'representative_operators.npz') as z:
        body=z['body_points'];qv=z['volume_weights'];V=4*np.pi*.2**3/3
        np.testing.assert_allclose(qv.sum(),V,atol=1e-15,rtol=0)
        np.testing.assert_allclose(qv@body,0,atol=1e-15,rtol=0)
        np.testing.assert_allclose(body.T@(qv[:,None]*body),np.eye(3)*V*.2**2/5,atol=1e-15,rtol=0)
        independent=[]
        for row in rows:
            n=row['n'];h=1/n;c=np.array(row['centre']);X=body+c;axis=(np.arange(n)+.5)*h
            lines=[kernel((axis[None,:]-X[:,d,None])/h) for d in range(3)]
            sums=np.array([a.sum(axis=1) for a in lines]);total=np.prod(sums,axis=0)
            partition=float(np.max(np.abs(total-1)));volume=abs(qv@total-V)/V
            quad=np.array([qv@((lines[d]@(axis**2))*np.prod(np.delete(sums,d,axis=0),axis=0)) for d in range(3)])
            error=float(np.max(np.abs(quad-V*(c*c+.2**2/5)))/V)
            assert partition<1e-11 and volume<1e-11
            np.testing.assert_allclose(error,row['quadratic_integral_error_per_volume'],atol=3e-15,rtol=0)
            independent.append({'n':n,'phase':row['phase'],'partition_error':partition,'volume_relative_error':volume,'quadratic_error':error})
        # Dense, independent kernel operator for the representative archive.
        g=z['grid'];X=z['markers'];h=1/16
        A=np.ones((len(X),len(g)))
        for d in range(3):
            # Dense lines indexed onto grid, avoiding the sparse production stencil.
            line=kernel((((np.arange(16)+.5)*h)[None,:]-X[:,d,None])/h)
            idx=np.rint(g[:,d]/h-.5).astype(int);A*=line[:,idx]
        u=z['grid_velocity'];F=z['marker_forces'];sf=A.T@F/h**3;Ju=A@u
        np.testing.assert_allclose(sf,z['grid_force_density'],atol=1e-13,rtol=0)
        np.testing.assert_allclose(Ju,z['interpolated_velocity'],atol=1e-14,rtol=0)
        np.testing.assert_allclose(A.T@qv/h**3,z['smoothed_volume_density'],atol=1e-14,rtol=0)
        power_error=float(abs(h**3*np.sum(u*sf)-np.sum(Ju*F)));assert power_error<1e-11
        force_error=float(np.max(np.abs(h**3*sf.sum(axis=0)-F.sum(axis=0))));assert force_error<1e-11
        torque_error=float(np.max(np.abs(h**3*np.cross(g,sf).sum(axis=0)-np.cross(X,F).sum(axis=0))));assert torque_error<1e-11
    worst=[max(r['quadratic_error'] for r in independent if r['n']==n) for n in (12,16,24)]
    orders=[float(np.log(worst[i]/worst[i+1])/np.log((16,24)[i]/(12,16)[i])) for i in (0,1)]
    assert all(o>=1.5 for o in orders)
    out=BASE/'render_01';out.mkdir(exist_ok=False)
    dump(out/'independent_audit.json',{'audit_passed':True,'new_flow_runs':0,'initial_console_export_failure_preserved':True,'both_attempt_arrays_exactly_equal':True,'independent_phase_checks':independent,'representative_dense_power_error':power_error,'representative_dense_force_error':force_error,'representative_dense_torque_error':torque_error,'quadratic_orders':orders})
    metrics={k:max(r[k] for r in rows) for k in ('partition_error','first_moment_error','volume_relative_error','centroid_error','force_error','torque_error','power_error','uniform_interior_momentum_error','manufactured_force_error')}
    summary='\n'.join(f'| {k.replace("_"," ")} | {value:.3e} |' for k,value in metrics.items())
    report=f'''# Stage36K — conservative immersed-interface candidate

**Operator verification passed; the moving-fluid solver is not yet repaired.**

We selected a fixed-lattice immersed-boundary candidate to avoid binary cover/uncover population deletion. Implemented and tested the four-point transfer kernel and persistent sphere-volume integration. No new fluid time-step simulations were run. Stage36J's seven failed translating-sphere cases remain failed and unchanged.

## Evidence

133 unit tests passed (121 regressions + 12 new). The frozen 27 positions cover N=12,16,24 and nine sub-cell phases. All operator gates pass at the predeclared 1e-11 tolerances. The evaluator independently rebuilt the kernel using dense coordinate lines, checked all 27 quadratic-field integrals, and reconstructed a representative dense transfer matrix, its force/torque totals and power identity.

| Maximum error | Value |
|---|---:|
{summary}

Worst quadratic interior-integral errors divided by sphere volume are {worst[0]:.6g}, {worst[1]:.6g}, {worst[2]:.6g} in unit-box length squared. Observed orders are {orders[0]:.3f}, {orders[1]:.3f}. This is smooth-field interpolation/integration convergence, not flow-solution convergence.

## What changed, and what did not

The candidate leaves computational fluid nodes active even inside the moving object. Marker force is an integrated force, spread as a grid force density; the same kernel interpolates velocity. This preserves discrete force, torque and power identities within the tested non-seam domain. Persistent interior quadrature has analytic sphere volume by construction. Its deposited field is a smoothed indicator, not exact cut-cell occupancy or validated porosity. Constant geometric volume is not evidence of exterior-fluid mass conservation.

The force-accounting candidate includes the rate of change of interior fictitious-fluid momentum: F_h = -F_IB + dP_inside/dt in the stated translation-only, no-other-body-force setting. We verified this with prescribed nonzero target forces and constant acceleration, not forces generated by a fluid solver. Omitting the interior term or using the wrong sign is detected by the tests. Rotational interior dynamics, body-force corrections and two-way motion remain unqualified.

## Literature basis

[Peskin (2002), eq.6.27](https://doi.org/10.1017/S0962492902000077) supplies the four-point kernel and its discrete moment conditions. [Uhlmann (2005), eqs.9–11 and Appendix B](https://arxiv.org/html/1809.08170v1) supplies the fixed-grid forcing framework and interior-fluid momentum term. Uhlmann's original implementation used a three-point kernel and finite differences; this is a new operator prototype, not replication of its validated results.

## Next bounded step

Integrate these operators with a complete CPU fluid step, with an explicit force time level and no-slip solve. Repeat prescribed sphere co-motion, then a nonzero-slip or manufactured nonuniform-flow test that cannot pass with an inactive interface. Independently audit computational mass, exterior-fluid mass, density, slip, interior momentum and net force; study grid, time-step and marker-spacing effects before interpreting drag. No density rescaling or threshold relaxation. Fibre transport and release fractions remain outside the qualified scope.

## Reproducibility

Run: Python stage36_staging/verify_stage36k_interface_v2.py (creates a new immutable directory; refuses an existing one). Analysis: Python stage36_staging/evaluate_render_stage36k_v1.py. Raw results and all dependencies are SHA256-bound in verification_02/verification.json. verification_01 is preserved: numerical artifacts completed, but the final console JSON print raised a NumPy-bool serialization error. The version-2 console fix exited successfully; both attempts' numerical arrays and phase results match exactly. Thus 27 unique operator conditions were evaluated twice, not 54 independent cases. No GPU, production simulation or old evidence was changed.
'''
    (out/'RESULTS.md').write_text(report,encoding='utf-8')
    dump(out/'next_gate.json',{'selected_operator_source':str(ROOT/'stage36_staging/immersed_interface_v1.py'),'selected_operator_sha256':sha(ROOT/'stage36_staging/immersed_interface_v1.py'),'evidence_manifest':str(RAW/'verification.json'),'evidence_sha256':sha(RAW/'verification.json'),'operator_verification_passed':True,'next_scope':'bounded full CPU prescribed sphere immersed-boundary integration; actual exterior mass and nonzero-slip tests required','full_flow_solver_qualified':False,'release_prediction_qualified':False,'production_execution_authorized':False})
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(1,2,figsize=(12,5.5));fig.subplots_adjust(top=.73,bottom=.22,wspace=.35)
    fig.suptitle('Stage36K | A verified interface, not yet a verified moving-flow solver',fontsize=17,y=.97)
    fig.text(.07,.85,'133 unit tests passed  |  27 geometry positions checked  |  0 new flow simulations',fontsize=12)
    ax[0].loglog([12,16,24],worst,'o-',lw=2,color='#247c88',label='Worst of nine phases')
    ax[0].loglog([12,16,24],worst[0]*(12/np.array([12,16,24]))**2,'--',color='#888888',label='Second-order reference')
    ax[0].set_xticks([12,16,24],['12','16','24']);ax[0].xaxis.set_minor_locator(NullLocator())
    ax[0].set(xlabel='Grid points per box side N',ylabel='Quadratic integral error / sphere volume',title='Smooth-field operator convergence')
    ax[0].legend(frameon=False,fontsize=9);ax[0].text(.03,.08,f'Observed order: {orders[0]:.2f}, {orders[1]:.2f}',transform=ax[0].transAxes)
    ax[1].axis('off');ax[1].text(0,.98,'PASSED — interface algebra',color='#247c88',weight='bold',va='top')
    ax[1].text(0,.84,'Velocity interpolation & force spreading\nForce / torque / power identities\nMoving interior-volume integration',va='top',linespacing=1.7)
    ax[1].text(0,.46,'NOT YET VERIFIED — fluid motion',color='#bd5a36',weight='bold',va='top')
    ax[1].text(0,.32,'Exterior-fluid mass conservation\nNo-slip boundary and hydrodynamic drag\nFibre transport or contamination release',va='top',linespacing=1.7)
    fig.text(.07,.07,'Scope: CPU manufactured-field tests. Volume is conserved by quadrature construction, not by a demonstrated fluid solver.\nStage36J failures remain unchanged. Next: complete prescribed-sphere flow benchmark with an active interface.',fontsize=10,color='#555555')
    fig.savefig(out/'interface_verification.png',dpi=180);plt.close(fig)
    dump(out/'render_manifest.json',{'source_hashes':{str(Path(__file__).resolve()):sha(__file__),str(RAW/'verification.json'):sha(RAW/'verification.json')},'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'decision':'operators_only_pass'})
    print(json.dumps(metrics,indent=2));print(out)

if __name__=='__main__':main()
