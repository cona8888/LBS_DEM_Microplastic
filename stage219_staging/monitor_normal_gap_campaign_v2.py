"""Bounded tail seals; preserve V1 full initial snapshot and all identity guards."""
from pathlib import Path
import json,sys
import monitor_normal_gap_campaign_v1 as previous
api,job=previous.api,previous.job
SOURCE=Path(previous.__file__)
source=SOURCE.read_text()
before="for ready in sorted((job.RUN/c['id']).glob('segment_*.ready.json')):"
after="for ready in sorted((job.RUN/c['id']).glob('segment_*.ready.json'))[-2:]:"
api.require(source.count(before)==1,'one bounded latest-two per-case full raw-seal observation site')
source=source.replace(before,after)
before="                    job.policy.verify_receipt(paths,c['id'],index,expected,d['audit_source_sha256'],m['input_checkpoint_sha256'],prior_receipt)"
after="""                    parent=job.paths(job.RUN,c['id'],index-1)['receipt'] if index>1 else None
                    prior_receipt=None if parent is None else api.sha(parent)
                    job.policy.verify_receipt(paths,c['id'],index,expected,d['audit_source_sha256'],m['input_checkpoint_sha256'],prior_receipt)"""
api.require(source.count(before)==1,'exact immediate sealed receipt ancestry for bounded tail')
source=source.replace(before,after)
before='all_committed_raw_full_seals_verified=seals'
api.require(source.count(before)==1,'honest limited read-only seal scope')
source=source.replace(before,'latest_two_per_case_full_raw_seals_verified=seals, raw_numerical_full_history_audits_remain_owned_by_streaming_auditor=True')
before="str(Path(__file__).with_name('run_terminal_evaluator_v1.py')) in cmd"
after="any(str(Path(__file__).with_name(n)) in cmd for n in ('run_terminal_evaluator_v1.py','run_terminal_evaluator_v2.py','evaluate_normal_gap_campaign_v2.py'))"
api.require(source.count(before)==1,'include exact versioned terminal evaluator/witness commands')
source=source.replace(before,after)
ns=dict(__name__='_stage219_bounded_read_only_v2',__file__=__file__)
exec(compile(source,__file__+'::same_guards_bounded_tail_and_versioned_evaluation','exec'),ns)
def run(expected):
    r=ns['run'](expected);r.update(read_only_monitor_version=2,previous_monitor_source_sha256=api.sha(SOURCE),bounded_full_raw_tail_scope=2)
    api.require(r['latest_two_per_case_full_raw_seals_verified']<=12,'bounded raw monitoring, never a substitute for full terminal audit')
    return r
if __name__=='__main__':print(json.dumps(run(sys.argv[1]),indent=2))
