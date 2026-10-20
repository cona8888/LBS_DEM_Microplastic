"""Read-only identity-order repair around the unchanged frozen recovery monitor.

Different process birth proves the recorded identity is absent at this PID. A
command is inspected only when birth matches. Inspection denial never supplies
retirement evidence. No worker, controller, finalizer or manifest is changed.
"""
from pathlib import Path
import importlib, math, sys
import psutil
import campaign_common_v1 as c

ORIGINAL = Path(__file__).with_name('monitor_recovery_v2.py')
ORIGINAL_SHA256 = '0e47cfb786e0e216f6d251d3417b494c7f69421a3d8cf5501aaaa2a022f5db3b'
RETIREMENT = c.OUT/'initial_retirement_01/results.json'
RETIREMENT_SHA256 = 'e5eeecbb494e15439e1b271db47e94c51caa51f28431c077d1381dabb0bcfd6e'


def inspect_process(receipt, process_factory=None):
    """Read only; birth mismatch short-circuits inaccessible command inspection."""
    pid = receipt.get('pid'); created = receipt.get('created')
    expected = receipt.get('command', receipt.get('argv'))
    if (type(pid) is not int or pid <= 0 or type(created) not in (int, float)
            or not math.isfinite(created) or created <= 0
            or type(expected) is not list or not expected
            or not all(type(value) is str and value for value in expected)):
        return dict(status='unqualified_identity_receipt', pid=pid)
    if 'command' in receipt and 'argv' in receipt and receipt['command'] != receipt['argv']:
        return dict(status='conflicting_command_argv_receipt', pid=pid)
    if process_factory is None:
        process_factory = psutil.Process
    try:
        process = process_factory(pid)
        actual_birth = process.create_time()
        if actual_birth != created:
            return dict(status='identity_mismatch', pid=pid, birth_matches=False,
                command_matches=None, command_inspected=False,
                recorded_created=created, actual_created=actual_birth,
                recorded_command=expected, actual_command=None,
                command_not_inspected_because_birth_mismatch=True)
        actual_command = process.cmdline()
        matched = actual_command == expected
        return dict(status='exact_launch_identity_running' if matched else 'identity_mismatch',
            pid=pid, birth_matches=True, command_matches=matched, command_inspected=True,
            recorded_created=created, actual_created=actual_birth,
            recorded_command=expected, actual_command=actual_command)
    except psutil.NoSuchProcess:
        return dict(status='recorded_pid_absent', pid=pid,
            recorded_created=created, recorded_command=expected)
    except psutil.AccessDenied:
        return dict(status='identity_inspection_denied', pid=pid)


def run():
    c.bound(); c.environment()
    if c.sha(ORIGINAL) != ORIGINAL_SHA256:
        raise RuntimeError('Frozen original recovery monitor changed')
    if c.sha(RETIREMENT) != RETIREMENT_SHA256:
        raise RuntimeError('Frozen initial retirement receipt changed')
    proof = c.sealed(RETIREMENT)
    if (proof['passed'] is not True or proof['all_exact_launch_identities_retired'] is not True
            or proof['authorization_sha256'] != c.sha(c.AUTH)):
        raise RuntimeError('Sealed original retirement remains mandatory')
    original = importlib.import_module('monitor_recovery_v2')
    prior = original.inspect_process
    try:
        original.inspect_process = inspect_process
        return original.run()
    finally:
        original.inspect_process = prior


if __name__ == '__main__':
    if sys.argv[1:]:
        raise ValueError('Monitor takes no arguments')
    run()
