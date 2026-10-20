"""Unchanged local protocol/gates using the version-2 contact fallback."""
import sys
import verify_reduced_repair_v2 as updated
import local_regression_v1 as job
job.repair=updated.revised
job.DESIGN=updated.base.DESIGN.with_name('local_protocol_02.json')
job.OUT=updated.base.EVAL/'local_evaluation_01'
job.RUN=updated.base.RUN
api=job.api


def prepare():
    unit=updated.base;inherited=api.read(unit.DESIGN);unit.verify(inherited)
    inputs={}
    for folder in [unit.EVAL/'units_01',unit.EVAL/'refined_units_01']:
        r=api.read(folder/'results.json');seal=api.read(folder/'completion.json')
        api.require(r['passed'] and seal['results_sha256']==api.sha(folder/'results.json'),'version-2 unit seals')
        for path in [folder/'results.json',folder/'completion.json']:inputs[str(path)]=api.sha(path)
    inputs[str(unit.DESIGN)]=api.sha(unit.DESIGN)
    d={'stage':'Stage169_local_v2','upstream_design_sha256':api.sha(unit.DESIGN),'budget':inherited['budget'],'limits':inherited['limits'],
        'factors':inherited['factors_relative_to_stage167_fine'],'horizon_s':inherited['local_horizon_s'],
        'source_checkpoint':inherited['source_checkpoint'],'failed_segment':inherited['failed_segment'],
        'fixed_stop':'600-second local wall ceiling, 25,000 accepted test steps, three levels only. No long trajectories.',
        'restart_lengths':[100,37,63],'sources':job.parent.source_map(),'inputs':inputs}
    d['binding']=api.digest(d);api.write(job.DESIGN,d);print('LOCAL V2 FROZEN',api.sha(job.DESIGN),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:job.run()
    else:raise ValueError('prepare or run')
