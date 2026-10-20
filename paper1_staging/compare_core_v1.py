"""New evidence assembler; original full-path metric/observation/gate code reused."""
from pathlib import Path
import argparse,copy,json,sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_core_v2 as shared
s=shared.s;api=s.api
SOURCE_FILES={str(path):s.sha(path) for path in (
    Path(__file__).resolve(),
    Path(s.q.job.path_metrics.metrics.__code__.co_filename).resolve(),
    Path(s.q.job.policy.pair_gates.__code__.co_filename).resolve())}


def physical_signature(spec):
    result=copy.deepcopy(spec)
    result.pop('case_id');result.pop('refinement')
    for key in s.factory.SCALED_CONTROLS:result['config']['numerics'].pop(key)
    return result


def authenticate(root,plan_path,physical_path):
    root=Path(root);plan=s.read(plan_path);d=s.read(physical_path);case=d['cases'][0]
    api.verify_mapping(SOURCE_FILES)
    api.require(len(d['cases'])==1 and plan['case_id']==case['id'], 'Exact single planned case')
    final=s.fields.sealed(root/'final_disposition_01/results.json')
    retirement=s.fields.sealed(root/'retirement_01/results.json')
    api.require(final['passed'] and retirement['passed'] and retirement['all_exact_owned_identities_retired'],
                'Retired complete evidence required before comparison')
    api.require(final['native_complete'] and final['known_unaccepted_saved_steps']==final['unknown_reserved_steps_upper_bound']==0,
                'Native complete, no censored/unknown work')
    api.require(plan['physical_design_sha256']==s.sha(physical_path) and final['design_sha256']==s.sha(plan_path),
                'Immutable physical/numerical designs')
    api.require(retirement['design_sha256']==s.sha(plan_path)
        and retirement['final_disposition_sha256']==s.sha(root/'final_disposition_01/results.json'),
        'Independent retirement binds this exact final disposition')
    api.verify_mapping(retirement['artifacts']);api.verify_mapping(retirement['closed_logs'])
    for identity in retirement['identities']:
        api.require(s.sha(identity['path'])==identity['sha256']
            and s.identity(s.read(identity['path']))['retired'],'Fresh exact retired launch identities')
    labels=final['production_labels']
    api.require(labels==[f'production_{i:05d}' for i in range(1,len(labels)+1)]
        and sorted(p.name for p in (root/'records').glob('production_*'))==labels,
        'All production records, including no omitted failed reservation')
    api.verify_mapping(plan['source_files']);api.verify_mapping(plan['physical_inputs'])
    codec=shared.archives.build(s.q.job.codec,preset=9)
    doc=shared.documents.build(s.q.job.codec,api)
    prefix=before=None;paths=[];receipts={};steps=0
    for label in labels:
        folder=root/'records'/label
        gate=s.fields.sealed(folder/'guard_completion/results.json');api.verify_mapping(gate['artifacts'])
        manifest=s.read(folder/'results.json');complete=s.read(folder/'completion.json')
        api.require(complete['results_sha256']==s.sha(folder/'results.json'),'Complete audit document reference seal')
        receipt=doc.read(folder/'results.json')
        api.require(gate['passed'] and receipt['passed'] and receipt['summary']['passed'],'Original independent physics/guard gates')
        api.verify_mapping(receipt['artifacts'])
        rec,prefix=codec.read_record(folder/'call.json.xz',s.sha(physical_path),prefix)
        api.require(rec['spec']==case['spec'] and rec['input_checkpoint_sha256']==api.digest(before),
                    'Exact contiguous physical raw ancestry')
        api.require(receipt['input_checkpoint_sha256']==api.digest(before)
            and receipt['output_checkpoint_sha256']==api.digest(rec['result']['checkpoint'])
            and gate['full_checkpoint_sha256']==receipt['output_checkpoint_sha256'],'Full checkpoint/raw/audit identities')
        initial_steps=0 if before is None else before['state']['steps']
        initial_time=0. if before is None else before['state']['t']
        n=len(rec['rows']);terminal=rec['result'];before=terminal['checkpoint']
        api.require(before['state']['steps']==initial_steps+n and receipt['summary']['start_s']==initial_time
                    and receipt['summary']['stop_s']==before['state']['t'],'Whole step/clock coverage')
        expected=np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],dtype=np.float64)
        path=folder/'trace.npy';actual=np.load(path,mmap_mode='r',allow_pickle=False)
        api.require(np.array_equal(expected,actual),'Every trace row reconstructs from original raw')
        paths.append(path);steps+=n;receipts[str(folder/'results.json')]=s.sha(folder/'results.json')
    api.require(steps==final['accepted_physical_steps']==before['state']['steps'] and api.digest(before)==final['full_checkpoint_sha256'],
                'Entire start-to-terminal path, not a prefix')
    recovered=doc.read(root/'recoverable/checkpoint.json')
    api.require(api.digest(recovered)==api.digest(before),'Standalone FULL checkpoint preserved')
    evidence=dict(status=terminal['status'],steps=steps,start_s=0.,stop_s=before['state']['t'],rejected=terminal['rejected'],
        failure_markers=[],pending_trial=before['state']['pending_trial'],first_dwell_s=terminal['first_contact_dwell_time_s'],
        export_verified=terminal['status']=='full_window_exit',raw_hashes_verified=True,clock_steps_verified=True,
        physics_verified=True,fresh_start=True)
    observation=s.q.job.policy.observation(evidence,case['spec']['horizon_s'])
    api.require(observation['complete_observation'],'Original full observation gate')
    evidence_paths=[Path(plan_path),Path(physical_path),
        root/'final_disposition_01/results.json',root/'final_disposition_01/completion.json',
        root/'retirement_01/results.json',root/'retirement_01/completion.json']
    return dict(case=case,logical_core_id=plan['logical_core_id'],observation=observation,paths=paths,receipts=receipts,
                evidence_files={str(path.resolve()):s.sha(path) for path in evidence_paths},
                final_sha256=s.sha(root/'final_disposition_01/results.json'),retirement_sha256=s.sha(root/'retirement_01/results.json'))


