"""Rebuild individual editable scientific figures from the recorded CSV/JSON."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .validate import OUT

def read(name):
    with (OUT/name).open() as f:return list(csv.DictReader(f))
def save(fig,name):
    folder=OUT/'figures';folder.mkdir(exist_ok=True)
    for ext in ('svg','pdf','png'):fig.savefig(folder/f'{name}.{ext}',bbox_inches='tight',dpi=180)
    plt.close(fig)

def main():
    width=json.loads((OUT/'width_summary.json').read_text())
    fig,ax=plt.subplots(figsize=(7.0,4.4))
    for W,color,marker in [(125,'black','o'),(62.5,'red','s')]:
        rr=sorted([r for r in width if r['interface_width_um']==W],key=lambda x:x['scale'])
        ax.plot([50/r['scale'] for r in rr],[r['force_contrast_pct'] for r in rr],marker=marker,color=color,label=f'Interface parameter W = {W:g} µm')
    ax.set_xscale('log',base=2);ax.set_xticks([6.25,12.5,25],['6.25','12.5','25']);ax.invert_xaxis();ax.axhline(0,color='.7',lw=.7)
    ax.set(xlabel='Grid spacing Δx (µm)',ylabel='Root versus outer force contrast (%)',title='Effect-size sensitivity at fixed gap and endpoint inventories')
    ax.legend(frameon=False);ax.grid(alpha=.15);save(fig,'force_contrast')
    fig,ax=plt.subplots(figsize=(7.0,4.4))
    for W,color,marker in [(125,'black','o'),(62.5,'red','s')]:
        rr=sorted([r for r in width if r['interface_width_um']==W],key=lambda x:x['scale'])
        ax.plot([50/r['scale'] for r in rr],[r['root_laplace_error_pct'] for r in rr],marker=marker,color=color,label=f'W = {W:g} µm')
    ax.axhline(5,color='.5',ls='--',label='5% diagnostic gate');ax.set_xscale('log',base=2);ax.set_xticks([6.25,12.5,25],['6.25','12.5','25']);ax.invert_xaxis()
    ax.set(xlabel='Grid spacing Δx (µm)',ylabel='Pressure–curvature discrepancy (%)',title='Root-dried bridge: bulk pressure versus γ/R')
    ax.legend(frameon=False);ax.grid(alpha=.15);save(fig,'laplace_check')
    # Same source observations; SD represents replicate variation, not CI.
    cups=read('ceramic_frozen_predictions.csv');large=[r for r in cups if r['size']=='large'];x=np.array([float(r['saturation_pct']) for r in large])
    fig,ax=plt.subplots(figsize=(7.0,4.4));ax.errorbar(x,[float(r['observation_cm3']) for r in large],yerr=[float(r['replicate_sd_cm3']) for r in large],fmt='o',color='black',capsize=4,label='Measured large cup, mean ± SD, n=5')
    ax.plot(x,[float(r['prediction_cm3']) for r in large],'s--',color='red',label='Frozen saturated fit; zero bulk-pressure assumption')
    ax.set(xlabel='Initial saturation (%)',ylabel='Water extracted in 20 minutes (cm³)',title='Only the saturated point is an admitted validation case')
    ax.set_xticks([70,85,100]);ax.legend(frameon=False,fontsize=8);ax.grid(alpha=.15);save(fig,'cup_holdout')
    fig,ax=plt.subplots(figsize=(7.0,4.4));r=read('radial_profiles_60s.csv')
    for ts,style in [(0,'--'),(1800,'-.'),(3600,':'),(7200,'-')]:
        a=[p for p in r if abs(float(p['t_s'])-ts)<1e-6]
        ax.plot([float(p['r_m'])*1000 for p in a],[float(p['suction_kPa']) for p in a],ls=style,color='black' if ts!=7200 else 'red',label=f'{ts/3600:g} h')
    ax.set(xlabel='Radial distance from root axis (mm)',ylabel='Matric suction (kPa)',title='Separate radial Richards reference, not LBM or measured data');ax.legend(frameon=False);ax.grid(alpha=.15);save(fig,'radial_reference')
if __name__=='__main__':main()
