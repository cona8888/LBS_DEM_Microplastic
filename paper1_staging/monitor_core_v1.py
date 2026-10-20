"""Compact read-only live/retired identity and sealed production monitor."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_core_v2 as shared
s=shared.s


def monitor(root):
    root=Path(root).resolve();plan_path=s.ROOT/'paper1_designs'/root.name/'design_01.json'
    p=s.read(plan_path);s.api.verify_mapping(p['source_files']);s.api.verify_mapping(p['physical_inputs'])
    identities=[]
    for path in (root/'controller_01/launch.json',root/'controller_01/worker_launch.json'):
        launch=s.read(path);identities.append(dict(path=str(path),pid=launch['pid'],inspection=s.identity(launch)))
    docs=shared.documents.build(s.q.job.codec,s.api)
    admitted=steps=0;stop=0.;last=None;pending=[]
    for folder in sorted((root/'records').glob('production_*')):
        gate=folder/'guard_completion/results.json'
        if not gate.with_name('completion.json').exists():
            pending.append(folder.name);continue
        row=s.fields.sealed(gate);s.api.verify_mapping(row['artifacts']);assert row['passed']
        receipt=docs.read(folder/'results.json');s.api.verify_mapping(receipt['artifacts'])
        assert receipt['passed'] and receipt['summary']['passed']
        assert s.read(folder/'completion.json')['results_sha256']==s.sha(folder/'results.json')
        assert row['full_checkpoint_sha256']==receipt['output_checkpoint_sha256']
        assert receipt['summary']['start_s']==stop
        steps+=row['saved_steps'];admitted+=1;stop=receipt['summary']['stop_s'];last=row['full_checkpoint_sha256']
    assert len(pending)<=1,'At most one unverified record'
    physical=s.read(s.ROOT/'paper1_designs'/root.name/'physical_cases_01.json')
    horizon=physical['cases'][0]['spec']['horizon_s']
    final=None
    if (root/'final_disposition_01/completion.json').exists():
        final=s.fields.sealed(root/'final_disposition_01/results.json')
        assert final['accepted_physical_steps']==steps and final['full_checkpoint_sha256']==last
    return dict(root=str(root),identities=identities,admitted_production_records=admitted,
        accepted_physical_steps=steps,time_s=stop,horizon_s=horizon,observation_fraction=stop/horizon,
        pending_records=pending,last_full_checkpoint_sha256=last,final=final,
        numerical_cutoff=p['simulation_cutoff_utc'],absolute_end=p['end_utc'])


if __name__=='__main__':
    import json
    print(json.dumps(monitor(sys.argv[1] if len(sys.argv)>1 else shared.OUT),sort_keys=True))