def compare(first,second,destination):
    api.verify_mapping(SOURCE_FILES)
    a,b=first['case'],second['case']
    api.require(first['logical_core_id']==second['logical_core_id'],'Same labelled logical case')
    api.require(physical_signature(a['spec'])==physical_signature(b['spec']),'Same physical inputs/exposure/placement/shape')
    api.require(a['factor']==.125 and b['factor']==.0625,'Prospective original-control finer reference')
    for key in s.factory.SCALED_CONTROLS:
        api.require(b['spec']['config']['numerics'][key]==a['spec']['config']['numerics'][key]*.5,'Exact original numerical refinement')
    initial=a['spec']['initial_state'];row0=[0.,*initial['position_m'],*initial['orientation'],*initial['velocity_generalized']]
    def blocks(paths):
        for path in paths:yield np.load(path,mmap_mode='r',allow_pickle=False)
    cfg=a['spec']['config'];gates=s.read(s.factory.contract()['physical_design_file'])['numerical_gates']
    metrics=s.q.job.path_metrics.metrics(blocks(first['paths']),blocks(second['paths']),row0,row0,
        first['observation']['stop_s'],second['observation']['stop_s'],cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
    result=s.q.job.policy.pair_gates(first['observation'],second['observation'],metrics,gates)
    evidence_files={**first['evidence_files'],**second['evidence_files']}
    api.verify_mapping(evidence_files);api.verify_mapping(SOURCE_FILES)
    body=dict(passed=result['passed'],core_case=a['id'],reference_case=b['id'],full_path_gates=result,
        logical_core_id=first['logical_core_id'],admission_level='Per-case original temporal pair gates only',paper1_dataset_complete=False,
        observations=[first['observation'],second['observation']],original_gate_values=gates,
        whole_start_to_terminal_paths=True,new_transport_steps=0,
        source_files=SOURCE_FILES,evidence_files=evidence_files,
        path_artifacts={str(p):s.sha(p) for p in first['paths']+second['paths']},
        prerequisite_final_and_retirement_sha256=[first['final_sha256'],first['retirement_sha256'],second['final_sha256'],second['retirement_sha256']],utc=s.utc())
    s.seal(Path(destination),body)
    return body


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('coarse_root',type=Path)
    parser.add_argument('fine_root',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    def accepted(root):
        design=s.ROOT/'paper1_designs'/root.name
        return authenticate(root,design/'design_01.json',design/'physical_cases_01.json')
    result=compare(accepted(args.coarse_root.resolve()),accepted(args.fine_root.resolve()),args.destination.resolve())
    print(json.dumps({'passed':result['passed'],'logical_core_id':result['logical_core_id'],
        'full_path_gates':result['full_path_gates'],'new_transport_steps':0}),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
