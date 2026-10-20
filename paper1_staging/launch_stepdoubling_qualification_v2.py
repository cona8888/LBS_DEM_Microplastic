"""Inactive sole launch wrapper and separate post-retirement authenticator.

This file creates no clock/approval/authority. The wrapper owns the actual
supervisor Popen handle, records its observed return, and closes its logs.
The separate close command runs only after exact wrapper/supervisor retirement.
"""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import time

import run_stepdoubling_qualification_v2 as run


def launch():
    import psutil
    run.environment()
    p=run.authority(False,refresh_sources=True)
    folder=run.OUT/'launcher'
    run.need(not folder.exists() and not (run.OUT/'supervisor').exists(),
             'exactly one fresh launcher; preserve any earlier partial launch')
    run.verify_mapping(p['historical_evidence_files'])
    folder.mkdir(parents=True,exist_ok=False)
    me=psutil.Process();me.cpu_affinity([14])
    run.commit(folder/'launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),
        design_sha256=run.sha(run.PLAN),utc=run.utc()))
    command=[str(run.PYTHON),'-B','-u',str(run.SELF),'supervise']
    forced=False;errors=[];child_launch=None
    with (folder/'stdout.log').open('xb') as stdout, (folder/'stderr.log').open('xb') as stderr:
        child=subprocess.Popen(command,cwd=run.ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            child_launch=run.process_identity(child,command)
            run.commit(folder/'supervisor_launch.json',child_launch)
            while child.poll() is None:
                if time.time()>=run.instant(p['end_utc'])-300:
                    forced=True
                    break
                time.sleep(.5)
        except BaseException as exc:
            forced=True;errors.append(dict(stage='registration_or_wait',error=repr(exc)))
            # Recapture is permitted only through the SAME still-live original
            # Popen handle. Access denial never authorizes a PID-only stop.
            if child_launch is None:
                try:child_launch=run.process_identity(child,command)
                except BaseException as capture:
                    errors.append(dict(stage='exact_identity_unresolved',error=repr(capture)))
        finally:
            if forced:
                # A final backstop only. Exact birth AND full accessible command
                # are required; reused/inaccessible identities are never killed.
                owned=[] if child_launch is None else [child_launch]
                try:owned += [r['launch'] for r in run.registered_identities()]
                except Exception as exc:errors.append(dict(stage='registered_inventory',error=repr(exc)))
                owner=run.OUT/'owner/launch.json'
                if owner.exists():
                    try:owned.append(run.read(owner))
                    except Exception as exc:errors.append(dict(stage='owner_identity_inventory',error=repr(exc)))
                # Stop descendants first where their identities are known, then
                # the supervisor from its captured original Popen identity.
                if child_launch is not None:
                    owned=[item for item in owned if item is not child_launch]+[child_launch]
                for identity in owned:
                    try:
                        if not run.inspect_identity(identity)['retired']:
                            run.exact_stop(psutil.Process(identity['pid']),identity)
                    except Exception as exc:
                        errors.append(dict(identity=identity,error=repr(exc)))
            try:actual_return=child.wait(timeout=30)
            except BaseException as exc:
                run.commit(folder/'unresolved_registration_failure.json',dict(passed=False,
                    error=repr(exc),identity=child_launch,errors=errors,live_owned_handle_unresolved=True,
                    no_exitcode_inferred=True,requires_attention=True,utc=run.utc()))
                raise
    # The logs above are CLOSED, and the actual supervisor return was observed
    # through the original handle. This wrapper is still administrative-live.
    if child_launch is None:
        run.commit(folder/'unresolved_registration_failure.json',dict(passed=False,
            actual_supervisor_returncode=actual_return,supervisor_returncode_directly_observed=True,
            retirement_authenticated=False,errors=errors,no_exit_identity_inferred=True,
            closed_logs={str(path):run.sha(path) for path in (folder/'stdout.log',folder/'stderr.log')},utc=run.utc()))
        raise RuntimeError('Unresolved supervisor launch identity; actual return/logs preserved, no retirement inferred')
    try:observation=run.inspect_identity(child_launch)
    except Exception as exc:
        observation=dict(retired=False,unresolved_identity=True,error=repr(exc))
        errors.append(dict(stage='post_wait_identity',error=repr(exc)))
    run.seal(folder/'completion_01',dict(passed=not forced and not errors,
        actual_supervisor_returncode=actual_return,supervisor_returncode_directly_observed=True,
        supervisor_launch=child_launch,supervisor_retirement=observation,forced=forced,errors=errors,
        closed_logs={str(path):run.sha(path) for path in (folder/'stdout.log',folder/'stderr.log')},
        wrapper_own_exitcode_not_observed=True,wrapper_administrative_live_while_sealing=True,
        final_external_receipt_still_required=True,design_sha256=run.sha(run.PLAN),utc=run.utc()))
    print('ACTUAL_SUPERVISOR_RETURN',actual_return,'FORCED',forced,'ERRORS',len(errors),flush=True)
    return 0 if actual_return==0 and not forced and not errors else 2


def close(expected_wrapper_completion_sha256):
    run.environment()
    p=run.authority(False,refresh_sources=False)
    folder=run.OUT/'launcher';path=folder/'completion_01/results.json'
    run.need(run.is_sha(expected_wrapper_completion_sha256)
             and run.sha(path)==expected_wrapper_completion_sha256,
             'caller-pinned actual wrapper completion, never an inferred exit')
    wrapper=run.sealed(path)
    run.need(wrapper['supervisor_returncode_directly_observed'] is True,
             'actual original supervisor Popen return, never an inferred zero')
    identities=[run.read(folder/'launch.json'),wrapper['supervisor_launch']]
    owner=run.OUT/'owner/launch.json'
    if owner.exists():identities.append(run.read(owner))
    identities += [r['launch'] for r in run.registered_identities()]
    before=run.assert_retired(identities)
    run.verify_mapping(wrapper['closed_logs'])
    errors=[];owner_exit=supervisor=final=None
    for key in ('source_files','physical_inputs','evidence_files','historical_evidence_files'):
        try:run.verify_mapping(p[key])
        except Exception as exc:errors.append(dict(stage=key,error=repr(exc)))
    try:
        owner_exit=run.read(run.OUT/'owner/exit.json')
        run.verify_mapping(owner_exit['logs'])
        run.need(owner_exit['launch']==run.read(owner),'owner observed exit belongs to exact immutable launch')
    except Exception as exc:errors.append(dict(stage='owner_exit_or_logs',error=repr(exc)))
    try:
        supervisor=run.sealed(run.OUT/'supervisor/completion_01/results.json')
        actual=run.read(run.OUT/'supervisor/launch.json')
        run.need(all(actual[k]==identities[1][k] for k in ('pid','created','command')),
                 'wrapper actual Popen identity equals supervisor own launch')
        run.need(supervisor['held_design_sha256']==run.sha(run.PLAN)
            and supervisor['directly_observed_owner_exit_sha256']==run.sha(run.OUT/'owner/exit.json')
            and owner_exit is not None and supervisor['directly_observed_owner_returncode']==owner_exit['returncode'],
            'immutable actual owner exit and held design association')
    except Exception as exc:errors.append(dict(stage='supervisor_associations',error=repr(exc)))
    try:
        final=run.sealed(run.OUT/'final_disposition_01/results.json')
        run.need(supervisor is not None and supervisor['final_disposition_sha256']==run.sha(run.OUT/'final_disposition_01/results.json')
                 and final['design_sha256']==run.sha(run.PLAN),'immutable original final disposition association')
        # Never bless a new current digest map in place of its original seals.
        run.verify_mapping(final['artifacts'])
        current_counts=run.ledger()
        run.need(current_counts==final['ledger'],'no work/ledger extension after final disposition')
        allowed={'owner/exit.json','owner/stdout.log','owner/stderr.log',
            'supervisor/completion_01/results.json','supervisor/completion_01/completion.json',
            'launcher/completion_01/results.json','launcher/completion_01/completion.json',
            'launcher/stdout.log','launcher/stderr.log',
            'final_disposition_01/results.json','final_disposition_01/completion.json'}
        extras=set(run.artifact_inventory(exclude_live=False))-set(final['artifacts'])
        run.need(all(Path(name).relative_to(run.OUT).as_posix() in allowed for name in extras),
                 'no extra native/raw/reservation/admission work after final inventory')
    except Exception as exc:errors.append(dict(stage='immutable_final_or_ledger',error=repr(exc)))
    artifacts=run.artifact_inventory(exclude_live=False)
    run.verify_mapping(artifacts)
    after=run.assert_retired(identities)
    run.need(time.time()<run.instant(p['end_utc']),'final authentication inside SAME fixed end')
    qualified=(not errors and wrapper['actual_supervisor_returncode']==0 and not wrapper['forced'] and not wrapper['errors']
        and supervisor is not None and supervisor.get('passed') is True
        and final is not None and final.get('qualification_passed') is True)
    if qualified:
        for name in ('comparison_fine','comparison_coarse'):
            try:
                run.need(run.sealed(run.OUT/name/'results.json',positive=True)['original_gate_values']==run.ORIGINAL_GATES,
                         'both literal original full-path pair gates')
            except Exception as exc:
                errors.append(dict(stage=name,error=repr(exc)));qualified=False
    run.seal(run.OUT/'final_execution_receipt_01',dict(passed=not errors,closure_complete=not errors,
        exact_process_retirement_authenticated=True,closure_errors=errors,
        actual_supervisor_returncode=wrapper['actual_supervisor_returncode'],
        actual_owner_returncode=None if owner_exit is None else owner_exit['returncode'],
        wrapper_own_returncode_unobserved=True,no_exitcode_inferred=True,
        qualified=qualified,eligible_case_count=2 if qualified else 1,paper1_dataset_complete=False,
        exact_retirement_before=before,exact_retirement_after=after,artifacts=artifacts,
        final_disposition_sha256=run.sha(run.OUT/'final_disposition_01/results.json') if final is not None else None,
        supervisor_completion_sha256=run.sha(run.OUT/'supervisor/completion_01/results.json') if supervisor is not None else None,
        wrapper_completion_sha256=expected_wrapper_completion_sha256,
        prior_attempt_accounting=run.prior_attempt_accounting(),
        source_files=p['source_files'],physical_inputs=p['physical_inputs'],
        evidence_files=p['evidence_files'],historical_evidence_files=p['historical_evidence_files'],
        no_new_force_or_transport_work=True,design_sha256=run.sha(run.PLAN),utc=run.utc()))
    print('FINAL_EXECUTION_CLOSURE','COMPLETE',not errors,'QUALIFIED',qualified,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='action',required=True)
    subs.add_parser('launch')
    closer=subs.add_parser('close');closer.add_argument('wrapper_completion_sha256')
    args=parser.parse_args()
    if args.action=='launch':raise SystemExit(launch())
    close(args.wrapper_completion_sha256)
