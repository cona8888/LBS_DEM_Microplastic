"""Zero-step actual prepare hook and independent provenance negative controls."""
from pathlib import Path
import copy,os,sys,traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
import normal_gap_scope_v1 as candidate
import audit_normal_gap_v1 as auditor
job,api=candidate.job,candidate.api
WORK=ROOT/'stage213_designs/normal_gap_trajectory_20261001/zero_step_contract_01.json'
OUT=ROOT/'stage213_evaluations/normal_gap_trajectory_20261001/scope_qualification_01'

def run():
    w=api.read(WORK);api.verify_mapping(w['sources']);api.verify_mapping(w['inputs']);job.verify(api.read(job.DESIGN))
    api.require(w['maximum_new_trajectory_steps']==0 and not w['production_authorized'],'zero-step authority')
    api.require(not candidate.proof.source.frozen.active_owned(False),'exclusive scoped check')
    proof=candidate.proof.api.read(candidate.proof.OUT/'results.json');api.require(proof['zero_step_qualification_closed'],'closed held qualification')
    d=api.read(job.DESIGN);spec=next(c['spec'] for c in d['cases'] if c['id']=='s2_i124_sphere_f0p0625')
    geo=spec['field_metadata']['geometry'];data=np.load(geo['path'],allow_pickle=False)
    geometry=candidate.model.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],spec['field_metadata']['cell_length_m'])
    state=api.read(job.RUN/'s2_i124_sphere_f0p0625/result.json')['final_result']['checkpoint']['state']
    x,p=np.asarray(state['x']),np.asarray(state['p']);a,b,_=spec['config']['prolate_semiaxes_m']
    original=candidate.backend._prepare_geometry;raw=geometry.contacts(x,p,a,b,1e-5*b)
    expected=api.read(candidate.proof.source.OUT/'failed_systems.json')['failed_inner_systems'][0]['system']
    api.require(candidate.plain_contacts(raw)==api.read(candidate.proof.source.OUT/'failed_systems.json')['failed_outer_trials'][0]['outer_inputs'][6],'exact captured raw membership')
    J,g,frames=original(raw,a);api.require(np.array_equal(J,expected['jacobian']) and np.array_equal(g,expected['gaps_m']),'native captured J/g')
    inputs={str(p):api.sha(p) for p in (Path(__file__),WORK,candidate.proof.OUT/'results.json',job.DESIGN)}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),new_trajectory_steps=0,inputs=inputs))
    try:
        with candidate.scope(2) as log:
            actual=geometry.contacts(x,p,a,b,1e-5*b)
            api.require(candidate.plain_contacts(actual)==candidate.plain_contacts(raw),'raw membership/geometry unchanged')
            newJ,newg,newframes=candidate.backend._prepare_geometry(actual,a)
            api.require(np.array_equal(newJ,J) and np.array_equal(newg,np.zeros(3))
                and all(np.array_equal(x,y) for x,y in zip(frames,newframes)),'only solver gaps revised')
        api.require(candidate.backend._prepare_geometry is original,'prepare binding restored')
        record=dict(spec=spec,normal_gap_operand_policy=log,numerical_policy_contract_sha256=api.sha(WORK),
                    rows=[dict(active_contact_ids=[int(c[0]) for c in raw])],
                    contact_trial_trace=dict(trial_inner_counts=[1],detailed_trials=[dict(trial_index=0,outer_inputs=[None]*6+[candidate.plain_contacts(raw)])]))
        prepared=auditor.provenance(record,geometry,dict(state=state));api.require(len(prepared)==1,'independent hook provenance')
        rejected=[]
        for label in ('raw_gap','effective_gap','jacobian','classification_band','pose','contact_id'):
            bad=copy.deepcopy(record);c=bad['normal_gap_operand_policy']['prepare_calls'][0]
            if label=='raw_gap':c['contacts'][0][1]+=1e-12
            elif label=='effective_gap':c['effective_gaps_m'][0]=1e-12
            elif label=='jacobian':c['jacobian_sha256']='0'*64
            elif label=='classification_band':c['metadata'][0]['classification']['uncertainty_m']*=2
            elif label=='pose':c['metadata'][0]['context']['x'][0]+=1e-12
            else:c['contacts'][0][0]=0
            try:auditor.provenance(bad,geometry,dict(state=state))
            except (AssertionError,RuntimeError):rejected.append(label)
            else:raise RuntimeError('corrupt scoped provenance accepted '+label)
        # Fibre is an exact identity path and does not change native membership.
        fraw=geometry.contacts(x,p,a,a/4,.001);fJ,fg,ff=original(fraw,a)
        with candidate.scope(1) as flog:
            fcontacts=geometry.contacts(x,p,a,a/4,.001);jj,gg,fr=candidate.backend._prepare_geometry(fcontacts,a)
            api.require(candidate.plain_contacts(fcontacts)==candidate.plain_contacts(fraw)
                and np.array_equal(jj,fJ) and np.array_equal(gg,fg)
                and all(np.array_equal(l,r) for l,r in zip(fr,ff)),'fibre exact raw prepare identity')
            api.require(all(not m['classification']['changed'] for m in flog['prepare_calls'][0]['metadata']),'fibre policy identity')
        api.verify_mapping(w['sources']);api.verify_mapping(w['inputs']);api.verify_mapping(inputs);job.verify(d)
        r=dict(passed=True,new_trajectory_steps=0,raw_geometry_membership_lubrication_sweep_dwell_unchanged=True,
               original_normal_lever_jacobian_frames_preserved=True,solver_normal_gap_policy_explicit=True,
               controls_rejected=rejected,scope_witness=record,fibre_prepare_contacts=len(fraw),production_authorized=False,
               inputs=inputs,claim='Zero-step scope/provenance check only. No trajectory or full-path campaign acceptance.')
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
        print('NORMAL_GAP_SCOPE_PASS',len(rejected),len(fraw),api.sha(OUT/'results.json'),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise

if __name__=='__main__':run()
