"""Zero-step boundary/mutation checks before the immutable preflight launch."""
from pathlib import Path
import copy,os,psutil
import contact_repaired_stack_preflight_v1 as w
job,api=w.job,w.api
OUT=job.OUT/'prelaunch_01'
def run():
    d=api.read(job.DESIGN);job.verify(d);w.ledger();other=[]
    for p in psutil.process_iter(['name','cmdline']):
        if p.pid!=os.getpid() and 'python' in (p.info['name'] or '').lower():other.append({'pid':p.pid,'argv':p.info['cmdline']})
    api.require(not other,'no competing Python simulation or unresolved evaluator process')
    mutations=[('physics',lambda b:b['cases'][0]['spec']['config'].update(friction_coefficient=.31)),('gates',lambda b:b['numerical_gates'].update(whole_position_over_b_max=.1)),('workers',lambda b:b['budget'].update(workers=6)),('seed',lambda b:b.update(stress_case='unbound')),('deadline',lambda b:b.update(simulation_cutoff_utc='2030-01-01T00:00:00+00:00')),('production',lambda b:b.update(production_authorized=True)),('step_budget',lambda b:b['preflight'].update(maximum_new_steps=18000))]
    rejected=[]
    for name,change in mutations:
        bad=copy.deepcopy(d);change(bad);bad.pop('binding');bad['binding']=api.digest(bad)
        try:job.verify(bad)
        except (ValueError,RuntimeError,AssertionError):rejected.append(name)
        else:raise AssertionError('accepted corrupt design '+name)
    api.require(len(rejected)==len(mutations),'all corrupt amendments rejected')
    disk=job.shutil.disk_usage(job.ROOT).free;api.require(disk>d['budget']['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED,'bounded temporary archive reserve')
    result={'passed':True,'new_trajectory_steps':0,'design_sha256':api.sha(job.DESIGN),'source_sha256':api.sha(__file__),'rejected':rejected,'other_python_processes':other,'free_bytes':disk,
            'old_stage200_evaluator':{'pid_present':psutil.pid_exists(40572),'evaluation_output_present':(w.ROOT/'stage200_evaluations/revised_deadline_campaign_20260927/evaluation_01').exists(),'status':'unresolved: previously running process absent and no output, no exit cause inferred or retry launched'},'utc':job.utc().isoformat()}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('PRELAUNCH_PASS',rejected,flush=True)
if __name__=='__main__':run()
