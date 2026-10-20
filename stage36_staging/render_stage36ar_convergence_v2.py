"""Static scientific figure of the solved radial reference, from saved results."""
import json,hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'stage36_evaluations/stage36ar_sharp_radial_20260911'
OUT=BASE/'render_02'
def main():
    OUT.mkdir(exist_ok=False)
    p=BASE/'verification_01/results.json';r=json.loads(p.read_text());assert all(r['checks'].values())
    rows=r['rows'];n=[x['intervals'] for x in rows];errors=np.array([x['drag_relative_error'] for x in rows])*100
    fig,ax=plt.subplots(figsize=(8.5,5.4))
    ax.loglog(n,errors,'o-',color='#157d87',lw=2,ms=8,label='Numerically solved drag error')
    ax.axhline(1,color='#ad632a',ls='--',label='1% finest-resolution acceptance limit')
    for xx,yy in zip(n,errors):ax.annotate(f'{yy:.3f}%',(xx,yy),xytext=(8,8),textcoords='offset points',fontsize=11)
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xticks(n,[str(x) for x in n]);ax.set_xlim(80,520);ax.set_ylim(.025,2.2)
    ax.set_xlabel('Radial intervals (not 3-D grid dimensions)');ax.set_ylabel('Relative drag error (%)')
    ax.set_title('Sharp-boundary sphere: numerical convergence',loc='left',weight='bold',pad=15)
    ax.grid(which='both',alpha=.2);ax.legend(loc='lower left',fontsize=9)
    fig.text(.12,.035,'Isolated, axisymmetric Stokes flow; exact outer velocity data.\nSphere-specific reference only — the 3-D fibre/soil solver remains unqualified.',fontsize=9,color='#435466')
    fig.subplots_adjust(left=.12,right=.97,bottom=.22,top=.89)
    fig.savefig(OUT/'convergence.png',dpi=160);plt.close(fig)
    manifest={'result_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
              'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'image_sha256':hashlib.sha256((OUT/'convergence.png').read_bytes()).hexdigest(),
              'status':'rendered_pending_visual_check'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
