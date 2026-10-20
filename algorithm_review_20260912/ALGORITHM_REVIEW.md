# Algorithm review and optimization, 12 September 2026

Reviewed the accumulated work through Stage 66 and implemented new, isolated
candidates. **The exact field optimization and the event/applicability fixes
pass bounded verification. The accelerated contact solver remains experimental
because trajectory refinement and cost qualification fail.** Stage 55 is still
unpromoted. Historical source and evidence files were preserved.

## Changes and decision

| Change | Evidence | Decision |
|---|---|---|
| Allocation-free gradient products and reused trilinear stencil indices in `wall_field_exact_v1.py` | 3,480 identical samples; independent polynomial check; six paired matrix trajectories with identical samples, trial states and health | Suitable implementation optimization for the existing field model |
| Earliest whole-body exit in `exit_event_v1.py` | Detects rotating exit-and-return missed by endpoint signs; eight event/applicability checks and 240 independent analytical cases pass | Use corrected detector in the new path; old affected exit results need rechecking |
| Actual endpoint and fractional-exit fluid samples in `trajectory_explicit_v1.py` | Separate manufactured terminal and outlet Reynolds violations correctly return `unresolved_model` | Corrects applicability screening without changing frozen-force integration |
| Explicit solver dependency in `inertial_explicit_v1.py` | Per-trajectory selection; frozen 17-check smoke suite passes for both candidate policies | Removes mutable global solver rebinding from the new execution path |
| Dimensionless force variables and analytic contact Jacobian | 60 derivative comparisons, 17 manufactured contact systems, all six captured systems and 12 unit-scaling checks pass | Verified local solver; recovery trajectory qualification incomplete |
| Optional 200-sweep PGS prefix, then analytic solver and Stage 53 fallback | Ordinary calls preserve original results; one difficult packing-3 crossing completes within its budget | Useful experimental branch; do not promote to the study default |

The field microbenchmark measured a **1.94×** median sampler speedup. Local
half-dt algebraic probes took 0.00147–0.00666 s with the new solver versus
0.274–0.492 s with Stage 53. Neither measurement is a campaign speedup.

The optional prefix candidate completed the original packing-3 start through
**1.376620538 s**, crossing the former failure at 1.326620538 s, in **135.28 s**
under a 300 s step-boundary budget. It passed clearance, contact, force,
momentum and Reynolds checks. The previous Stage 65 application reached only
1.34947 s in 304.4 s. These are different accepted algorithms under different
host loads, so the comparison establishes a bounded completion improvement,
not a controlled speed multiplier or identical trajectory.

## Assumptions and physical equations

The changes retain rigid prolate/sphere geometry, size, mass and density;
signed contact gaps; unilateral normal contact; the original Coulomb disk
projection; friction coefficient; drag, lubrication and reduced inertia
closures; periodic geometry and frozen flow; and the declared timestep bounds.
There is no gap clipping, added damping, contact softening, friction change,
reaction carry-over or tolerance relaxation. The local residual threshold is
1e-10, normal forces remain nonnegative, the original relative cone allowance
is retained, closure is checked at 1e-8, and friction cannot generate power
beyond the existing roundoff allowance. Optimizer success alone never accepts
a contact result.

The new variables scale force by contact mobility and free-velocity magnitude.
The analytic normal and tangential derivatives remove poorly scaled numerical
differencing. Exact inactive-force subsets retain every original contact
residual equation. This preserves the zero set of the discrete equations;
it does **not** prove uniqueness or preserve which admissible frictional root
is selected. The optional prefix can change selection on a call that Stage 53
would eventually solve. The default explicit trajectory still uses Stage 53.
See [the contract](RESEARCH_CONTRACT.md) and
[contact derivation](evidence/CONTACT_ALGORITHM_REVIEW.md).

## Trajectory qualification

