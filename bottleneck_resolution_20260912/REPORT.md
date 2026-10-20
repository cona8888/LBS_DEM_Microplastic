# Contact-loop optimization and trajectory qualification

The previously stalled original-start crossing now completes its target in
**263.401 seconds, within the unchanged 300-second budget**. The implementation
combines arithmetic-preserving compiled loops with exact-cycle early rejection.
The completed records below are frozen. **Six of nine refinement cases completed;
three were budget-censored, so full three-packing timestep qualification remains
unestablished and the transport pilot stays deferred.**

## Finding and implemented change

Stage73's evolving packing-2 profile spent 21.205 of 21.390 seconds in contact
solving. Projected SOR accounted for 12.112 seconds, Krylov for 5.545 seconds and
the Stage53 fallback for 3.549 seconds. These are nested profile timings, not
independent quantities to add. Swept geometry cost only 0.164 seconds in that
particular contact episode.

The new implementation compiles the ordered cold PGS and SOR sweeps and calls
the same NumPy OpenBLAS DLL used by the reference. It preserves dot products,
two-row matrix-vector products and norm evaluation order. It retains the cold
zero force, contact ordering, Stage53 LM paths, Stage70 recovery order and
original Stage50 acceptance gates. No physical parameter or timestep bound was
relaxed. The driver also consolidates the already reviewed event/Re corrections
and Stage68 outer-failure retry policy, with explicit local solver injection.

Files: [compiled loop](src/compiled_blas_loop.py),
[Stage53 wrapper](src/compiled_stage53_blas.py),
[consolidated driver](src/driver_consolidated.py),
[inertial coupling](src/inertial_consolidated.py), and
[recovery portfolio](src/portfolio_explicit.py).

## Controlled local result

The same saved packing-2 mechanical state was continued for 0.002 seconds,
serially, using the same consolidated driver and physical inputs.

| Quantity | Reference | Compiled NumPy-BLAS |
|---|---:|---:|
| Trajectory runtime | 12.075699 s | 2.988390 s |
| Accepted / rejected steps | 5 / 4 | 5 / 4 |
| SOR branch time | 7.02246 s | 0.051326 s |
| Ordinary plus fallback Stage53 time | 2.10767 s | 0.027058 s |
| Krylov branch time | 2.80197 s | 2.789319 s |

This is a **4.0409× local trajectory speedup**. Startup compilation was recorded
separately as 0.5182 seconds in the paired command. The independent audit found
all nine physical attempt records identical, including all 30 inner solves,
prepared systems, forces, residuals, solver choices, timesteps, accepted states
and final physical result. It excludes timing/work metadata and added exception
diagnostics from the identity comparison. Krylov is now the dominant local cost.

Evidence: [paired result](evidence/local_blas_ab_01/results.json) and
[independent trace audit](evidence/local_blas_independent_audit_01/REVIEW.md).
This short restart resets dwell and recovery history; it does not establish
equivalence of a full original trajectory or residence time.

## Verification completed

- Final compiled source: 60 evolving-system 256-sweep traces, 12 saved-system
  25,000-sweep traces, 48 random positive-semidefinite traces and 17 manufactured
  cases matched the reference. All 30 evolving terminal acceptance/rejection
  outcomes matched; all 23 accepted velocities and full health matched exactly.
  Fourteen invalid-input checks rejected safely.
- Stage53 wrapper: all 15 comparison cases retained reference acceptance status;
  all 12 accepted candidates passed the original gates and velocity/load checks.
  Frozen half-dt systems are algebraic probes, not physical timestep refinement.
- Consolidated driver: 17 smoke, eight corrected event and 15 diagnostic checks
  passed. Full physical-step replay was identical; mutating captured snapshots
  left the manufactured trajectory unchanged. The final BLAS candidate also
  passed all 17 smoke checks.

See [kernel qualification](evidence/compiled_numpy_blas_final_01/results.json),
[input guards](evidence/compiled_numpy_blas_final_guard_01/results.json),
[Stage53 checks](evidence/blas_stage53_primitives_01/results.json),
[driver checks](evidence/driver_consolidated_02), and
[BLAS smoke checks](evidence/blas_smoke_01/smoke/results.json).

## Full-run diagnosis and exact-cycle rejection

BLAS-only acceleration reached 2.408383772 seconds against the 2.421624792-second
original-start target. It ended budget-censored after 336.044819 seconds, with
3,720 accepted steps, 1,771 clearance rejections and 230 contact retries. All
recorded physical health gates passed. This advanced beyond Stage74's
2.380623 seconds, but these different historical implementations do not form a
controlled full-run speedup comparison.

