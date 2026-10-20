"""JSON round-trip split-run equivalence on a near-static contact state."""
import json,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage106_staging'),str(ROOT/'stage104_staging')]
import trajectory_checkpoint_core_v2 as core
import trajectory_failure_only_rescue_v1 as parent
h=parent.h
oldcore=h.candidate.parent.parent.core
OUT=ROOT/'stage106_evaluations/checkpoint_recovery_01'
CASE=ROOT/'stage96_runs/population_prefix_01/s2_i0_prolate_ar4.json'
class Runner:
    checkpoint=None
    pause=None
    binding=''
    @classmethod
    def integrate(cls,*args,**kwargs):
        old=oldcore.integrate
        def trampoline(*a,**kw):
            core.inertial=oldcore.inertial
            return core.integrate(*a,**kw,checkpoint=cls.checkpoint,checkpoint_binding=cls.binding,pause_after_steps=cls.pause)
        oldcore.integrate=trampoline
        try:return parent.integrate(*args,**kwargs)
        finally:oldcore.integrate=old
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(h.DESIGN.read_text());state=json.loads(CASE.read_text())['result']
    for key in ('max_dt_s','relaxation_fraction','displacement_fraction','angle_limit_rad'):cfg['numerics'][key]/=4
    sources={str(Path(m.__file__).resolve()):h.sha(m.__file__) for m in list(sys.modules.values())
      if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents}
    _,_,_,_,files=h.matrix_case_v1.load(2)
    bindings={str(p):h.sha(p) for p in (CASE,h.DESIGN,*files)}
    Runner.binding=core.hashlib.sha256(json.dumps([sources,bindings],sort_keys=True).encode()).hexdigest()
    h.dump(OUT/'protocol.json',dict(source_hashes=sources,input_hashes=bindings,binding=Runner.binding,horizon_s=.01,pause_after_steps=5,
      scope='Local numerical restart verification. Does not reconstruct missing state of old release runs.'))
    reference=h.run_local(parent,cfg,state,2,.01,30.)
    full=h.run_local(Runner,cfg,state,2,.01,30.)
    Runner.pause=5
    split=h.run_local(Runner,cfg,state,2,.01,30.)
    h.dump(OUT/'pause.json',split)
    Runner.checkpoint=json.loads((OUT/'pause.json').read_text())['checkpoint'];Runner.pause=None
    resumed=h.run_local(Runner,cfg,state,2,.01,30.)
    for name,r in [('reference',reference),('full',full),('resumed',resumed)]:h.dump(OUT/f'{name}.json',r)
    ignored={'runtime_seconds','checkpoint','nullspace_rescue','short_pgs_seed_stats','fail_fast_sweep_stats','within_pose_reuse_stats'}
    normalize=lambda r:json.loads(json.dumps({k:v for k,v in r.items() if k not in ignored},default=h.json_value))
    checks=dict(reference_complete=reference['status']=='present_at_horizon',pause_reached=split['status']=='paused_checkpoint',
      unchanged_core=normalize(reference)==normalize(full),exact_split_equivalence=normalize(full)==normalize(resumed))
    cp=Runner.checkpoint
    for name in ('binding','state'):
        Runner.checkpoint=copy.deepcopy(cp)
        if name=='binding':Runner.checkpoint['contract']='wrong'
        else:Runner.checkpoint['state']['t']+=1
        try:h.run_local(Runner,cfg,state,2,.01,30.)
        except ValueError:checks[name+'_tampering_rejected']=True
        else:checks[name+'_tampering_rejected']=False
    result=dict(passed=all(checks.values()),checks=checks,paused_time_s=split['time_s'],
      artifact_hashes={str(p):h.sha(p) for p in OUT.glob('*.json')})
    h.dump(OUT/'results.json',result);h.dump(OUT/'completion.json',dict(status='complete_passed' if result['passed'] else 'complete_failed',results_sha256=h.sha(OUT/'results.json')))
    print(json.dumps(result,default=h.json_value))
if __name__=='__main__':main()
