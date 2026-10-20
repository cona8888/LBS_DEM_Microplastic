"""V1 empty-contact negative-control indexing repaired; physics gates identical."""
from pathlib import Path
import inspect
import audit_failed_preflight_v1 as original
api,job=original.api,original.job
OUT=job.OUT/'failed_preflight_independent_02'

def corrupt_gap(record,field):
    calls=record['normal_gap_operand_policy']['prepare_calls']
    active=next((c for c in calls if c['contacts']),None)
    if field=='gap':
        if active is None:calls[0]['effective_gaps_m'].append(1e-10)
        else:active['effective_gaps_m'][0]+=1e-10
    else:
        if active is None:calls[0]['contacts'].append([999,1e-10,[1.,0.,0.],[0.,0.,0.]])
        else:active['contacts'][0][1]+=1e-10

source=inspect.getsource(original.run)
changes={
 "bad['normal_gap_operand_policy']['prepare_calls'][0]['effective_gaps_m'][0]+=1e-10":"corrupt_gap(bad,'gap')",
 "bad['normal_gap_operand_policy']['prepare_calls'][0]['contacts'][0][1]+=1e-10":"corrupt_gap(bad,'raw_gap')",
 "(Path(__file__),job.DESIGN,w.WORK,pre.OUT/'failure.json')":"(Path(__file__),Path(original.__file__),job.OUT/'failed_preflight_independent_01/failure.json',job.DESIGN,w.WORK,pre.OUT/'failure.json')"
}
for before,after in changes.items():
    api.require(source.count(before)==1,'exact empty-contact diagnostic-only substitution')
    source=source.replace(before,after)
ns=dict(original.__dict__,__file__=__file__,OUT=OUT,original=original,corrupt_gap=corrupt_gap)
exec(compile(source,__file__+'::unchanged_independent_physical_audit','exec'),ns)
if __name__=='__main__':ns['run']()
