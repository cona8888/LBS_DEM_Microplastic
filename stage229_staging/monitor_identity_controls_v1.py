"""Pure fake-process controls for a read-only birth-first monitor adapter."""
import json
import psutil
import campaign_common_v1 as c
import monitor_recovery_v3 as m


def run():
    c.bound(); c.environment()
    target = c.OUT/'monitor_identity_repair_01'
    if target.exists():
        raise RuntimeError('Create-only control evidence; existing attempt preserved')
    cases = []
    receipt = dict(pid=1234, created=1000.0, command=['python.exe', '-B', 'worker.py'])

    class FakeProcess:
        def __init__(self, birth=1000.0, command=None, birth_denied=False, command_denied=False):
            self.birth = birth; self.command = receipt['command'] if command is None else command
            self.birth_denied = birth_denied; self.command_denied = command_denied
            self.birth_reads = 0; self.command_reads = 0
        def create_time(self):
            self.birth_reads += 1
            if self.birth_denied: raise psutil.AccessDenied(1234)
            return self.birth
        def cmdline(self):
            self.command_reads += 1
            if self.command_denied: raise psutil.AccessDenied(1234)
            return self.command

    def check(name, record, process, status, command_reads, factory_error=None):
        factory_reads = []
        def factory(pid):
            factory_reads.append(pid)
            if factory_error: raise factory_error(pid)
            return process
        result = m.inspect_process(record, factory)
        assert result['status'] == status, (name, result)
        assert process is None or process.command_reads == command_reads, name
        cases.append(dict(name=name, passed=True, result=result,
            fake_factory_reads=len(factory_reads),
            fake_birth_reads=0 if process is None else process.birth_reads,
            fake_command_reads=0 if process is None else process.command_reads))
        return result

    r = check('different_birth_inaccessible_command', receipt,
        FakeProcess(birth=2000.0, command_denied=True), 'identity_mismatch', 0)
    assert r['birth_matches'] is False and r['command_matches'] is None and r['command_inspected'] is False
    r = check('same_birth_same_command', receipt, FakeProcess(), 'exact_launch_identity_running', 1)
    assert r['birth_matches'] is True and r['command_matches'] is True
    check('same_birth_wrong_command', receipt, FakeProcess(command=['unrelated.exe']), 'identity_mismatch', 1)
    check('unreadable_birth_not_retired', receipt, FakeProcess(birth_denied=True), 'identity_inspection_denied', 0)
    check('same_birth_unreadable_command_not_retired', receipt, FakeProcess(command_denied=True), 'identity_inspection_denied', 1)
    check('pid_absent', receipt, None, 'recorded_pid_absent', 0, psutil.NoSuchProcess)
    malformed = [dict(receipt, pid=True), dict(receipt, pid=-1), dict(receipt, created=None),
        dict(receipt, created=float('nan')), dict(receipt, command=[]), dict(receipt, command=[''])]
    for index, record in enumerate(malformed):
        r = check('malformed_receipt_'+str(index), record, None, 'unqualified_identity_receipt', 0)
        assert cases[-1]['fake_factory_reads'] == 0
    check('conflicting_command_argv', dict(receipt, argv=['different.exe']), None,
        'conflicting_command_argv_receipt', 0)
    assert cases[-1]['fake_factory_reads'] == 0
    check('legacy_argv_same_birth_exact', dict(pid=1234, created=1000.0, argv=receipt['command']),
        FakeProcess(), 'exact_launch_identity_running', 1)
    assert c.sha(m.ORIGINAL) == m.ORIGINAL_SHA256
    assert c.sha(m.RETIREMENT) == m.RETIREMENT_SHA256
    original_sha = c.sha(m.ORIGINAL)
    result = dict(passed=True, utc=c.utc(), authorization_sha256=c.sha(c.AUTH),
        numerical_calls=0, transport_steps=0, live_process_inspections=0, process_actions=0,
        changes_active_sources_or_bindings=False, original_monitor_preserved=True,
        interpretation='Birth mismatch proves the recorded process identity differs; unavailable birth or a matching birth with unavailable command never proves retirement.',
        cases=cases, number_of_controls=len(cases),
        sources={str(m.ORIGINAL):original_sha, str(m.__file__):c.sha(m.__file__), str(__file__):c.sha(__file__)},
        inputs={str(m.RETIREMENT):c.sha(m.RETIREMENT), str(m.RETIREMENT.parent/'completion.json'):c.sha(m.RETIREMENT.parent/'completion.json')})
    c.commit(target/'results.json', result)
    c.commit(target/'completion.json', dict(passed=True, utc=c.utc(), results_sha256=c.sha(target/'results.json')))
    print(json.dumps(dict(passed=True, number_of_controls=len(cases), results_sha256=c.sha(target/'results.json'),
        monitor_source_sha256=c.sha(m.__file__), numerical_calls=0, process_actions=0), sort_keys=True))
    return result


if __name__ == '__main__':
    run()
