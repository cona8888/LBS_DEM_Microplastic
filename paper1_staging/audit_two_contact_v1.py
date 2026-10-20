"""Post-exit authentication; recomputes residuals without native solver calls."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
import runpy
import sys
import numpy as np

p=SimpleNamespace(**runpy.run_path(str(Path(__file__).with_name('diagnose_two_contact_v1.py')),
                                 run_name='paper1_onset_retirement'))
s=p.s


def audit(observed_exit, root_session):
    assert observed_exit==0
    d=s.read(p.DESIGN);assert datetime.now(timezone.utc)<datetime.fromisoformat(d['end_utc'])
    ready=s.fields.sealed(p.DESIGNS/'readiness_01/results.json')
    human=s.fields.sealed(p.DESIGNS/'human_approval_01/results.json')
    assert ready['passed'] and human['passed'] and human['two_contact_probes_authorized']
    assert ready['proposal_sha256']==human['proposal_sha256']==d['proposal_sha256']==s.sha(p.PROPOSAL)
    assert d['human_approval_sha256']==s.sha(p.DESIGNS/'human_approval_01/results.json')
    final=s.fields.sealed(p.BASE/'final_01/results.json')
    assert final['passed'] and final['attempted_contact_calls']==final['completed_contact_calls']==8
    assert final['unknown_or_unqualified_contact_calls']==final['new_transport_steps']==final['new_saved_steps']==0
    for key in ('artifacts','source_files','inputs'):s.api.verify_mapping(final[key])
    controller=s.read(p.BASE/'controller_launch.json');assert s.identity(controller)['retired']
    identities=[dict(path=str(p.BASE/'controller_launch.json'),identity=controller,retired=True)]
    reports=[]
    for fixture in d['fixtures']:
        data=s.read(fixture['path']);assert s.sha(fixture['path'])==fixture['sha256']
        values=data['inner_arguments'];args=[np.asarray(v,float) for v in values[:4]]+values[4:]
        expected=data['expected_first_inner'];assert p.old.core.digest_args(args)==expected['input_sha256']
        answers={};physics={};costs={}
        for mode in ('primary','fallback'):
            folder=p.BASE/f"call_{fixture['fixture_id']:02d}_{mode}"
            launch=s.read(folder/'launch.json');assert s.identity(launch)['retired']
            exit=s.read(folder/'exit.json');assert exit['returncode']==0;s.api.verify_mapping(exit['logs'])
            record=s.fields.sealed(folder/'results.json');started=s.read(folder/'started.json')
            assert started['contact_calls_attempted']==1 and started['new_transport_steps']==0
            assert record['passed'] and record['input_sha256']==expected['input_sha256']
            proof=p.old.core.physical_output(args,record['answer'])
            assert proof['passed'] and s.api.digest(proof)==s.api.digest(record['independent_physics'])
            if mode=='primary':
                assert np.asarray(record['answer'][0],float).tobytes()==np.asarray(expected['map_output'],float).tobytes()
            assert p.old.core.digest_args(args)==expected['input_sha256']
            identities.append(dict(path=str(folder/'launch.json'),identity=launch,retired=True))
            answers[mode]=np.asarray(record['answer'][0],float);physics[mode]=proof;costs[mode]=record['force_call_seconds']
        difference=float(np.linalg.norm(answers['primary']-answers['fallback'])/data['speed_m_s'])
        assert difference==final['reports'][fixture['fixture_id']]['difference_over_U']
        reports.append(dict(fixture_id=fixture['fixture_id'],difference_over_U=difference,
            primary_archive_bits=True,independently_recomputed_physics=physics,scoped_call_seconds=costs))
    s.seal(p.BASE/'retirement_01',dict(passed=True,observed_root_exit=observed_exit,root_exec_session_id=root_session,
        all_exact_identities_retired=True,identities=identities,new_transport_steps=0,new_saved_steps=0,
        completed_route_invocations=8,unknown_or_unqualified_route_invocations=0,
        prior_nonadvancing_reservations_preserved=11,total_nonadvancing_reservations=19,
        native_solvers_called_by_this_audit=0,original_physics_recomputed_for_all_eight=True,reports=reports,
        representative_speedup_inferred=False,full_path_admission=False,production_installation=False,
        source_files={str(Path(__file__).resolve()):s.sha(Path(__file__)),**d['source_files']},
        inputs={str(p.DESIGN):s.sha(p.DESIGN),str(p.BASE/'final_01/results.json'):s.sha(p.BASE/'final_01/results.json')},
        artifacts=final['artifacts'],utc=s.utc()))
    print('TWO_CONTACT_RETIRED',s.sha(p.BASE/'retirement_01/results.json'),reports,flush=True)


if __name__=='__main__':audit(int(sys.argv[1]),int(sys.argv[2]))
