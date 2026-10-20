# Reduced fixed/mobile microplastic model

## Purpose and claim boundary

This model is a transparent mechanism and calibration-design tool. It does
not call MatDEM `pore` or `pore3d`, and its outputs are not presented as a
MatDEM pore-scale prediction or as a calibrated laboratory prediction.

## Fixed inclusions

Microplastic content `f` is presently defined as a fraction of total solid
volume. For spherical sand and microplastic particles, the specific surface
per solid volume is

```text
S0 = 6 [(1-f)/d_s + f/d_mp].
```

Intrinsic permeability is calculated with the mixed-surface
Kozeny-Carman relation

```text
k = phi^3 / [C_K S0^2 (1-phi)^2].
```

At `f = 0` and `C_K = 5`, this reduces exactly to the standard spherical-grain
form `k = d_s^2 phi^3 / [180 (1-phi)^2]`. A configurable linear porosity change
is available, but its default is zero until packing or laboratory evidence is
supplied.

## Mobile particles

For each time step, Darcy flow sets incoming microplastic mass. A filtration
coefficient determines potential capture, retained capacity limits deposition,
and a first-order rate permits detachment. The effluent mass is calculated as
incoming mass minus the actual retained-mass increment. This construction
provides an explicit control-volume mass balance.

Retained-capacity saturation `theta` changes intrinsic permeability through

```text
k_mobile / k_fixed = max(r_min, (1-theta)^n).
```

The filtration coefficient, capacity, detachment rate and clogging exponent
are calibration parameters. They are not independently identified by a single
final permeability measurement; transient flow and effluent concentration are
needed to reduce that non-uniqueness.

## Hydraulic protocols and specimen

The configured specimen is a saturated cylinder 50 mm in diameter and 20 mm
high. The same intrinsic permeability is observed through two test equations:

- constant head: `Q = K A Delta-h / L`;
- falling head: `h(t) = h0 exp[-K A t / (a L)]`.

The falling-head transient is also integrated with the mobile retention law.
Three explicit time-step refinements verify convergence against the analytical
exponential limit. The current 10 mm standpipe, 100-to-20 mm head interval and
constant-head gradient of 1.0 are labelled apparatus placeholders.

## Verification evidence

The active 50 mm by 20 mm Leighton Buzzard Fraction B case passed the
following checks on 2026-07-19:

- literature inputs: D10 = 0.65 mm, D50 = 0.82 mm, Cu = 1.38,
  emin = 0.46 and emax = 0.79;
- selected Dr = 50% scenario: e = 0.625 and porosity = 0.384615;
- clean plus 1% fixed-plastic solid-volume cases;
- clean-sand Kozeny-Carman relative error: `1.84e-16`;
- clean hydraulic conductivity: `5.48293e-3 m/s`;
- 1% fixed-plastic hydraulic conductivity: `5.23574e-3 m/s`;
- fixed-plastic permeability ratio: `0.954917`, a 4.51% decrease;
- maximum constant-head mobile mass-balance relative error: `3.30e-16`;
- maximum falling-head mobile mass-balance relative error: `1.71e-15`;
- constant- and falling-head permeability recovery errors below `2.0e-16`;
- falling-head finest-step normalized analytical error: `0.004647`;
- nine MATLAB unit tests passed with zero failures or incomplete tests.

At the refined falling-head mobile step (`Delta-t/tau = 0.001`), every mobile
case takes longer to reach terminal head than its fixed-bed counterpart. This
checks the expected direction of the clogging effect.

The default mobile parameters produce strong clogging in the one-hour
constant-gradient toy (final ratios about 0.125 to 0.130). The much shorter
falling-head test produces a final ratio near 0.9988. Both magnitudes are toy
responses and must not be used as physical conclusions before calibration and
held-out validation.

## Escalation to MatDEM

The standalone MatDEM distribution contains the reference workflow
`user_L3PorePermeability1/2/3.m` and a `user_PoreAdsorption1/2/3.m` example.
The former supplies the specimen, pressure-boundary and steady-flow pattern;
the latter supplies a transport/retention precedent. A research-grade MatDEM
study should adapt those workflows after the specimen geometry, test protocol,
mixture definition and measured targets are fixed.
