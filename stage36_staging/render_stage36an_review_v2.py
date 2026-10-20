"""Render measured optimization and the proposed modelling hierarchy."""
import hashlib
import json
from pathlib import Path
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'stage36_evaluations/stage36an_optimization_review_20260910'
OUT=BASE/'render_02'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=False)
    result=BASE/'verification_02/results.json'
    r=json.loads(result.read_text())
    assert r['status']=='pass' and all(r['checks'].values())
    fig=plt.figure(figsize=(12,7.2),facecolor='#f8fafc')
    fig.text(.05,.935,'Microplastics in soil flow: lighter computation, explicit limits',fontsize=18,weight='bold',color='#14334b')
    fig.text(.05,.895,'Stage36AN  |  10 September 2026  |  Existing evidence preserved; no production transport run',fontsize=10,color='#506477')
    ax=fig.add_axes([.08,.57,.37,.23])
    vals=[1000*statistics.median(r['seconds_per_step'][k]) for k in ['reference','optimized']]
    ax.barh([1,0],vals,color=['#8896a5','#178c89'],height=.5)
    ax.set_yticks([1,0],['Reference','Selected v2'])
    ax.set_xlim(0,85)
    for y,v in zip([1,0],vals): ax.text(v+1,y,f'{v:.1f} ms',va='center',fontsize=11)
    ax.set_xlabel('CPU time per step (lower is better)',fontsize=10)
    ax.set_title('Measured: 21.8% less step time',loc='left',fontsize=13,weight='bold',pad=15)
    ax.spines[['top','right']].set_visible(False)
    fig.text(.08,.414,'N32; three 16-step repetitions; warmup excluded.\n64 startup + 32 stationary regression steps: exact population match.\n11/11 bounded checks passed; not a whole-campaign benchmark.',fontsize=9,color='#506477',linespacing=1.6)
    bx=fig.add_axes([.56,.53,.38,.27]); bx.axis('off')
    bx.text(0,1,'Scientific readiness',fontsize=13,weight='bold',color='#14334b')
    bx.text(0,.79,'Fixed-fibre hydraulic contrasts',fontsize=11,weight='bold',color='#178c89')
    bx.text(0,.64,'Selected CPD4 ratio shifts < 0.000488.\nNumerical verification, not experimental validation.',fontsize=10,color='#506477',linespacing=1.5)
    bx.text(0,.36,'Mobile-particle forces: NOT qualified',fontsize=11,weight='bold',color='#ac4824')
    bx.text(0,.12,'Corrected sphere drag / benchmark = 1.328.\nThe force time-level bug is fixed; the drag error remains.',fontsize=10,color='#506477',linespacing=1.5)
    fig.text(.05,.337,'Recommended architecture — proposed, not yet a qualified transport model',fontsize=12,weight='bold',color='#14334b')
    boxes=[('1  Resolve reference flow','Fixed soil; verified drag\nand pore-constriction tests'),('2  Track particle shape','Capsule chains; anisotropic\ndrag, torque and contact'),('3  Refresh + account','Recompute obstructed flow;\ntrack retained/exported mass')]
    for i,(title,body) in enumerate(boxes):
        x=.05+i*.31
        fig.add_artist(FancyBboxPatch((x,.145),.28,.145,boxstyle='round,pad=0.012',transform=fig.transFigure,facecolor='#e7f1f3',edgecolor='#c5dbe0'))
        fig.text(x+.012,.245,title,fontsize=11,weight='bold',color='#14334b')
        fig.text(x+.012,.187,body,fontsize=10,color='#344e60',linespacing=1.5)
        if i<2: fig.text(x+.287,.211,'→',fontsize=20,color='#178c89')
    fig.text(.05,.065,'Boundary: pulse-injection recovery ≠ release from initially contaminated soil. No validated release fraction yet.',fontsize=10,color='#ac4824')
    fig.savefig(OUT/'review.png',dpi=160,facecolor=fig.get_facecolor())
    plt.close(fig)
    inputs=[result,BASE/'REVIEW.md',Path(__file__)]
    (OUT/'manifest.json').write_text(json.dumps({'status':'rendered_pending_visual_review','inputs':{str(p):sha(p) for p in inputs},'png_sha256':sha(OUT/'review.png')},indent=2))
    print(OUT/'review.png')

if __name__=='__main__':main()
