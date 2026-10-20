"""Explicitly revised sphere-only numerical gap classification.

This is a fixed conservative arithmetic-scale policy, not a global proof of
floating-point error for every geometry. It must be independently qualified.
The original primitive's normal, lever, gap and source are never modified.
Only an exactly spherical body's effective normal-gap operand may change.
"""
import math
import numpy as np

NAME = 'stage212_binary64_sphere_gap_band_v1'
OPERATIONS = 64
UNIT_ROUNDOFF = 2.0 ** -53
MAX_BAND_OVER_BODY_RADIUS = 1e-10


def classify(x, c, a, b, r, raw_gap):
    x, c = np.asarray(x, dtype=float), np.asarray(c, dtype=float)
    if x.shape != (3,) or c.shape != (3,) or not np.isfinite(x).all() or not np.isfinite(c).all():
        raise ValueError('finite three-dimensional stored centres required')
    a, b, r, raw_gap = map(float, (a, b, r, raw_gap))
    if not all(math.isfinite(v) for v in (a, b, r, raw_gap)) or min(a, b, r) <= 0:
        raise ValueError('finite positive radii and finite raw gap required')
    if a != b:
        return raw_gap, dict(policy=NAME, raw_gap_m=raw_gap, effective_gap_m=raw_gap,
                             uncertainty_m=0.0, sphere=False, classified_zero=False, changed=False)
    # gamma64 and a sum of absolute operands are chosen before seeing outcomes.
    # Outward rounding prevents the implemented band falling below this formula.
    gamma = math.nextafter(OPERATIONS * UNIT_ROUNDOFF / (1.0 - OPERATIONS * UNIT_ROUNDOFF), math.inf)
    scale = math.nextafter(math.fsum([*map(abs, x), *map(abs, c), a, r]), math.inf)
    band = math.nextafter(gamma * scale, math.inf)
    if not math.isfinite(band) or band <= 0 or band > MAX_BAND_OVER_BODY_RADIUS * a:
        raise ValueError('sphere arithmetic band outside frozen relative-radius ceiling')
    zero = abs(raw_gap) <= band
    effective = 0.0 if zero else raw_gap
    return effective, dict(policy=NAME, raw_gap_m=raw_gap, effective_gap_m=effective,
                          uncertainty_m=band, sphere=True, classified_zero=zero,
                          changed=zero and raw_gap != 0.0, operations=OPERATIONS,
                          unit_roundoff=UNIT_ROUNDOFF, absolute_operand_scale_m=scale,
                          maximum_band_over_body_radius=MAX_BAND_OVER_BODY_RADIUS)
