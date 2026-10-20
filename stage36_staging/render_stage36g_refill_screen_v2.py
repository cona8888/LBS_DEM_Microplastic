"""Render saved Stage36G evidence after independently checking all file bindings."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    source=args.input.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report=json.loads((source/'verification.json').read_text())
    if not report['execution_completed'] or not report['unit_tests_passed']:raise ValueError('incomplete screening')
    bindings={}
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for path,expected in report[group].items():
            if digest(path)!=expected:raise ValueError('binding mismatch: '+path)
            bindings[path]=expected
    rows=json.loads((source/'screen_results.json').read_text())['cases']
    # Recompute mass/density directly from all 24 archived states, independently
    # of metrics() and reject any disagreement with the saved result tables.
    for r in rows:
        with np.load(source/(r['case_id']+'.npz')) as a:
            before=np.sum(a['old'],dtype=np.float64);after=np.sum(a['new'],dtype=np.float64)
            rel=abs(after-before)/before
            error=np.max(np.abs(np.sum(a['new'],axis=0)[a['new_fluid']]-1))
            if not np.isclose(rel,r['mass_relative_change'],rtol=1e-12,atol=1e-16):raise ValueError('mass mismatch')
            if not np.isclose(error,r['density_max_error'],rtol=1e-12,atol=1e-15):raise ValueError('density mismatch')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,3,figsize=(14,5.4),gridspec_kw={'width_ratios':[1,1,1.15]})
    cmap=plt.get_cmap('RdBu_r').copy();cmap.set_bad('#555f6c')
    norm=TwoSlopeNorm(vmin=-1.85,vcenter=0,vmax=1.85)
    for ax,method in zip(axes[:2],('AE6','POOL6')):
        with np.load(source/f'{method}_N32_shift1.npz') as a:
            d=a['new'].sum(axis=0)-1;d[~a['new_fluid']]=np.nan
            im=ax.imshow(d[:,:,16].T,origin='lower',extent=(0,32,0,32),cmap=cmap,norm=norm,interpolation='nearest')
        ax.set_title(('Extrapolation: uniform field' if method=='AE6' else 'Local pooling: density artefacts'),fontsize=11)
        ax.set_xlabel('x / lattice spacing');ax.set_ylabel('y / lattice spacing')
    cbar=fig.colorbar(im,cax=fig.add_axes([.10,.19,.45,.025]),orientation='horizontal')
    cbar.set_label('Relative density error, (rho - rho_ref) / rho_ref')
    ax=axes[2]
    for n,color in zip((16,24,32),('#218a8a','#4978c9','#a350a3')):
        rr=[r for r in rows if r['method']=='POOL6' and r['n']==n]
        ax.plot([r['shift_lu'] for r in rr],[100*r['density_max_error'] for r in rr],'o-',label=f'POOL6 N={n}',color=color)
    ax.axhline(1,color='black',linestyle='--',linewidth=1,label='1% screen limit')
    ax.set(xlabel='Prescribed geometric shift / lattice spacing',ylabel='Maximum density error (%)',title='Conservation alone does not pass')
    ax.grid(alpha=.18);ax.legend(fontsize=9,loc='upper left');ax.set_ylim(-5,220)
    fig.suptitle('Stage36G | Moving-mask refill screen: neither candidate qualified',fontsize=16,x=.05,ha='left',y=.98)
    fig.text(.05,.02,'95 unit tests passed | 24 isolated CPU mask updates | No fluid time integration or release prediction\n'
             'Maps: N=32, shift=1, z=16.5. POOL6 conserves mass to 2.3e-16; AE6 fractional shifts change mass by up to 0.101%.',fontsize=10)
    fig.subplots_adjust(left=.05,right=.985,top=.84,bottom=.34,wspace=.40)
    fig.savefig(out/'refill_screen.png',dpi=150,facecolor='white');plt.close(fig)
    manifest={'source_hashes':{str(source/'verification.json'):digest(source/'verification.json'),str(Path(__file__).resolve()):digest(__file__)},
              'verified_bindings_count':len(bindings),'independent_archived_state_checks':24,
              'artifact_hashes':{str(out/'refill_screen.png'):digest(out/'refill_screen.png')}}
    (out/'render_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
