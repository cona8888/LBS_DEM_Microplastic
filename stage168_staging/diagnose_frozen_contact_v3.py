"""Exact frozen-pose replay under all existing scoped solver wrappers.

No integrator runs: the innermost integration entry is replaced with a single
algebraic probe. Versions 1/2 omitted outer scalar/recovery wrappers; preserve
their non-matching diagnostics rather than treating them as original failures.
"""
import sys
import diagnose_frozen_contact_v2 as corrected
capture=corrected.capture
exact= capture.diag.replay


def wrapped(field,geometry,spec,state,dt):
    parent=capture.parent
    core=parent.api.frozen.oldcore
    original=core.integrate
    calls=[]
    def algebra_only(*args,**kwargs):
        if calls:raise RuntimeError('only one frozen algebraic probe authorized')
        calls.append(True)
        return {'frozen_pose_result':exact(field,geometry,spec,state,dt)}
    core.integrate=algebra_only
    try:
        with parent.engine.runtime.repair_scope():
            result=parent.api.frozen.parent.integrate()
        if len(calls)!=1:raise RuntimeError('frozen probe dispatch mismatch')
        return result['frozen_pose_result']
    finally:core.integrate=original


capture.diag.replay=wrapped
capture.DESIGN=capture.DESIGN.with_name('design_03.json')
capture.OUT=capture.OUT.with_name('capture_03')
if __name__=='__main__':
    if sys.argv[1:]==['prepare']:capture.prepare()
    elif sys.argv[1:]==['run']:capture.run()
    else:raise ValueError('prepare or run')
