"""Same oracle/identity/invalid tests for exact-node v2, with v1 failure bound."""
from pathlib import Path
import sys,types,traceback
import qualify_streaming_metrics_v1 as prior
import streaming_path_metrics_v2 as candidate
api=prior.api;ROOT=prior.ROOT
DESIGN=ROOT/'stage180_designs/incremental_audit_20260924/metric_design_02.json'
OUT=ROOT/'stage180_evaluations/incremental_audit_20260924/metrics_02'


def prepare():
    d=api.read(prior.DESIGN);d.pop('binding')
    d['stage']='Stage180 streaming metric v2 units';d['sources']={str(Path(p).resolve()):api.sha(p) for p in [__file__,prior.__file__,candidate.__file__,candidate.base.__file__,prior.previous.stream_audit.__file__]}
    d['inputs']={str(prior.OUT/'failure.json'):api.sha(prior.OUT/'failure.json'),str(prior.DESIGN):api.sha(prior.DESIGN)}
    d['change']='Return an exact stored node at interpolation endpoints; all oracle tolerances and exact identity tests unchanged.'
    d['binding']=api.digest(d);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def run():
    d=api.read(DESIGN);api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['inputs'])
    cloned=types.FunctionType(prior.run.__code__,{**prior.run.__globals__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT},argdefs=prior.run.__defaults__)
    try:cloned()
    except Exception as e:
        if OUT.exists():api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
