"""Exact-rational fixed-policy classifier, separate from producer code."""
from contextlib import contextmanager
from fractions import Fraction as F
from pathlib import Path
from types import FunctionType,SimpleNamespace
import math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage213_staging'))
import normal_gap_scope_v1 as original_scope
NAME='stage215_independent_fraction_sphere_gap_reference_v1'
POLICY_NAME='stage212_binary64_sphere_gap_band_v1'


def classify(x,c,a,b,r,g):
    x,c=np.asarray(x,dtype=float),np.asarray(c,dtype=float)
    a,b,r,g=map(float,(a,b,r,g))
    if x.shape!=(3,) or c.shape!=(3,) or not all(math.isfinite(z) for z in [*x,*c,a,b,r,g]) or min(a,b,r)<=0:
        raise ValueError('finite original centres/radii/raw gap required')
    if a!=b:
        return g,dict(policy=POLICY_NAME,raw_gap_m=g,effective_gap_m=g,uncertainty_m=0.,sphere=False,classified_zero=False,changed=False)
    u=F(1,2**53)
    gamma=math.nextafter(float(64*u/(1-64*u)),math.inf)
    operand_sum=sum((abs(F.from_float(float(v))) for v in [*x,*c,a,r]),F(0))
    scale=math.nextafter(float(operand_sum),math.inf)
    uncertainty=math.nextafter(gamma*scale,math.inf)
    if not math.isfinite(uncertainty) or not 0<uncertainty<=1e-10*a:
        raise ValueError('fixed sphere arithmetic domain ceiling')
    zero=abs(g)<=uncertainty;effective=0. if zero else g
    return effective,dict(policy=POLICY_NAME,raw_gap_m=g,effective_gap_m=effective,uncertainty_m=uncertainty,
        sphere=True,classified_zero=zero,changed=zero and g!=0.,operations=64,unit_roundoff=2.**-53,
        absolute_operand_scale_m=scale,maximum_band_over_body_radius=1e-10)


# Reuse the already independently qualified observational geometry/provenance
# adapter bytecode. Only its classifier namespace is different, not membership.
_gen=original_scope.scope.__wrapped__
_reference_gen=FunctionType(_gen.__code__,{**_gen.__globals__,'policy':SimpleNamespace(NAME=POLICY_NAME,classify=classify)},
                            _gen.__name__,_gen.__defaults__,_gen.__closure__)
scope=contextmanager(_reference_gen)


@contextmanager
def forbid_producer():
    old=original_scope.policy.classify
    def forbidden(*args,**kwargs):raise AssertionError('producer classifier invoked during independent reference work')
    original_scope.policy.classify=forbidden
    try:yield
    finally:original_scope.policy.classify=old
