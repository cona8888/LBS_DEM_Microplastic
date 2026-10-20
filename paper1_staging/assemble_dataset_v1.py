"""Read-only intermediate assembly of the frozen twelve labelled Paper1 cases.

Consumes authenticated measurements and negative full-path comparisons; never
advances transport or admits a numerical case. Missing outcomes stay unknown.
Dataset completion still requires independent robustness and figure closure.
"""
from pathlib import Path
import argparse,csv,json,math,numbers,sys
import shutil
sys.path.insert(0,str(Path(__file__).resolve().parent))
import derive_observables_v2 as measurements
s=measurements.s;api=s.api;SELF=Path(__file__).resolve()
CONTRACT=s.factory.CONTRACT;PROTOCOL=measurements.PROTOCOL
CONTRACT_SHA='e04f863f6297581efe42606e1c3125b4105a17b2af081a685173dc9f1d4f7166'
PROTOCOL_SHA='0dedae903d44689ad6a2066085b600d357a49202975faa3c94bfed8c2b0ebc69'
SOURCE_FILES={str(SELF):s.sha(SELF),str(Path(measurements.__file__).resolve()):s.sha(measurements.__file__),
              **measurements.comparison.SOURCE_FILES,
              **{str(Path(m.__file__).resolve()):s.sha(m.__file__) for m in (s,s.factory,s.fields)}}


def scalar(value):
    if isinstance(value,bool) or not isinstance(value,numbers.Real) or not math.isfinite(value):
        raise ValueError('Finite real feature required; booleans and missing values are not measurements')
    return float(value)


def finite_contrast(ac,af,bc,bf):
    ac,af,bc,bf=map(scalar,(ac,af,bc,bf));dc=bc-ac;df=bf-af
    threshold=2*(abs(ac-af)+abs(bc-bf))
    if not all(math.isfinite(v) for v in (dc,df,threshold)):raise ValueError('Finite differences and threshold required')
    signs=(dc>0 and df>0) or (dc<0 and df<0)
    passed=signs and abs(df)>threshold
    reason=('resolved_finite_level_screen' if passed else 'zero_contrast' if dc==0 or df==0
            else 'sign_reversal' if not signs else 'not_above_twice_feature_change')
    return dict(available=True,coarse_difference=dc,fine_difference=df,
                twice_sum_feature_changes=threshold,resolved=bool(passed),reason=reason,
                direction='second_minus_first',rigorous_error_bound=False,statistical_interval=False)


def export_bounds(values):
    values=list(values)
    if any(type(v) is not bool and v is not None for v in values):raise ValueError('Exact binary outcome or unknown required')
    known=sum(v is not None for v in values);exported=sum(v is True for v in values)
    return dict(minimum_exports=exported,maximum_exports=exported+len(values)-known,
                known_labels=known,unresolved_labels=len(values)-known,total_labels=len(values),
                interpretation='Deterministic counts among these designed labels; no population inference')


def query_key(query):
    kind=query['kind']
    if kind=='common_pv':return kind,scalar(query['target_pv'])
    if kind=='common_physical_time':return kind,scalar(query['time_s'])
    raise ValueError('Only the two frozen exposure clocks are admitted')


def feature_contrasts(rows,features):
    result={}
    for feature in features:
        values=[row.get(feature) for row in rows]
        result[feature]=(dict(available=False,resolved=False,reason='inapplicable_or_missing_feature')
                         if any(v is None for v in values) else finite_contrast(*values))
    return result


def pair_contrasts(a,b,features):
    """B-A on shared clocks only; own-stop export summaries are descriptive."""
    if a is None or b is None:return dict(available=False,reason='awaiting_qualified_pair',summary=None,queries=[])
    ac,af=a['variants'];bc,bf=b['variants'];variants=(ac,af,bc,bf)
    full=all(v['summary']['observed_stop_s']==v['summary']['horizon_s'] for v in variants)
    summary=(dict(available=True,clock='common_full_pore_volume',features=feature_contrasts(
        [v['summary'] for v in variants],features)) if full else
        dict(available=False,reason='own_stop_summary_after_early_export_is_not_shared_exposure'))
    maps=[]
    for v in variants:
        mapping={query_key(q):q for q in v['queries']}
        if len(mapping)!=len(v['queries']):raise ValueError('Duplicate query target')
        maps.append(mapping)
    targets=set().union(*(set(m) for m in maps));queries=[]
    for key in sorted(targets):
        rows=[m.get(key) for m in maps]
        common=dict(kind=key[0],target=key[1])
        if any(row is None or row.get('available') is not True for row in rows):
            queries.append(dict(**common,available=False,reason='query_unavailable_no_extrapolation'));continue
        queries.append(dict(**common,available=True,features=feature_contrasts(rows,features)))
    return dict(available=True,reason='authenticated_temporal_pair_measurements',summary=summary,queries=queries,
                endpoint_primary_export_difference=int(bf['summary']['whole_body_control_volume_export'])-
                int(af['summary']['whole_body_control_volume_export']),
                physical_clock_interpretation='Equal PV changes duration across flows; equal time changes water dose')


