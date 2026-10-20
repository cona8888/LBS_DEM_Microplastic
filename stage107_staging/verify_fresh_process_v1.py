"""Fresh interpreter and synthetic active-recovery restart checks."""
import copy,json,sys,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage106_staging'))
import verify_checkpoint_v2 as lib
h=lib.h
BASE=ROOT/'stage106_evaluations/checkpoint_equivalence_02'
OUT=ROOT/'stage107_evaluations/fresh_process_01'
WORKER=Path(__file__).with_name('checkpoint_worker_v1.py')
def normal(r):
    skip={'runtime_seconds','checkpoint','nullspace_rescue','short_pgs_seed_stats','fail_fast_sweep_stats','within_pose_reuse_stats'}
    return {k:v for k,v in r.items() if k not in skip}
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    protocol=json.loads((BASE/'protocol.json').read_text())
    bindings={**protocol['source_hashes'],**protocol['input_hashes'],str(WORKER):h.sha(WORKER),str(Path(__file__)):h.sha(__file__)}
    for p,d in bindings.items():
        if h.sha(p)!=d:raise RuntimeError('prerequisite binding drift')
    cp=json.loads((BASE/'pause.json').read_text())['checkpoint']
    h.dump(OUT/'protocol.json',dict(bindings=bindings,parent_pid=os.getpid(),synthetic_recovery_test=True,
      scope='Numerical restart tests, not physical release observations.'))
    def worker(name,checkpoint,pause=None):
        path=OUT/f'{name}_job.json';output=OUT/f'{name}.json'
        h.dump(path,dict(bindings=bindings,binding=protocol['binding'],checkpoint=checkpoint,pause=pause,output=str(output)))
        run=subprocess.run([sys.executable,str(WORKER),str(path)],capture_output=True,text=True)
        h.dump(OUT/f'{name}_process.json',dict(returncode=run.returncode,stdout=run.stdout,stderr=run.stderr))
        if run.returncode:raise RuntimeError('worker failed: '+run.stderr)
        return json.loads(output.read_text())
    natural=worker('natural',cp)
    reference=json.loads((BASE/'resumed.json').read_text())
    synthetic=copy.deepcopy(cp);synthetic['state']['recovery']=True
    synthetic['state_sha256']=lib.core.hashlib.sha256(json.dumps(synthetic['state'],sort_keys=True,allow_nan=True).encode()).hexdigest()
    # This is a declared synthetic mode flag, not an alteration to saved evidence.
    full=worker('active_full',synthetic)
    paused=worker('active_pause',synthetic,6)
    if paused['result']['status']!='paused_checkpoint':raise RuntimeError('active case did not pause')
    resumed=worker('active_resumed',paused['result']['checkpoint'])
    checks=dict(natural_exact=normal(natural['result'])==normal(reference),
      active_exact=normal(full['result'])==normal(resumed['result']),
      active_complete=full['result']['status']==resumed['result']['status']=='present_at_horizon',
      active_flag_preserved=paused['result']['checkpoint']['state']['recovery'] is True,
      separate_processes=len({natural['pid'],full['pid'],paused['pid'],resumed['pid'],os.getpid()})==5)
    result=dict(passed=all(checks.values()),checks=checks,artifact_hashes={str(p):h.sha(p) for p in OUT.glob('*.json')})
    h.dump(OUT/'results.json',result);h.dump(OUT/'completion.json',dict(status='complete_passed' if result['passed'] else 'complete_failed',results_sha256=h.sha(OUT/'results.json')))
    print(json.dumps(result))
if __name__=='__main__':main()