The complete continuation ledger is in
[saved continuation results](evidence/saved_continuation_01/results.json) and
[optional-prefix refinement results](evidence/saved_prefix_refinement_01/results.json).
These tests rebuild mobility, free velocity, finite-Re iteration and contact
queries at every physical retry. Earlier Stage 56/66 half-dt files change only
the gap/dt term with frozen coefficients; they are algebraic probes, not actual
smaller-step dynamics.

The recovery-only candidate completed the coarse 0.02 s continuation for
all three packings, but the finer packing-1 continuations exhausted their 120 s
budgets before the common horizon. Packing 2's medium setting completed;
its fine setting did not. The optional-prefix saved packing-3 continuation
also exhausted its smaller 60 s budget at all three settings.
Packing 3's recovery-only medium and fine settings stopped at 0.002878096 s
and 0.002228600 s with `inertial/contact fixed point did not converge`. Solving each contact root is
therefore insufficient: convergence of the outer finite-Re/contact coupling
must also be diagnosed and qualified.
Accepted-state health remains separate from these completion failures.
Failed or unequal-time runs do not establish coordinate convergence.

| Recovery-only packing | Coarse, 0.1 | Medium, 0.05 | Fine, 0.025 |
|---|---|---|---|
| 1 | Complete, 0.020000 s | Budget, 0.017106 s | Budget, 0.003946 s |
| 2 | Complete, 0.020000 s | Complete, 0.020000 s | Budget, 0.006667 s |
| 3 | Complete, 0.020000 s | Outer iteration failure, 0.002878 s | Outer iteration failure, 0.002229 s |

All nine recovery-only runs and all three optional-prefix continuation runs
passed accepted-state health checks; none of the three-packing refinement
gates passed. The tabulated times are simulated continuation time, not runtime.

The tested controls refine displacement and relaxation bounds together by
factors of two. Angular-step, maximum-step and flow-resolution sensitivity
remain additional requirements. Saved-state tests restart the dwell monitor;
they test mechanical continuation, not residence statistics. Source hashes
and failures are retained, including unsuccessful development fixtures.

## What is scientifically defensible

The current model can support investigation of **conditional passage and
finite contact dwell of an initially mobile rigid particle in the specified
fixed periodic sand and flow**, after numerical and physical qualification.
It does not yet support quantitative soil-column release, irreversible
retention, a sphere-versus-fibre population effect, or evolving permeability.

The main physical gaps are near-wall tangential/rotational resistance,
finite-body versus centre-sampled flow, shear and rotational inertia,
independent friction/roughness calibration, and system boundaries. Gravity is
transverse to the x observation outlet, and the flow is fixed. Full release
requires a resident population and mobilization/detachment design; evolving
permeability requires hydraulic feedback. A separate fixed-fibre permeability
study needs its own matrix preparation, hydraulic solve and validation.
These changes preserve the current assumptions without claiming that those
assumptions have been validated for every study purpose.

Numerical failures and runtime censoring must stay separate from physical
retention. The Stage 55 pattern—all three fibre cases numerically failing,
with unequal sphere completion—precludes a morphology inference. A converged
residual is not temporal convergence, and a categorical pilot pass is not a
coordinate-accuracy pass. The detailed
[scientific review](SCIENTIFIC_REVIEW.md) gives ranked findings, archived
evidence and primary literature.

## Next decision

Use the exact field wrapper and corrected explicit Stage 53 path for further
bounded verification. Keep both analytic contact policies experimental.
Capture the full states and outer finite-Re iteration at repeated analytic
rejections, compare admissible body velocities and resultant reactions, then qualify a recovery-active
matched-time trajectory at three numerical levels. Do not increase budgets
or relax tolerances to turn the present qualification failures into a pass.
Repeat the paired pilot only after robust completion and accuracy, then
qualify the physical closures and sampling design before population claims.

[Usage and reproduction](README.md),
[field verification](FIELD_REVIEW.md),
[independent event review](evidence/independent_event_review_01/REVIEW.md),
and [evidence manifest](evidence/REVIEW_MANIFEST.json) provide the implementation
and audit trail. The manifest includes the final source hashes and identifies
the superseded event fixtures.