def authenticate(path,contract,decision,artifacts):
    path=Path(path).resolve();value=s.fields.sealed(path)
    api.require(value['passed'] and value['new_transport_steps']==0,'Complete derived measurement receipt')
    for key in ('source_files','inputs','artifacts'):api.verify_mapping(value[key]);artifacts.update(value[key])
    api.require(value['inputs'].get(str(PROTOCOL))==PROTOCOL_SHA
        and value['inputs'].get(str(s.factory.EXPOSURE))==s.sha(s.factory.EXPOSURE),'Exact frozen analysis/exposure lineage')
    candidates=[Path(p) for p in value['inputs'] if p not in (str(PROTOCOL),str(s.factory.EXPOSURE))]
    qualified=[]
    for p in candidates:
        v=s.read(p)
        if isinstance(v,dict) and v.get('whole_start_to_terminal_paths'):
            v=s.fields.sealed(p)
            api.require(v['passed'] and v['full_path_gates']['passed'] and v['original_gate_values']==s.q.job.policy.GATES,
                        'Unchanged original complete-path accuracy/event gates')
            for key in ('source_files','evidence_files','path_artifacts'):api.verify_mapping(v[key]);artifacts.update(v[key])
            qualified.append(v)
    api.require(len(qualified)==1,'Exactly one declared accepted pair, never outcome-based pair selection')
    pair=qualified[0];logical=value['logical_core_id'];api.require(logical==pair['logical_core_id'],'Exact logical identity')
    expected=next((c for c in contract['cases'] if c['id']==logical),None)
    api.require(expected is not None,'One of the twelve original case identities')
    variants=value['variants'];api.require(len(variants)==2 and tuple(v['factor'] for v in variants)==(.125,.0625),
        'Prospective primary coarse/fine pair; no post-outcome reference-pair selection')
    resolved=[]
    for variant in variants:
        api.require(variant['logical_core_id']==logical and all(variant[k]==expected[k]
            for k in ('shape','placement_id','nominal_flow_level')),'Original shape, placement and flow')
        api.verify_mapping(variant['evidence_files']);artifacts.update(variant['evidence_files'])
        physical=[Path(p) for p in variant['evidence_files'] if Path(p).name=='physical_cases_01.json']
        api.require(len(physical)==1,'One exact physical design per variant')
        cases=[c for c in s.read(physical[0])['cases'] if c['id']==variant['case_id']]
        api.require(len(cases)==1,'Exact compared physical variant')
        case=cases[0];spec=case['spec'];resolved.append(spec)
        original=s.factory.case_for(logical,spec['field_metadata'],decision['selected_pv'],variant['factor'],'core')
        api.require(measurements.comparison.physical_signature(original['spec'])==measurements.comparison.physical_signature(spec)
            and original['spec']['config']['numerics']==spec['config']['numerics']
            and original['spec']['refinement']==spec['refinement'],
            'Original factory physics, refinement and numerical controls; only case ID aliases may differ')
        api.require(spec['seed']==2 and spec['cpd']==6 and spec['sample_id']==expected['placement_id']
            and spec['flow_factor']==expected['nominal_flow_level'] and case['factor']==variant['factor']
            and case['shape']==expected['shape'],'Frozen specimen and resolved variant settings')
        obs=measurements.compared_observation(case,pair);summary=variant['summary']
        api.require(summary['observed_stop_s']==obs['stop_s'] and summary['horizon_s']==spec['horizon_s']
            and summary['whole_body_control_volume_export']==(obs['status']=='full_window_exit')
            and summary['export_time_s']==(obs['stop_s'] if obs['status']=='full_window_exit' else None)
            and summary['original_dwell_threshold_s']==.5
            and summary['observed_duration_can_span_dwell_threshold']==(obs['stop_s']>=.5),
            'Original export clock and dwell eligibility, never permanent retention')
        for feature in s.read(PROTOCOL)['features']:
            v=summary[feature]
            if feature=='fibre_director_angle_to_flow_rad' and expected['shape']=='equal_volume_sphere':
                api.require(v is None,'Sphere orientation is inapplicable')
            elif v is not None:scalar(v)
            else:raise ValueError('Missing applicable summary feature')
        dependencies={v['path']:v['sha256'] for v in spec['field_metadata'].values()
                      if isinstance(v,dict) and {'path','sha256'}<=v.keys()}
        api.verify_mapping(dependencies);artifacts.update(dependencies)
        wanted=measurements.queries_for(spec,decision);queries=variant['queries']
        api.require(len(queries)==len(wanted)==8 and {query_key(q) for q in queries}=={query_key(q) for q in wanted},
                    'All four targets in each frozen query family')
        lookup={query_key(q):q for q in wanted}
        for q in queries:
            api.require(q['time_s']==lookup[query_key(q)]['time_s'] and type(q['available']) is bool,'Exact query clock and availability')
            if q['available']:
                api.require(q['time_s']<=obs['stop_s'],'No post-export extrapolation')
                for feature in s.read(PROTOCOL)['features']:
                    if q.get(feature) is not None:scalar(q[feature])
                if expected['shape']=='equal_volume_sphere':api.require(q['fibre_director_angle_to_flow_rad'] is None,'No sphere director effect')
            else:api.require(q['time_s']>obs['stop_s'] and obs['status']=='full_window_exit'
                and q['reason']=='export_before_query','Unavailable query is explicit export censoring, never zero')
    api.require(measurements.comparison.physical_signature(resolved[0])==measurements.comparison.physical_signature(resolved[1]),
                'Matched physical settings and exposure within the accepted pair')
    artifacts[str(path)]=s.sha(path);artifacts[str(path.with_name('completion.json'))]=s.sha(path.with_name('completion.json'))
    return value,resolved[0]


