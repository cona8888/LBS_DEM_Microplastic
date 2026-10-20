"""Seal both attempts honestly: canonical pass, moving refinement incomplete."""
from pathlib import Path
import sys
import numpy as np
import verify_rigid_rotation_v2 as wrapper

w=wrapper.workflow
api=w.api
ROOT=w.ROOT
OUT=ROOT/'stage151_evaluations'/'bounded_rigid_rotation_runtimefix_20260921'/'independent_audit_01'


def main():
    d=api.read(w.DESIGN);w.verify(d)
    api.require(api.read(wrapper.FAILURE)['error'].startswith('AttributeError'),'preserved interface failure')
    api.require(api.read(w.OUT/'failure.json')['error']=="RuntimeError('bounded moving-fibre gate failed; no automatic extension')",'expected bounded failure')
    canonical=api.read(w.OUT/'canonical.json');api.require(canonical['passed'],'canonical mechanics')
    api.require(api.read(w.OUT/'checkpoint_negative.json')['wrong_mode_rejected'],'wrong-model checkpoint rejection')
    w.prior.parent.old.prior.prior.configure()
    baseline=api.read(w.OUT/'quasistatic.json');items=[];records=[]
    source=api.read(d['case']['source'])['result']['checkpoint']
    for factor in d['moving']['factors']:
        p=w.OUT/f'rigid_{factor}.json';rec=api.read(p);r=rec['result'];spec=rec['spec']
        binding=api.digest([d['binding'],factor,True,False])
        cp=w.model.checkpoint(spec,binding,source,True)
        api.require(api.digest(cp)==rec['input_checkpoint_sha256'],'initial checkpoint')
        api.require(r['checkpoint']['contract']==w.engine.prior.contracts.expected_contract(spec,w.model.binding_for(binding,True)),'model checkpoint contract')
        api.require(r['checkpoint']['state_sha256']==api.digest(r['checkpoint']['state']),'final state integrity')
        clock=w.prior.audit.clock_chain(cp['state']['t'],rec['rows'],r['time_s'])
        health=w.engine.prior.reference.independent_health(r,spec)
        api.require(clock['passed'] and health['passed'] and not r.get('stage119_repair_calls'),'independent clock and health')
        api.require(len(rec['rows'])==r['steps']-cp['state']['steps'],'accepted step accounting')
        completed=r['status']=='present_at_horizon' and r['time_s']==spec['horizon_s']
        items.append({'factor':factor,'completed':completed,'status':r['status'],'accepted_steps':len(rec['rows']),
                      'new_rejections':r['rejected']-cp['state']['rejected'],'independent_health_passed':health['passed'],'clock_passed':clock['passed'],
                      'time_s':r['time_s'],'completed_window_s':r['time_s']-source['state']['t'],'remaining_window_s':spec['horizon_s']-r['time_s'],
                      'runtime_s':r['runtime_seconds'],'record_sha256':api.sha(p)})
        records.append(rec)
    api.require([r['completed'] for r in items]==[True,True,False],'completion pattern')
    api.require(items[-1]['status']=='incomplete_budget','incomplete reason')
    result={'stage':'Stage151','moving_refinement_qualified':False,'canonical_mechanics_passed':True,
            'interface_failure_preserved_and_repaired':True,'finest_case_numerically_healthy_but_incomplete':True,
            'levels':items,'completed_pair_difference':w.compare(records[0]['result'],records[1]['result'],records[1]['spec']),
            'quasistatic_vs_completed_half_step_rigid':w.compare(baseline['result'],records[1]['result'],records[1]['spec']),
            'baseline_runtime_s':baseline['result']['runtime_seconds'],'baseline_accepted_steps':len(baseline['rows']),
            'exact_restart_test_completed':False,'production_promotion':False,
            'next_actions':['Prospectively authorize a small segmented completion budget for the saved finest checkpoint; retain the original failed bounded attempt.',
                            'Do not repeat the completed coarse/medium trajectories. Apply the unchanged three-level accuracy limits after reaching the same clock.',
                            'Check exact restart with a different split point, then assess longer contact-onset/release windows before changing the production model.'],
            'claim':d['scope'],'design_sha256':api.sha(w.DESIGN),'audit_source_sha256':api.sha(__file__),
            'artifact_hashes':{str(p):api.sha(p) for folder in [w.OUT,wrapper.FAILURE.parent] for p in folder.iterdir() if p.is_file()}}
    OUT.mkdir(parents=True,exist_ok=False);api.write(OUT/'results.json',result,raw=True)
    api.write(OUT/'completion.json',{'audit_completed':True,'moving_refinement_qualified':False,'results_sha256':api.sha(OUT/'results.json')})
    print('AUDIT_COMPLETE; MOVING_REFINEMENT_NOT_QUALIFIED',items,flush=True)


if __name__=='__main__':main()
