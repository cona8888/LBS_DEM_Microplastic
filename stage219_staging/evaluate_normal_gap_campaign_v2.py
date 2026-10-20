"""Versioned actual terminal entry point; uses qualified accounting-only adapter."""
import sys
import terminal_ledger_adapter_v1 as a
if __name__=='__main__':
    from pathlib import Path
    b=a.frozen.sealed(a.job.OUT/'terminal_command_binding_01/results.json');a.api.verify_mapping(b['inputs'])
    a.api.require(b['passed'] and b['inputs'][str(Path(__file__))]==a.api.sha(__file__),'exact qualified terminal command source')
    expected=sys.argv[1];s=a.install(expected)
    s.require_old_terminal_closure();s.job.evaluate('campaign')