def write_csv(path,rows,fields):
    with path.open('x',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def assemble(paths,failures,destination):
    s.environment();destination=Path(destination).resolve();api.require(s.ROOT/'paper1_evaluations' in destination.parents
        and not destination.exists(),'Create-only intermediate dataset destination')
    api.require(s.sha(CONTRACT)==CONTRACT_SHA and s.sha(PROTOCOL)==PROTOCOL_SHA,'Frozen twelve-case contract and analysis')
    contract=s.read(CONTRACT);decision=s.fields.sealed(s.factory.EXPOSURE);protocol=s.read(PROTOCOL)
    api.verify_mapping(SOURCE_FILES)
    api.require(decision['contract_sha256']==CONTRACT_SHA and decision['frozen_before_core_comparisons']
        and decision['core_comparisons_completed']==0 and decision['outcomes_used_for_selection'] is False,
        'Prospective exposure was frozen before shape/flow contrasts')
    for key in ('source_files','inputs'):api.verify_mapping(decision[key])
    retained=sum(p.stat().st_size for name in ('paper1_runs','paper1_designs','paper1_evaluations')
                 for p in (s.ROOT/name).rglob('*') if p.is_file())
    api.require(retained+2*1024**2<20*1024**3 and shutil.disk_usage(s.ROOT).free>20*1024**3+2*1024**2,
                'Intermediate analysis stays inside existing retention/free-disk limits')
    api.require(len(contract['cases'])==12 and len({c['id'] for c in contract['cases']})==12
        and decision['passed'] and decision['selected_pv']==.01,'Original twelve labels and prospective common exposure')
    artifacts={str(CONTRACT):s.sha(CONTRACT),str(PROTOCOL):s.sha(PROTOCOL),str(s.factory.EXPOSURE):s.sha(s.factory.EXPOSURE),
               str(s.factory.EXPOSURE.with_name('completion.json')):s.sha(s.factory.EXPOSURE.with_name('completion.json')),
               **decision['source_files'],**decision['inputs']}
    api.require(s.sha(contract['physical_design_file'])==contract['physical_design_sha256'],'Original physical template seal')
    artifacts[contract['physical_design_file']]=contract['physical_design_sha256']
    measured={};specs={};negative={c['id']:[] for c in contract['cases']}
    for path in paths:
        value,spec=authenticate(path,contract,decision,artifacts);key=value['logical_core_id']
        api.require(key not in measured,'No duplicated case denominator or convenient pair selection')
        measured[key]=value;specs[key]=spec
    seen_failures=set()
    for path in failures:
        path=Path(path).resolve();v=s.fields.sealed(path)
        api.require(path not in seen_failures,'Distinct failure evidence, never duplicate attempts');seen_failures.add(path)
        api.require(v['passed'] is False and v['whole_start_to_terminal_paths'] and v['full_path_gates']['passed'] is False
            and v['original_gate_values']==s.q.job.policy.GATES and v['logical_core_id'] in negative,'Authentic original full-path scientific rejection')
        for key in ('source_files','evidence_files','path_artifacts'):api.verify_mapping(v[key]);artifacts.update(v[key])
        artifacts[str(path)]=s.sha(path);artifacts[str(path.with_name('completion.json'))]=s.sha(path.with_name('completion.json'))
        negative[v['logical_core_id']].append(dict(path=str(path),sha256=s.sha(path),gate_result=v['full_path_gates']))
    # Fair same-label shape comparisons remain conditional on actual settings.
    for a in contract['cases']:
        for b in contract['cases']:
            if a['id'] not in specs or b['id'] not in specs:continue
            if a['placement_id']==b['placement_id']:
                api.require(specs[a['id']]['initial_state']==specs[b['id']]['initial_state'],'Identical paired initial state across shapes/flows')
            if a['placement_id']==b['placement_id'] and a['nominal_flow_level']==b['nominal_flow_level']:
                ca,cb=(specs[c['id']]['config'] for c in (a,b));va=math.prod(ca['prolate_semiaxes_m']);vb=math.prod(cb['prolate_semiaxes_m'])
                api.require(math.isclose(va,vb,rel_tol=1e-12) and ca['particle_density_kg_m3']==cb['particle_density_kg_m3'],
                            'Equal-volume/density paired shapes')
    index=[];binary=[]
    for c in contract['cases']:
        key=c['id'];value=measured.get(key);known=None if value is None else value['variants'][1]['summary']['whole_body_control_volume_export']
        binary.append(known);index.append(dict(logical_core_id=key,shape=c['shape'],placement_id=c['placement_id'],
            nominal_flow_level=c['nominal_flow_level'],status='temporally_measured' if value else 'accuracy_unresolved' if negative[key] else 'not_available',
            export_within_observation=known,negative_full_pair_receipts=len(negative[key]),source_measurement_available=value is not None))
    pairdefs=[]
    for a in contract['cases']:
        for b in contract['cases']:
            shape=(a['placement_id']==b['placement_id'] and a['nominal_flow_level']==b['nominal_flow_level']
                   and a['shape']=='equal_volume_sphere' and b['shape']=='rigid_prolate_ar4')
            flow=(a['placement_id']==b['placement_id'] and a['shape']==b['shape']
                  and (a['nominal_flow_level'],b['nominal_flow_level']) in ((.5,1.),(1.,2.)))
            if shape or flow:pairdefs.append(dict(kind='shape' if shape else 'flow',first=a['id'],second=b['id'],
                comparison=pair_contrasts(measured.get(a['id']),measured.get(b['id']),protocol['features'])))
    api.require(len(pairdefs)==14,'Six paired shape and eight adjacent-flow comparisons, no time-sample replicates')
    api.verify_mapping(artifacts);destination.mkdir(parents=True,exist_ok=False)
    write_csv(destination/'case_index.csv',index,list(index[0]))
    contrasts=[]
    for pair in pairdefs:
        result=pair['comparison']
        if not result['available']:continue
        sections=([dict(kind='common_full_pore_volume',target=.01,**result['summary'])]
                  if result['summary']['available'] else [])+result['queries']
        for section in sections:
            if not section['available']:continue
            for feature,row in section['features'].items():
                contrasts.append(dict(first=pair['first'],second=pair['second'],pair_kind=pair['kind'],clock=section['kind'],target=section['target'],
                    feature=feature,available=row['available'],coarse_difference=row.get('coarse_difference'),fine_difference=row.get('fine_difference'),
                    twice_sum_feature_changes=row.get('twice_sum_feature_changes'),resolved=row.get('resolved',False),reason=row['reason']))
    fields=['first','second','pair_kind','clock','target','feature','available','coarse_difference','fine_difference','twice_sum_feature_changes','resolved','reason']
    write_csv(destination/'paired_contrasts.csv',contrasts,fields)
    outputs={str(p):s.sha(p) for p in destination.glob('*.csv')}
    body=dict(passed=True,scope='Authenticated INTERMEDIATE twelve-label assembly; never final study admission',
        paper1_dataset_complete=False,all12_temporally_measured=len(measured)==12,temporally_measured_cases=len(measured),
        case_index=index,negative_attempts_by_logical_case=negative,pairs=pairdefs,labelled_export_count_bounds=export_bounds(binary),
        missing_completion_evidence=['Selected middle-flow third-level checks','Current-setting spatial/model-domain and targeted robustness',
            'All-case failure/censoring/work accounting and resolved claim audit','Complete reproducible publication figures/tables and final closure'],
        original_physics_changes=[],original_accuracy_gate_changes=[],new_transport_steps=0,new_native_solver_calls=0,
        source_files=SOURCE_FILES,inputs=artifacts,artifacts=outputs,
        reproduce_command=[sys.executable,'-B',str(SELF),*sys.argv[1:]],utc=s.utc())
    api.verify_mapping(SOURCE_FILES);api.verify_mapping(artifacts)
    s.seal(destination,body);print(json.dumps(dict(passed=True,paper1_dataset_complete=False,temporally_measured_cases=len(measured),
        case_count=len(index),labelled_export_count_bounds=body['labelled_export_count_bounds'],results_sha256=s.sha(destination/'results.json'))),flush=True)
    return body


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observables',type=Path,nargs='*',default=[])
    parser.add_argument('--failed-comparison',type=Path,nargs='*',default=[])
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args();assemble(args.observables,args.failed_comparison,args.destination)
