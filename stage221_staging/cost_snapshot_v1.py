"""Read-only cost ledger; no transport, source import, or scientific gate change."""
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = Path('D:/MATDEM_MICROPLASTIC/stage219_runs/normal_gap_campaign_20261001/run_01')
NEW = ROOT / 'stage220_runs/checkpoint_recovery_20261006/production_01'
DESIGN = ROOT / 'stage219_designs/normal_gap_campaign_20261001/design_01.json'
RECOVERY = ROOT / 'stage220_designs/checkpoint_recovery_20261006/design_01.json'
OUT = ROOT / 'stage221_evaluations/cost_review_20261007/snapshot_01'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run():
    assert not OUT.exists(), 'Exclusive immutable snapshot'
    evidence = {}

    def read(path):
        raw = path.read_bytes()
        evidence[str(path)] = sha(raw)
        return json.loads(raw)

    design = read(DESIGN)
    plan = read(RECOVERY)
    physical_sha = evidence[str(DESIGN)]
    recovery_sha = evidence[str(RECOVERY)]
    cases = []
    totals = dict(steps=0, producer_transaction_seconds=0., physics_audit_seconds=0.,
                  certified_sweeps=0, fallback_force_systems=0, segments=0)

    def accumulator():
        return {k: 0 for k in totals}

    def add(bucket, steps, transaction, summary):
        assert steps > 0 and math.isfinite(transaction) and transaction >= 0
        assert summary['passed'] and summary['steps'] == steps
        audit = summary['audit_seconds']
        assert math.isfinite(audit) and audit >= 0
        values = dict(steps=steps, producer_transaction_seconds=transaction,
                      physics_audit_seconds=audit, certified_sweeps=summary['certified_sweeps'],
                      fallback_force_systems=summary['fallback_force_systems'], segments=1)
        for key, value in values.items():
            bucket[key] += value
            totals[key] += value

    for case in design['cases']:
        folder = OLD / case['id']
        markers = sorted(folder.glob('segment_*.ready.json'))
        old = accumulator()
        stop = 0.
        previous = None
        for index, path in enumerate(markers, 1):
            assert path.name == f'segment_{index:05d}.ready.json'
            ready = read(path)
            receipt_path = folder / f'segment_{index:05d}.audit.json'
            receipt = read(receipt_path)
            summary = receipt['summary']
            assert ready['design_sha256'] == receipt['design_sha256'] == physical_sha
            assert ready['case'] == receipt['case'] == case['id']
            assert ready['input_checkpoint_sha256'] == receipt['input_checkpoint_sha256']
            assert receipt['audit_source_sha256'] == design['audit_source_sha256']
            assert receipt['ready_sha256'] == evidence[str(path)]
            assert receipt['previous_receipt_sha256'] == previous
            assert receipt['status'] == 'independently_verified'
            assert summary['start_s'] == stop and summary['stop_s'] > stop
            add(old, ready['steps'], ready['transaction_seconds'], summary)
            stop = summary['stop_s']
            previous = evidence[str(receipt_path)]
        row = dict(case=case['id'], shape=case['shape'], sample_id=case['sample_id'],
                   timestep_factor=case['factor'], horizon_s=case['spec']['horizon_s'],
                   original=old, stop_s=stop, label=summary['status'])
        if case['id'] == plan['case']:
            assert stop == plan['original_time_s'] and old['steps'] == plan['original_saved_steps']
            new = accumulator()
            previous = None
            before = plan['seed_checkpoint_sha256']
            recent = []
            # Freeze the inventory before reading; the live producer may append later.
            markers = sorted(NEW.glob('segment_*/completion.json'))
            for index, complete_path in enumerate(markers, 1):
                assert complete_path.parent.name == f'segment_{index:05d}'
                complete = read(complete_path)
                result_path = complete_path.with_name('results.json')
                result = read(result_path)
                assert complete['passed'] and complete['results_sha256'] == evidence[str(result_path)]
                assert result['passed']
                assert result['recovery_design_sha256'] == recovery_sha
                assert result['physical_design_sha256'] == physical_sha
                assert result['previous_recovery_receipt_sha256'] == previous
                assert result['input_checkpoint_sha256'] == before
                summary = result['summary']
                assert summary['start_s'] == stop and summary['stop_s'] > stop
                accounting_path = result_path.with_name('accounting.json')
                accounting = read(accounting_path)
                assert result['artifacts'][str(accounting_path)] == evidence[str(accounting_path)]
                assert accounting['saved_steps'] == result['new_saved_steps']
                assert accounting['transaction_seconds'] == result['transaction_seconds']
                add(new, result['new_saved_steps'], result['transaction_seconds'], summary)
                delta = summary['stop_s'] - stop
                recent.append(dict(delta_s=delta, producer_seconds=result['transaction_seconds'],
                                   audit_seconds=summary['audit_seconds']))
                stop = summary['stop_s']
                before = result['output_checkpoint_sha256']
                previous = evidence[str(result_path)]
            row.update(recovery=new, stop_s=stop, label=summary['status'])
            remaining = max(0., row['horizon_s'] - stop)
            row['recent_ten_local_projection'] = dict(
                remaining_physical_s=remaining,
                producer_hours_median=remaining * statistics.median(x['producer_seconds']/x['delta_s'] for x in recent[-10:]) / 3600,
                limitation='Local producer-transaction extrapolation, not a bound; excludes decode, archive validation, final evaluation and scheduling.')
        combined = {k: row['original'][k] + row.get('recovery', {}).get(k, 0) for k in totals}
        row['combined'] = combined
        row['producer_hours'] = combined['producer_transaction_seconds'] / 3600
        row['physics_audit_hours'] = combined['physics_audit_seconds'] / 3600
        row['fallback_systems_per_saved_step'] = combined['fallback_force_systems'] / combined['steps']
        row['fallback_systems_per_certified_sweep'] = (
            combined['fallback_force_systems'] / combined['certified_sweeps']
            if combined['certified_sweeps'] else None)
        row['mean_saved_dt_s'] = row['stop_s'] / combined['steps']
        cases.append(row)
        print('COST_CASE', case['id'], row['producer_hours'], row['physics_audit_hours'], flush=True)

    result = dict(utc=datetime.now(timezone.utc).isoformat(), passed=True, new_trajectory_steps=0,
                  source_sha256=sha(Path(__file__).read_bytes()), cases=cases, totals=totals,
                  scope='Fresh ready/audit receipt chain hashes and recovery completion/accounting seals; raw archives and traces not rehashed here. No physics replay. Final scientific evaluation remains separate.',
                  timing_scope='Producer transaction includes integration, telemetry copying and raw archive writing. Physics audit timer excludes other archive decoding and validation. Summed task durations are not campaign wall time or CPU time; historical workers overlapped.',
                  diagnostic_limit='Fallback counts describe solver use, not a measured fraction of execution time. A profiler is needed for phase attribution.',
                  excluded_costs=['restart qualification', 'checkpoint reconstruction', 'read-only analyses', 'final evaluation', 'unsaved work at interruption', 'process setup and scheduling'],
                  final_evaluation_complete=(ROOT/'stage220_evaluations/checkpoint_recovery_20261006/combined_evaluation_01/completion.json').exists(),
                  evidence=evidence)
    OUT.mkdir(parents=True, exist_ok=False)
    raw = (json.dumps(result, indent=2, sort_keys=True) + '\n').encode()
    with (OUT/'results.json').open('xb') as stream:
        stream.write(raw)
    with (OUT/'completion.json').open('x') as stream:
        json.dump(dict(passed=True, results_sha256=sha(raw)), stream, indent=2)
    print('COST_SNAPSHOT', totals, flush=True)


if __name__ == '__main__':
    run()
