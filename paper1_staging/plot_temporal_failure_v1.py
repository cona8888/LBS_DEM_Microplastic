"""Scientific figure of authenticated rejected numerical comparisons; no simulation."""
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0,str(Path(__file__).resolve().parent))
import compare_core_v2 as c
s=c.s


def main():
    source=s.ROOT/'paper1_evaluations/fibre_accuracy_diagnosis_20261015/results.json'
    diagnosis=s.fields.sealed(source)
    s.api.verify_mapping(diagnosis['inputs']);s.api.verify_mapping(diagnosis['source_files'])
    s.require(diagnosis['new_transport_steps']==0 and not diagnosis['core_case_admission'], 'Rejected-path diagnostic only')
    gate=s.q.job.policy.GATES['mean_L1_q_over_U_max']
    s.require(gate==s.q.job.policy.GATES['endpoint_q_over_U_max']==.005, 'Original unchanged velocity gates')
    destination=source.parent/'render_01';destination.mkdir(exist_ok=False)
    colors=('#2166ac','#c55c00');labels=('0.125 vs 0.0625','0.0625 vs 0.03125')
    figure,axes=plt.subplots(1,2,figsize=(11.2,4.8),gridspec_kw={'width_ratios':[1.8,1]})
    figure.subplots_adjust(left=.075,right=.98,bottom=.22,top=.79,wspace=.31)
    figure.suptitle('Low-flow AR4 fibre: full-path temporal accuracy rejected',fontsize=14,y=.97)
    figure.text(.5,.90,'Same placement, packing, physics and 0.01-PV exposure; original gates retained',ha='center',fontsize=10)
    ax=axes[0]
    for item,color,label in zip(diagnosis['pairs'],colors,labels):
        bins=item['diagnosis']['bins'];mid=[(x['start_s']+x['stop_s'])/2 for x in bins]
        ax.plot(mid,[x['mean_q_error_over_U'] for x in bins],'-o',color=color,label=label,markersize=3.5,lw=1.6)
    ax.axhline(gate,color='#a40000',ls='--',lw=1.3,label='Original whole-path limit (reference)')
    ax.axvspan(.37306383473550975,.42306383473550975,color='#777777',alpha=.16,label='Proposed local diagnostic interval')
    ax.set(xlabel='Physical time (s)',ylabel=r'Time-bin mean $\|\Delta q\|/U$',yscale='log',xlim=(0,.9364396280429768),ylim=(3e-5,.12))
    ax.set_title('Early differences decrease; late differences do not',fontsize=10,pad=9)
    ax.grid(axis='y',which='major',alpha=.2);ax.legend(loc='upper left',fontsize=8,framealpha=.94)
    ax=axes[1];x=np.arange(2);width=.33
    for index,(item,color) in enumerate(zip(diagnosis['pairs'],colors)):
        d=item['diagnosis'];values=[d['endpoint_q_over_U_max'],d['mean_L1_q_over_U_max']]
        bars=ax.bar(x+(index-.5)*width,values,width,color=color)
        ax.bar_label(bars,labels=[f'{v:.4f}' for v in values],fontsize=8,padding=3)
    ax.axhline(gate,color='#a40000',ls='--',lw=1.3)
    ax.set(xticks=x,xticklabels=['Endpoint','Whole-path\ntime mean'],ylabel=r'Original velocity error $\|\Delta q\|/U$',ylim=(0,.034))
    ax.set_title('Both original velocity gates fail',fontsize=10,pad=9);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    figure.text(.075,.10,r'$q=(v,a\omega)$; $U$ is the achieved mean flow. Bins use accepted physical-interval durations.',fontsize=9)
    figure.text(.075,.055,'Dashed line is the whole-path limit; time bins are not separate acceptance gates. Shading is a proposed, unexecuted replay.',fontsize=8.5)
    for suffix in ('png','pdf','svg'):figure.savefig(destination/f'temporal_failure.{suffix}',dpi=170)
    plt.close(figure)
    files={str(p):s.sha(p) for p in destination.iterdir() if p.is_file()}
    s.seal(destination,dict(passed=True,new_transport_steps=0,scope='Diagnostic scientific figure of two rejected complete numerical paths; no case admission.',
        input_files={str(source):s.sha(source)},source_files={str(Path(__file__).resolve()):s.sha(Path(__file__))},
        artifacts=files,original_velocity_limit=gate,local_replay_executed_at_render=False,utc=s.utc()))
    print('TEMPORAL_FAILURE_FIGURE',s.sha(destination/'results.json'),flush=True)


if __name__=='__main__':main()
