"""Read-only v5: sealed completed-worker PID reuse, explicit template binding.

V4's preflight assumed the historical monitoring template was in the production
source manifest. It was not. Preserve that failed version; positively bind the
unchanged read-only template here without changing the production manifest.
"""
from pathlib import Path
from types import FunctionType
import monitor_cone_campaign_v4 as previous

TEMPLATE_SHA = 'bfa4b45d6d15e6e65c0fa7e108a7f42384b685b209b0237624ae93a1c008ac2a'
V4_SHA = 'bcf8c0fcd0789090440edea6ae89b3b41175cb4cd1b0846847c90f561fb700cb'


def guarded_template(source):
    assert source.resolve() == Path(__file__).resolve().parents[1] / 'stage200_staging/monitor_revised_campaign_v1.py'
    assert previous.previous.sha(source) == TEMPLATE_SHA, 'explicit original read-only template SHA'
    text = source.read_text()
    before = 'p=psutil.Process(pid);cmd=p.cmdline();expected=[str(v).lower() for v in argv]'
    after = '''p=psutil.Process(pid)
            replacement=different_executable(p,role,argv)
            if replacement is not None:
                processes.append(replacement);continue
            cmd=p.cmdline();expected=[str(v).lower() for v in argv]'''
    assert text.count(before) == 1
    return text.replace(before, after)


def run(expected):
    assert previous.previous.sha(previous.__file__) == V4_SHA, 'failed V4 source preserved unchanged'
    adapted = FunctionType(previous.run.__code__, dict(previous.run.__globals__,
                           guarded_template=guarded_template, __file__=__file__), 'read_only_v5')
    result = adapted(expected)
    result.update(read_only_monitor_version=5, monitor_v5_sha256=previous.previous.sha(__file__),
                  preserved_failed_v4_sha256=V4_SHA, read_only_template_sha256=TEMPLATE_SHA)
    return result


if __name__ == '__main__':
    import json, sys
    print(json.dumps(run(sys.argv[1]), indent=2))