The failure-inclusive breakdown was 181.610 seconds in Krylov and 139.875 seconds
in swept geometry. Ordinary Stage53, SOR and fallback Stage53 together cost only
7.424 seconds. These branch times overlap the enclosing inertia/attempt timings.

An independent trace audit identified seven failed physical-step solves
that repeated exactly the same binary64 velocities in period-two or period-three
cycles. All first repeats occurred by iteration seven; the original method kept
iterating to 80. The recorded solver work after the first repeats totalled
95.968 seconds. This is measured redundant work, not yet a prospective speedup.

The isolated [cycle guard](src/inertial_cycle_guard.py) checks ordinary convergence
first, then rejects only an exact repeat of the complete finite velocity state.
With the fixed inputs and audited deterministic cold portfolio, the outer map
must repeat the same previously failed transitions. The guard raises the same
nonconvergence error and leaves the existing timestep-halving rule in charge.
It never accepts, averages or changes a physical state. Arbitrary injected
solvers have the guard disabled by default; the [convenience factory](src/cycle_model.py)
exposes only the audited portfolio.

The guard passed 13 checks plus six period-three replay checks. A rebuilt
80-iteration physical-step failure reproduced the archived velocities exactly;
the guard reproduced the first seven and rejected the same period-two cycle.
Its runtime fell from 9.705 to 0.920 seconds. Successful-step velocity and
health remained identical. A separate period-three case reproduced its archived
seven-solve prefix twice. All 17 smoke checks also passed with the guard enabled.
See the [proof and test records](CYCLE_GUARD_PROOF.md) and
[guarded smoke results](evidence/cycle_smoke_01/smoke/results.json).

The BLAS-only refinement batch completed packing 1 at levels 1 and 0.5, but
level 0.25 was budget-censored at 0.013124258 of 0.02 seconds, taking 122.65 seconds
under its 120-second step-boundary budget. That batch
was superseded during packing 2 and explicitly archived as partial; packing 3
was not run there. The final cycle variant requires its own three-level checks.

Evidence: [BLAS crossing](evidence/crossing_blas_01/results.json),
[exact-cycle diagnosis](evidence/crossing_cycle_diagnosis_01/REVIEW.md), and
[interrupted refinement record](evidence/refinement_blas_01/INTERRUPTED.md).

## Original-start crossing result

| Variant | Simulated endpoint | Target | Runtime | Decision |
|---|---:|---:|---:|---|
| Compiled BLAS loops | 2.408383772 s | 2.421624792 s | 336.045 s | Budget-censored |
| Compiled loops + exact-cycle guard | 2.421624792 s | 2.421624792 s | 263.401 s | Complete, within 300 s |

The guarded run accepted 3,740 steps and rejected 2,006 trials (1,771 clearance
and 235 contact rejections). Twelve exact cycles were rejected early. Startup
compilation cost 0.545 seconds separately. The complete target was reached with
contact residual at most 9.9991e-11, force residual 1.0363e-11, momentum residual
3.2018e-13, minimum gap -4.9891e-10 m (limit -5e-10 m), and sampled Re at most
0.65263. The independent audit also checked individual accepted inner and
physical-step gates.

All 5,721 attempted steps from the previous BLAS crossing match in their
physical records, including all 3,720 accepted states and its final boundary
state at 2.408383772 seconds. For the seven shortened failures, each new inner
sequence exactly matches the old prefix up to the first repeat; every omitted
old state follows the demonstrated cycle. Exactly 518 redundant outer iterations
were omitted in that common prefix. There was no first physical divergence.
The additional continuation beyond the old endpoint has its own health checks;
it has no old complete trajectory to compare against.

Evidence: [successful crossing](evidence/crossing_cycle_01/results.json),
[common-prefix identity audit](evidence/crossing_cycle_prefix_audit_01/REVIEW.md),
[crossing health audit](evidence/final_qualification_audit_01/crossing_audit.json),
and [independent guard/AST review](evidence/final_qualification_audit_01/GUARD_REVIEW.md).

The new full-run cost is now dominated by swept geometry (142.419 s) and Krylov
(106.729 s); the compiled PGS/SOR work is small. The failed old crossing and
completed new crossing have different endpoints, so their runtimes are not
presented as a controlled full-horizon speedup ratio.

## Three-level mechanical continuations

Each case starts from its saved Stage55 mechanical state, resets dwell/recovery
history, targets 0.02 seconds and has a 120-second budget. Levels 1, 0.5 and 0.25
scale displacement, relaxation, angle and maximum-step bounds together. The
mass/dt, mobility, free velocity, finite-Re iteration and geometry are rebuilt.

