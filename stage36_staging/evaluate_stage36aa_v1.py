import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def main():
    avg=ROOT/'stage36_evaluations/stage36aa_cell_averaged_source_20260909/verification_01';point=ROOT/'stage36_evaluations/stage36w_spatial_flow_20260908/verification_01'
    av=json.loads((avg/'manifest.json').read_text());pv=json.loads((point/'manifest.json').read_text());assert av['completed'] and pv['completed'] and not (avg/'failure.json').exists()
    for manifest,data in ((avg,av),(point,pv)):
        for group in ('source_hashes','parent_hashes','artifact_hashes'):
            for p,h in data[group].items():assert sha(p)==h,p
    rows=[]
    for n in (12,16,24):
        ar=next(r for r in av['cases'] if r['n']==n);pr=next(r for r in pv['cases'] if r['n']==n);h=json.loads((avg/f'n{n}_history.json').read_text());assert len(h)==n*n
        for e in h:np.testing.assert_allclose(np.array(e['unsubtracted_force'])-np.array(e['interior_source_force']),e['force'],rtol=0,atol=1e-15)
        for required in ('first','states','source_components'):assert (avg/f'n{n}_{required}.npz').exists()
        rows.append({'n':n,'point_force':pr['max_force_error'],'average_force':ar['max_force_error'],'point_velocity':max(pr['quarter_velocity_errors']),'average_velocity':max(ar['quarter_velocity_errors']),'force_change':ar['max_force_error']-pr['max_force_error'],'velocity_change':max(ar['quarter_velocity_errors'])-max(pr['quarter_velocity_errors'])})
    out=avg.parent/'analysis_02';out.mkdir(exist_ok=False)
    fig,ax=plt.subplots(1,2,figsize=(9,4));ns=[r['n'] for r in rows]
    for key,label,style in (('point_force','Point sampled','o-'),('average_force','Cell averaged','s-')):ax[0].plot(ns,[100*r[key] for r in rows],style,label=label)
    for key,label,style in (('point_velocity','Point sampled','o-'),('average_velocity','Cell averaged','s-')):ax[1].plot(ns,[100*r[key] for r in rows],style,label=label)
    for a,title in zip(ax,('Maximum force error','Worst-quarter exterior velocity error')):a.axhline(2,color='k',ls='--',label='2% gate');a.set(xlabel='Grid N',ylabel='Error (%)',title=title);a.set_xticks(ns);a.grid(alpha=.25);a.legend()
    fig.suptitle('Stage36AA source-discretization comparison — all sphere cases fail');fig.tight_layout();fig.savefig(out/'comparison.png',dpi=160);plt.close(fig)
    (out/'comparison.json').write_text(json.dumps(rows,indent=2))
    lines=['# Stage36AA — cell-averaged source comparison','', 'Three new bounded CPU flows completed with all health gates passing. Source averaging was the sole numerical intervention; the analytical comparator and 2% gates were unchanged.','', '| Grid | Force: point → averaged | Velocity: point → averaged |','|---|---:|---:|']
    for r in rows:lines.append(f"| {r['n']}³ | {r['point_force']:.2%} → {r['average_force']:.2%} | {r['point_velocity']:.2%} → {r['average_velocity']:.2%} |")
    lines+=['','Cell averaging modestly reduces the worst-quarter velocity error at N16 and N24, but worsens force error at every grid. At N24 the velocity error falls from 160.10% to 142.75%, while force error rises from 11.49% to 15.06%. Therefore cell-centre source sampling is not the sole cause and this intervention does not qualify the manufactured sphere problem.','', 'This outcome points to coupled inconsistency among compact-source representation, immersed-boundary enforcement and force extraction. Do not select the averaged scheme as an improvement based on one observable. The next lowest-cost test should freeze N24 and separate the source support from the immersed interface while preserving the same continuum field family; that is a diagnostic sensitivity test, not validation. No permeability, drag or release fraction is qualified.']
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'completed':True,'analytical_passed':False,'new_flow_solves':0,'source_hash':sha(__file__),'parent_hashes':{str(avg/'manifest.json'):sha(avg/'manifest.json'),str(point/'manifest.json'):sha(point/'manifest.json')},'artifact_hashes':{str(p):sha(p) for p in out.iterdir()}},indent=2));print('\n'.join(lines).encode('ascii','replace').decode())
if __name__=='__main__':main()
