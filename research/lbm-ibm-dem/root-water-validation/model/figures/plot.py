"""Plot source data with physical axes. From repo root: make figures.
Each figure folder is also independently reproducible: python plot.py
"""
from pathlib import Path
import csv,shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parent.parent
STYLE={'svg.fonttype':'none','pdf.fonttype':42,'font.family':'DejaVu Sans','font.size':10,
       'axes.spines.top':False,'axes.spines.right':False,'axes.labelpad':8}

plt.rcParams.update(STYLE)

def formatting(ax):
    ax.grid(axis='y',alpha=.22);ax.set_axisbelow(True)

def save(fig,out):
    fig.tight_layout()
    for ext in ('pdf','svg','png'):
        fig.savefig(out/f'figure.{ext}',dpi=160,bbox_inches='tight',facecolor='white')
        if ext=='svg':
            svg=out/'figure.svg'; svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)

def opening(out):
    fig,ax=plt.subplots(figsize=(6.8,4.35));formatting(ax)
    for fname,ls in [('history_50um.csv','-'),('history_25um.csv','--')]:
        with (out/fname).open() as f: data=list(csv.DictReader(f))
        for mode,c in [('root','#97501f'),('outer','#11676f')]:
            subset=[r for r in data if r['mode']==mode];cond=[r for r in subset if r['stage']=='conditioning'][-1]
            points=[cond]+[r for r in subset if r['stage']=='opening']
            ax.plot([float(r['opening_m'])*1e6 for r in points],[-float(r['grain_capillary_N_m']) for r in points],color=c,ls=ls,lw=2)
    ax.set(xlabel='Support opening after drying (µm)',ylabel='Attractive force per unit depth (N/m)',xlim=(0,76))
    ax.legend(handles=[Line2D([],[],color='#97501f',lw=2,label='Root uptake'),Line2D([],[],color='#11676f',lw=2,label='Outer drainage'),Line2D([],[],color='.35',lw=1.6,label='50 µm grid'),Line2D([],[],color='.35',lw=1.6,ls='--',label='25 µm grid')],ncol=2,frameon=False,loc='lower left',fontsize=9)
    save(fig,out)

def geometry(out):
    fig,ax=plt.subplots(figsize=(6.7,4.1));t=[]
    for mode,c,ls in [('outer','#11676f','--'),('root','#97501f','-')]:
        data=np.genfromtxt(out/f'{mode}_field.csv',delimiter=',',names=True); ny=len(np.unique(data['y_m'])); nx=len(data)//ny
        X,Y=[data[k].reshape(ny,nx)*1e3 for k in ('x_m','y_m')]; ids=data['solid_id'].reshape(ny,nx);phi=data['phi'].reshape(ny,nx)
        if mode=='root':
            ax.contourf(X,Y,(ids>0).astype(float),levels=[.5,1.5],colors=['#e2e1dd'],zorder=1)
            ax.contour(X,Y,ids>0,levels=[.5],colors=['#aaa9a5'],linewidths=.8,zorder=2)
        ax.contour(X,Y,phi,levels=[0],colors=[c],linestyles=[ls],linewidths=2,zorder=3)
        t.append(Line2D([],[],ls=ls,color=c,lw=2,label=('Root uptake' if mode=='root' else 'Outer drainage')))
    ax.text(1.72,1.63,'Root',ha='center',va='center',fontweight='bold',color='#484744');ax.text(3.42,1.65,'Grain',ha='center',va='center',fontsize=9,color='#484744')
    ax.set(xlim=(1.6,3.86),ylim=(.88,2.5),xlabel='Horizontal position (mm)',ylabel='Vertical position (mm)',aspect='equal');ax.legend(handles=t[::-1],frameon=False,loc='upper left',fontsize=9)
    save(fig,out)

if __name__=='__main__':
    local=Path(__file__).resolve().parent
    if (local/'history_50um.csv').exists():opening(local)
    elif (local/'outer_field.csv').exists():geometry(local)
    else:
        for name,fun,files in [('01_opening',opening,{'history_50um.csv':'history.csv','history_25um.csv':'space_refinement/history.csv'}),('02_meniscus',geometry,{'root_field.csv':'field_root_opened.csv','outer_field.csv':'field_outer_opened.csv'})]:
            out=local/name;out.mkdir(exist_ok=True)
            for dest,source in files.items():shutil.copyfile(ROOT/'results'/source,out/dest)
            shutil.copyfile(Path(__file__),out/'plot.py');fun(out)
