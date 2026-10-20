"""Read-only full-horizon timecap monitor; mutable state never proves acceptance.

Authenticates the approved authority, exact process identities, and the immutable
reservation/admission chain. It never launches, stops, resumes, or advances work.
The original independent raw/physics/selector audits remain authoritative.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_core_v2 as shared

s = shared.s
ROOT = s.ROOT
DESIGNS = ROOT / 'paper1_designs/full_horizon_timecap_20261016'
OUT = ROOT / 'paper1_runs/full_horizon_timecap_20261016'
PLAN = DESIGNS / 'design_01.json'
AUTH = DESIGNS / 'authorization_01.json'
PROPOSAL = DESIGNS / 'proposal_01.json'
CONTROLLER = ROOT / 'paper1_staging/run_timecap_qualification_v1.py'
APPROVED_PROPOSAL_SHA256 = 'e293e344fedccfd5f47c8eca72fee3040b1caae9d71d4d708f7222cc09253f58'


def require(value, message):
    s.require(value, 'Full-horizon timecap monitor: ' + message)


def _instant(value):
    moment = datetime.fromisoformat(value)
    require(moment.tzinfo is not None, 'explicit timezone for every cutoff')
    return moment


def _level_id(factor):
    return 'f' + str(factor).replace('.', 'p')


def _bounded_path(path):
    target = Path(path).resolve()
    require(target == OUT or OUT in target.parents, 'ledger path stays inside this run')
    return target


def _identity(path):
    launch = s.read(path)
    require(type(launch.get('pid')) is int and isinstance(launch.get('command'), list)
            and launch['command'] and 'created' in launch,
            'complete PID, birth and full-command identity')
    # The original helper checks birth first; matching birth requires accessible
    # exact command bytes. Access denial is not interpreted as retirement.
    observed = s.identity(launch)
    return dict(path=str(path), sha256=s.sha(path), pid=launch['pid'], created=launch['created'],
                inspection=observed)


def _check_budgets(proposal, counts):
    caps = proposal['request']
    baseline = proposal['ledger']
    saved = counts['saved_steps'] + counts['reserved_steps']
    calls = counts['calls'] + counts['reserved_calls']
    require(saved <= caps['maximum_new_saved_steps'], 'shared new saved-step cap')
    require(calls <= caps['maximum_new_integration_calls'], 'shared new integration-call cap')
    require(baseline['conservative_prospective_baseline_saved_steps'] + saved
            <= caps['saved_step_ceiling_after'], 'all disclosed prior and new saved steps')
    require(baseline['conservative_prospective_baseline_integration_calls'] + calls
            <= caps['integration_call_ceiling_after'], 'all disclosed prior and new calls')
    require(counts['diagnostic_steps'] + counts['reserved_diagnostic_steps']
            <= caps['maximum_discarded_diagnostic_steps'], 'discarded diagnostic-step cap')
    require(counts['diagnostic_calls'] + counts['reserved_diagnostic_calls']
            <= caps['maximum_diagnostic_integration_calls'], 'diagnostic integration-call cap')
    for level in proposal['levels']:
        key = _level_id(level['factor'])
        row = counts['levels'][key]
        require(row['steps'] + row['reserved_steps'] <= level['maximum_new_production_steps']
                and row['calls'] + row['reserved_calls'] <= level['maximum_production_calls'],
                'prospectively fixed production caps for ' + key)


def monitor():
    require(s.sha(PROPOSAL) == APPROVED_PROPOSAL_SHA256, 'exact human-reviewed proposal')
    proposal = s.read(PROPOSAL)
    approval = s.fields.sealed(DESIGNS / 'human_approval_01/results.json')
    require(approval['passed'] and approval['proposal_sha256'] == APPROVED_PROPOSAL_SHA256,
            'sealed human approval binds this exact proposal')
    plan, auth = s.read(PLAN), s.read(AUTH)
    require(plan['authorization_sha256'] == s.sha(AUTH)
            and plan['proposal_sha256'] == APPROVED_PROPOSAL_SHA256
            and auth['proposal_sha256'] == APPROVED_PROPOSAL_SHA256,
            'plan, authority and approved proposal associations')
    require(plan['binding'] == s.api.digest({k: v for k, v in plan.items() if k != 'binding'}),
            'immutable complete plan binding')
    require(plan['start_utc'] == auth['start_utc'] and plan['end_utc'] == auth['end_utc'],
            'one shared absolute authority clock')
    start, end = _instant(auth['start_utc']), _instant(auth['end_utc'])
    require(0 < (end - start).total_seconds()
            <= proposal['request']['maximum_shared_wall_hours'] * 3600,
            'approved shared wall envelope')
    s.api.verify_mapping(proposal['source_files'])
    s.api.verify_mapping(proposal['physical_inputs'])
    s.api.verify_mapping(plan['source_files'])
    s.api.verify_mapping(plan['physical_inputs'])
    launch_auth = s.fields.sealed(OUT / 'launch_authentication_01/results.json')
    require(launch_auth['passed']
            and launch_auth['owner_identity_sha256'] == s.sha(OUT / 'owner_launch.json')
            and launch_auth['controller_source_sha256'] == s.sha(CONTROLLER)
            and launch_auth['design_sha256'] == s.sha(PLAN)
            and launch_auth['authorization_sha256'] == s.sha(AUTH)
            and launch_auth['proposal_sha256'] == APPROVED_PROPOSAL_SHA256,
            'immutable exact owner/controller launch authentication')
    owner = _identity(OUT / 'owner_launch.json')
    supervisor = _identity(OUT / 'supervisor/launch.json')
    now = datetime.now(timezone.utc)
    windows = []
    for folder in sorted((OUT / 'windows').glob('window_*')):
        window = s.read(folder / 'design_01.json')
        ws, we = _instant(window['start_utc']), _instant(window['end_utc'])
        cutoff = _instant(window['simulation_cutoff_utc'])
        require(start <= ws < cutoff <= we <= end
                and (we - ws).total_seconds()
                <= proposal['request']['maximum_hours_per_numerical_window'] * 3600,
                'bounded numerical-window clock inside the shared authority')
        worker_path = folder / 'worker_launch.json'
        identity = _identity(worker_path) if worker_path.exists() else None
        if identity is not None:
            worker = s.read(worker_path)
            window_auth = s.fields.sealed(folder / 'launch_authentication_01/results.json')
            require(worker['window_design_sha256'] == s.sha(folder / 'design_01.json')
                    and window_auth['passed']
                    and window_auth['window_design_sha256'] == s.sha(folder / 'design_01.json')
                    and window_auth['worker_launch_sha256'] == s.sha(worker_path)
                    and window_auth['controller_source_sha256'] == s.sha(CONTROLLER)
                    and window_auth['design_sha256'] == s.sha(PLAN),
                    'sealed numerical-window design, worker identity and shared-plan associations')
        exit_path = folder / 'exit.json'
        exit_code = None
        if exit_path.exists():
            exited = s.read(exit_path)
            exit_code = exited['returncode']
            if 'logs' in exited:
                s.api.verify_mapping(exited['logs'])
            require(identity is not None and identity['inspection']['retired'],
                    'a closed window has no exact live worker identity')
        windows.append(dict(window=folder.name, identity=identity, exit_code=exit_code,
                            simulation_cutoff_utc=window['simulation_cutoff_utc'],
                            end_utc=window['end_utc'], cutoff_reached=now >= cutoff))
    require(len(windows) <= proposal['request']['maximum_numerical_windows'],
            'approved numerical-window count')
    live_workers = [w for w in windows if w['identity'] is not None
                    and not w['identity']['inspection']['retired']]
    require(len(live_workers) <= 1, 'one exact numerical worker')
    levels = {_level_id(x['factor']): dict(steps=0, calls=0, reserved_steps=0,
              reserved_calls=0, time_s=0., last_full_checkpoint_sha256=None)
              for x in proposal['levels']}
    counts = dict(saved_steps=0, calls=0, diagnostic_steps=0, diagnostic_calls=0,
                  reserved_steps=0, reserved_calls=0, reserved_diagnostic_steps=0,
                  reserved_diagnostic_calls=0, levels=levels)
    pending = []
    reservations = sorted((OUT / 'reservations').glob('*.json'))
    indices = []
    for path in reservations:
        reservation = s.read(path)
        index = reservation['global_index']
        require(type(index) is int and index == len(indices) + 1
                and path.name == f'{index:06d}.json', 'contiguous unique global reservations')
        indices.append(index)
        level, label, kind = [reservation[k] for k in ('level_id', 'label', 'kind')]
        require(level in levels and isinstance(label, str) and label
                and isinstance(kind, str) and kind, 'explicit known level, label and work kind')
        folder = _bounded_path(OUT / 'levels' / level / 'records' / label)
        cap = reservation['maximum_saved_steps']
        require(type(cap) is int and 0 < cap <= proposal['request']['steps_per_record'],
                'positive bounded original per-record reservation')
        admission_path = OUT / 'admissions' / f'{index:06d}' / 'results.json'
        is_production = kind == 'production'
        if not admission_path.with_name('completion.json').exists():
            known = None
            accounting = folder / 'accounting.json'
            if accounting.exists():
                value = s.read(accounting)
                known = value['saved_steps']
                require(type(known) is int and 0 <= known <= cap, 'bounded known unverified work')
            pending.append(dict(global_index=index, level_id=level, label=label, kind=kind,
                                maximum_saved_steps=cap, known_saved_steps=known,
                                unknown_reserved_steps_upper_bound=cap if known is None else 0))
            counts['reserved_steps'] += cap
            counts['reserved_calls'] += 1
            if is_production:
                levels[level]['reserved_steps'] += cap
                levels[level]['reserved_calls'] += 1
            else:
                counts['reserved_diagnostic_steps'] += cap
                counts['reserved_diagnostic_calls'] += 1
            continue
        require(not pending, 'no successor reservation/admission after an unverified record')
        admission = s.fields.sealed(admission_path)
        require(admission['passed'] and admission['global_index'] == index
                and all(admission[k] == reservation[k] for k in ('level_id', 'label', 'kind'))
                and admission['cap'] == cap and admission['reservation_sha256'] == s.sha(path),
                'immutable admission binds exact prior reservation')
        saved = admission['saved_steps']
        require(type(saved) is int and 0 < saved <= cap, 'positive bounded admitted row count')
        guard_path = folder / 'guard_completion/results.json'
        extra_path = folder / 'timecap_guard/results.json'
        guard, extra = s.fields.sealed(guard_path), s.fields.sealed(extra_path)
        require(guard['passed'] and extra['passed']
                and admission['physical_guard_sha256'] == s.sha(guard_path)
                and admission['timecap_guard_sha256'] == s.sha(extra_path)
                and admission['raw_sha256'] == s.sha(folder / 'call.json.xz')
                and extra['raw_sha256'] == admission['raw_sha256']
                and guard['full_checkpoint_sha256'] == admission['full_checkpoint_sha256']
                and guard['saved_steps'] == extra['accepted_rows'] == saved,
                'both original and selector guards bind identical raw, checkpoint and steps')
        s.api.verify_mapping(guard['artifacts'])
        counts['saved_steps'] += saved
        counts['calls'] += 1
        if is_production:
            row = levels[level]
            require(label == f'production_{row["calls"] + 1:05d}'
                    and extra['start_s'] == row['time_s']
                    and extra['start_s'] < extra['stop_s'] <= proposal['full_exposure']['horizon_s'],
                    'complete contiguous fresh production clock and record order')
            row['steps'] += saved
            row['calls'] += 1
            row['time_s'] = extra['stop_s']
            row['last_full_checkpoint_sha256'] = admission['full_checkpoint_sha256']
        else:
            counts['diagnostic_steps'] += saved
            counts['diagnostic_calls'] += 1
    require(len(pending) <= proposal['request']['maximum_unverified_records'],
            'at most one unresolved integration record')
    admissions_folder = OUT / 'admissions'
    admission_indices = sorted(int(x.name) for x in admissions_folder.iterdir()
                               if x.is_dir() and (x / 'completion.json').exists()) \
                        if admissions_folder.exists() else []
    snapshot_last = len(indices)
    verified_admissions = list(range(1, counts['calls'] + 1))
    require([x for x in admission_indices if x <= counts['calls']] == verified_admissions,
            'no omitted or orphaned verified admission')
    newly_sealed = [x for x in admission_indices if counts['calls'] < x <= snapshot_last]
    require(set(newly_sealed).issubset({x['global_index'] for x in pending}),
            'only an initially pending record may seal during this snapshot')
    # A healthy owner may append while old raw records are hashed. New records
    # do not become an orphan merely because the monitor's initial snapshot
    # predates them; they make this observation incomplete and must be re-read.
    latest_reservations = sorted((OUT / 'reservations').glob('*.json'))
    require(len(latest_reservations) >= snapshot_last
            and latest_reservations[:snapshot_last] == reservations,
            'immutable reservation prefix never disappears or changes order')
    for index in admission_indices:
        require((OUT / 'reservations' / f'{index:06d}.json').exists(),
                'every sealed admission has a reservation')
    advanced = bool(newly_sealed) or len(latest_reservations) != snapshot_last
    _check_budgets(proposal, counts)
    state = s.read(OUT / 'state.json')
    # State can legitimately lag a just-sealed admission. It is displayed only;
    # exact progress, ceilings and unresolved work come from immutable records.
    retained = sum(p.stat().st_size for name in ('paper1_runs', 'paper1_designs', 'paper1_evaluations')
                   for p in (ROOT / name).rglob('*') if p.is_file())
    own = sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
    free = shutil.disk_usage(ROOT).free
    resources_ok = (retained <= proposal['request']['unchanged_total_retention_bytes']
                    and own <= proposal['request']['maximum_new_output_bytes']
                    and free >= proposal['request']['unchanged_free_reserve_bytes'])
    cutoff_live = any(w['cutoff_reached'] for w in live_workers)
    shared_expired_live = now >= end and (live_workers or not owner['inspection']['retired']
                                         or not supervisor['inspection']['retired'])
    failure = bool(state.get('error') or not resources_ok or cutoff_live or shared_expired_live)
    return dict(read_only=True, evidence_authentication_passed=True, passed=not failure,
                healthy=(False if failure else None if advanced else True),
                utc=now.isoformat(), owner=owner, supervisor=supervisor, windows=windows,
                live_numerical_workers=len(live_workers),
                state_progress_only={k: state.get(k) for k in ('phase', 'utc', 'window_count',
                    'current_window', 'current_level', 'new_saved_steps', 'new_calls', 'error')},
                immutable_ledger=counts, pending_records=pending,
                ledger_verified_through_global_index=snapshot_last,
                observation_advanced_during_read=advanced,
                newer_reservations_not_in_snapshot=len(latest_reservations) - snapshot_last,
                combined_saved_steps_upper_bound=proposal['ledger']['conservative_prospective_baseline_saved_steps']
                    + counts['saved_steps'] + counts['reserved_steps'],
                combined_integration_calls_upper_bound=proposal['ledger']['conservative_prospective_baseline_integration_calls']
                    + counts['calls'] + counts['reserved_calls'],
                resources=dict(passed=resources_ok, own_bytes=own, paper1_retained_bytes=retained, free_bytes=free),
                shared_end_utc=auth['end_utc'], numerical_cutoff_live=cutoff_live,
                shared_deadline_expired_with_exact_owned_process=bool(shared_expired_live),
                original_full_path_admission=False)


if __name__ == '__main__':
    print(json.dumps(monitor(), sort_keys=True), flush=True)