| Packing | Level | Simulated time (s) | Runtime (s) | Outcome |
|---|---:|---:|---:|---|
| 1 | 1 | 0.020000 | 11.045 | Complete |
| 1 | 0.5 | 0.020000 | 14.176 | Complete |
| 1 | 0.25 | 0.020000 | 108.439 | Complete |
| 2 | 1 | 0.020000 | 53.817 | Complete |
| 2 | 0.5 | 0.012872 | 121.339 | Budget-censored |
| 2 | 0.25 | 0.005053 | 120.362 | Budget-censored |
| 3 | 1 | 0.020000 | 26.480 | Complete |
| 3 | 0.5 | 0.020000 | 35.140 | Complete |
| 3 | 0.25 | 0.012697 | 120.866 | Budget-censored |

All nine cases passed the recorded physical health gates and source-stability
checks. Three exceeded their budgets at physical-step boundaries. The complete
common-horizon comparisons are:

| Packing / levels | Position change / minor radius | Orientation change (rad) | Decision |
|---|---:|---:|---|
| 1: 1 → 0.5 | 1.12953e-5 | 1.97017e-5 | Pass |
| 1: 0.5 → 0.25 | 7.95536e-6 | 1.38173e-5 | Pass |
| 3: 1 → 0.5 | 3.55510e-5 | 1.15883e-5 | Pass |

Limits are 0.01 minor radii and 0.001 radians. No convergence error is inferred
from the unequal-time endpoints of the three incomplete comparisons. The raw
harness retains those endpoint differences with `same_time=false`; the
independent audit marks them ineligible for refinement and leaves their
convergence errors null. Packing 1 passes both required comparisons. Full
three-level agreement remains unestablished for packings 2 and 3.

The failed packing-2 medium case spent 113.848 of 121.339 seconds in Krylov.
Its changing systems, rather than remaining exact repeats, dominate this cost:
screening repeated drag multipliers found only 0.3435 seconds (0.283%) of
potential reusable work. No memoization experiment or budget increase was made.

Evidence: [all nine results](evidence/refinement_cycle_01/results.json),
[independent qualification audit](evidence/final_qualification_audit_01/REVIEW.md),
and [redundancy screen](evidence/final_qualification_audit_01/MEMOIZATION_SCREEN.md).

**Decision:** retain the verified implementation improvements for bounded
numerical work; defer the full transport pilot. Follow the
[revised execution plan](NEXT_PLAN.md) for a small changing-system diagnosis and
the independent hydraulic/physical-validation work needed for the study.

## Failed approaches retained

The first compiled scalar-summation implementation was locally fast but changed
rounding and the later recovery path. Its paired trajectory slowed from 12.456
to 21.383 seconds, with four retries becoming 26. Compiling only scalar SOR
similarly slowed 12.176 to 33.998 seconds. Small endpoint differences passed the
functional tolerance but did not qualify either performance candidate. The
first run saved valid final JSON before its console summary failed to serialize
a NumPy boolean; the reporting harness was subsequently corrected.

Those raw results remain in [both-loop experiment](evidence/local_compiled_ab_01/results.json)
and [SOR-only experiment](evidence/local_compiled_sor_ab_01/results.json).
The default verification backend is now `blas`, not either scalar experiment.

## Scientific and operational limits

This is a numerical implementation improvement for the declared rigid-body,
frozen-bed, one-way-flow transport model. It preserves friction, geometry,
roughness, mass/inertia, added mass, fluid properties, gravity and finite-Re
iteration. Contact residual remains at most 1e-10, force/momentum closure at
most 1e-8, swept gap at least -1e-5 minor radii and sampled Reynolds number at
most three. Starting and endpoint/event Reynolds checks do not certify every
interior instant or physically validate the hydrodynamic closure.

The arithmetic backend is qualified for the recorded Windows, NumPy 2.3.1,
OpenBLAS 0.3.29 ILP64 installation. Numba 0.62.1 and llvmlite 0.45.1 are isolated
under this package's `deps`; system packages were not changed. JIT code with
process-specific BLAS pointers is not cached. Requalify after runtime, compiler,
architecture or relevant thread-setting changes.

Attempt traces include rejected work and unsuccessful solver branches. Some
historical failed-branch evaluation counts remain unavailable; their wall time
and attempt counts are retained. Nested timings must not be summed as exclusive
costs. Budgets are still checked at physical-step boundaries and can overshoot
during a long inner solve; they are not hard deadlines.

No unresolved run is physical retention. Contact convergence alone supports no
new claim about release, irreversible trapping, morphology populations or
evolving permeability. Fixed/mobile microplastic effects on saturated
constant- and falling-head permeability remain the study objective; hydraulic
verification and matched physical validation remain separate requirements.

Reproduction commands and runtime requirements are in [README](README.md).
