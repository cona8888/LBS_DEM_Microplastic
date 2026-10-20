"""Review source-only qualification preparation, never authorize numerical work.

The exact current source snapshots and actual child test return codes are
retained. Failed preparation remains negative. Tests use artificial mechanics
or saved literal history; they cannot certify native restart reproducibility.
"""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'paper1_designs/full_horizon_repair_20261018'
PYTHON=Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')
STAGING=ROOT/'paper1_staging'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while b:=stream.read(1024*1024):h.update(b)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def commit(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def verify(mapping):
    for path,expected in mapping.items():
        assert sha(path)==expected, 'changed source/input/evidence '+str(path)


def launches(value):
    found=[]
    if isinstance(value,dict):
        if {'pid','created','command'}<=value.keys():found.append(value)
        for item in value.values():found.extend(launches(item))
    elif isinstance(value,list):
        for item in value:found.extend(launches(item))
    return found


def review():
    assert Path(sys.executable).resolve()==PYTHON.resolve()
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'))
    # Source-only import: this driver deliberately imports no model at module
    # load. Actual interface function bodies are independently reviewed too.
    driver=module(STAGING/'run_stepdoubling_qualification_v1.py','_prepared_driver')
    assert not driver.OUT.exists() and not driver.AUTH.exists() and not driver.PLAN.exists()
    assert not driver.APPROVAL.exists() and not driver.CLOCK.exists()
    interfaces=driver.source_interfaces()
    assert interfaces['all_required_interfaces_present'], interfaces
    closed_path=ROOT/'paper1_runs/first_activation_common_state_20261018_fresh/final_execution_receipt_01/results.json'
    closed=read(closed_path)
    assert sha(closed_path)=='1e046412ac89d93a447bf11b10deb0f6cf1c943ecc650eef768fa1f60df7c983'
    assert closed['all_exact_owned_identities_retired'] and closed['passed']
    # New paths start at t0. Historical raw/closed-diag dependencies establish
    # the conservative OLD ledger; they are not the new path's seed. Preserve
    # and authenticate them in the full evidence map, before/final execution.
    # Native field/geometry/definition inputs are freshly hashed per packet.
    inputs={}
    historical=dict(closed['expected_consumed_evidence_files'])
    evidence={}
    for path,expected in closed['expected_physical_inputs'].items():
        assert historical.get(path,expected)==expected
        historical[path]=expected
    def native_references(value):
        if isinstance(value,dict):
            if {'path','sha256'}<=value.keys():
                path,expected=value['path'],value['sha256']
                assert inputs.get(path,expected)==expected
                inputs[path]=expected
            for child in value.values():native_references(child)
        elif isinstance(value,list):
            for child in value:native_references(child)
    native_references(read(FOLDER/'physical_cases_qualification_01.json')['cases'])
    contract_path=ROOT/'paper1_designs/mechanism_feasibility_20261013/contract_01.json'
    contract=read(contract_path)
    inputs[str(contract_path)]=sha(contract_path)
    inputs[contract['physical_design_file']]=contract['physical_design_sha256']
    for name in ('results.json','completion.json'):
        path=contract_path.parent/'exposure_decision_01'/name
        inputs[str(path)]=sha(path)
    evidence[str(closed_path)]=sha(closed_path)
    evidence[str(closed_path.with_name('completion.json'))]=sha(closed_path.with_name('completion.json'))
    old_full=ROOT/'paper1_runs/full_horizon_timecap_20261016/final_execution_receipt_01/results.json'
    old_analysis=ROOT/'paper1_evaluations/full_horizon_repair_20261018/execution_01/receipt_01/results.json'
    identities=[]
    for path in (closed_path,old_full,old_analysis):
        d=read(path)
        assert d.get('passed') is True
        evidence[str(path)]=sha(path)
        evidence[str(path.with_name('completion.json'))]=sha(path.with_name('completion.json'))
        identities.extend(launches(d))
    unique={json.dumps({k:item[k] for k in ('pid','created','command')},sort_keys=True):item for item in identities}
    identities=list(unique.values())
    inspections_before=driver.assert_retired(identities)
    sources=dict(closed['expected_source_files'])
    # Construct only the source-bound stencil closure, with NO call to it and
    # no field/geometry/force evaluation. This exposes the actual WORK-policy
    # JSON and original stencil sources consumed by the live adapter factory.
    # Placeholder geometry is deliberately unusable for a mechanical replay.
    if str(STAGING) not in sys.path:sys.path.insert(0,str(STAGING))
    import audit_full_state_stepdoubling_v1 as actual_audit
    physical=read(FOLDER/'physical_cases_qualification_01.json')
    for case in physical['cases']:
        factory=actual_audit.create_original_mechanical_adapter(case['spec'],case['binding'],None,
            sha(FOLDER/'physical_cases_qualification_01.json'),physical['minimum_gap_semantics'])
        assert factory.native_qualification_claimed is False
        for path,expected in factory.source_files.items():
            assert sources.get(path,expected)==expected
            sources[path]=expected
    new_names=['full_state_stepdoubling_v1.py','check_full_state_stepdoubling_v1.py',
        'full_state_integration_adapter_v1.py','check_full_state_integration_adapter_v1.py',
        'audit_full_state_stepdoubling_v1.py','prepare_stepdoubling_restart_v1.py',
        'check_stepdoubling_audit_v1.py','run_stepdoubling_qualification_v1.py',
        'prepare_full_qualification_contract_v1.py','prepare_full_qualification_review_v1.py',
        'build_full_qualification_proposal_v1.py','check_stepdoubling_qualification_v1.py']
    new_names.extend(['launch_stepdoubling_qualification_v1.py','check_stepdoubling_launcher_v1.py'])
    # Include additional staged controllers/facades/fixtures explicitly; all
    # local prepared source files are pinned, never wildcard old dependencies.
    for name in new_names:
        path=STAGING/name
        sources[str(path)]=sha(path)
    for name in ('physical_cases_qualification_01.json','method_policy_qualification_01.json',
                 'method_policy_clock_amendment_01.json','budget_full_qualification_01.json'):
        path=FOLDER/name
        inputs[str(path)]=sha(path)
    verify(sources);verify(inputs);verify(evidence);verify(historical)
    controls=[]
    test_names=['check_full_state_stepdoubling_v1.py','check_full_state_integration_adapter_v1.py',
                'check_stepdoubling_audit_v1.py','check_stepdoubling_qualification_v1.py',
                'check_stepdoubling_launcher_v1.py']
    for name in test_names:
        path=STAGING/name
        assert path.is_file(), 'required actual source controls '+name
        sources[str(path)]=sha(path)
        started=time.monotonic()
        result=subprocess.run([str(PYTHON),'-B',str(path)],cwd=ROOT,env=os.environ.copy(),
                              capture_output=True,text=True,timeout=180)
        item=dict(source_file=str(path),source_sha256=sha(path),returncode=result.returncode,
                  seconds=time.monotonic()-started,stdout=result.stdout,stderr=result.stderr,
                  no_target_force_or_transport=True)
        controls.append(item)
        print('SOURCE_CONTROL',name,result.returncode,flush=True)
        if result.returncode:
            negative=next(FOLDER/f'preparation_controls_negative_{i:02d}.json'
                          for i in range(1,100) if not (FOLDER/f'preparation_controls_negative_{i:02d}.json').exists())
            commit(negative,dict(passed=False,tests=controls,source_files=sources,
                                new_native_calls=0,new_transport_steps=0,dispatch_authorized=False))
            raise RuntimeError('actual source control failed; preserved '+str(negative))
    # No source may change during tests. This is not a mechanism replay or
    # authentication of new physics results; all numerical qualification gates
    # remain inside the future specifically approved resource envelope.
    verify(sources);verify(inputs);verify(evidence);verify(historical)
    inspections_after=driver.assert_retired(identities)
    resources=driver.resource_guard(force_inventory=True)
    assert resources['total_retained_bytes']+driver.OWN_BYTES<=driver.RETENTION_BYTES
    assert resources['free_bytes']-driver.OWN_BYTES>=driver.FREE_BYTES
    resources.update(projected_total_at_own_ceiling=resources['total_retained_bytes']+driver.OWN_BYTES,
                     projected_free_at_own_ceiling=resources['free_bytes']-driver.OWN_BYTES)
    folder=FOLDER/'preparation_qualification_01'
    assert not folder.exists(),'create-only preparation including negative partial work'
    result=dict(schema='paper1.stepdoubling.source-preparation.v1',passed=True,
        utc=datetime.now(timezone.utc).isoformat(),source_files=sources,physical_inputs=inputs,evidence_files=evidence,
        historical_evidence_files=historical,
        prior_exact_process_identities=identities,retirement_before=inspections_before,retirement_after=inspections_after,
        all_required_interfaces_present=True,source_interface_checks=interfaces,controls=controls,
        resources=resources,actual_test_exits_observed=True,dispatch_authorized=False,
        evidence_schedule='Every old declared historical input/raw remains in historical_evidence_files, fully authenticated here and before/final authorized execution. Only actual new native field/geometry/definitions plus source/receipt-chain bindings are fresh per packet; no old prefix is reused.',
        fresh_authority_created=False,native_restart_qualification_completed=False,
        native_mechanical_qualification_completed=False,native_solver_calls=0,new_transport_steps=0,
        numerical_admission_requires_explicit_approval_and_native_prelude=True)
    folder.mkdir()
    commit(folder/'results.json',result)
    commit(folder/'completion.json',dict(passed=True,results_sha256=sha(folder/'results.json')))
    print('SOURCE_PREPARATION_COMPLETE',sha(folder/'results.json'),flush=True)


if __name__=='__main__':review()
