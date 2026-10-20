"""Use real runtime ledger and the corrected documented fallback schema.

Failed zero_step_02 is retained. Stage169 repair telemetry stores dt but not
gaps; exact gaps are still checked between runtime, observer and inner system.
"""
import sys
import qualify_trial_trace_v2 as previous
import audit_contact_trial_trace_v2 as audit
import audit_optimized_record_v4 as kernel
job = previous.original
job.audit = audit
job.kernel = kernel
job.replay.__globals__['audit'] = audit
job.DESIGN = job.DESIGN.with_name('design_03.json')
job.OUT = job.OUT.with_name('zero_step_03')
if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']: job.prepare()
    elif sys.argv[1:] == ['run']: job.run()
    else: raise ValueError('prepare or run')
