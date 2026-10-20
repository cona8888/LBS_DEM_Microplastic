# Contact-loop bottleneck contract

The Stage73 evolving seed-2 profile attributes 21.205 of 21.390 seconds to
contact solving. Stage74's scalar rewrite changed both arithmetic and later
solver paths and failed its original-start crossing. The candidate here moves
the cold projected loops to compiled float64 code, without fast-math or
parallel reductions. It does not change the physical law, cold initial force,
contact order, residual thresholds, or recovery portfolio.

Use the corrected explicit trajectory with Stage68's declared outer-failure
retry policy. The diagnostic baseline is Stage53 ordinary contact and Stage70
Krylov/SOR/Stage53 recovery. Compiled candidates are checked by the unchanged
Stage50 residual, normal-force, Coulomb-cone, closure and dissipation gates;
compiler convergence alone cannot accept a result. No historical source is
patched or overwritten. No force warm start crosses solves.

The first native scalar candidate passed local physical agreement but increased
retries from 4 to 26 and worsened runtime. It is retained as failed performance
evidence. The revised candidate calls the exact installed NumPy BLAS library
from its compiled loop, preserving row-dot, matrix-vector and norm evaluation
paths. Its runtime library and ABI are explicitly checked. No recovery order
or numerical timestep controller is changed by this revision.

The original-start BLAS crossing subsequently exposed seven exact outer-velocity
cycles, each continuing to the 80-iteration limit and then being rejected. A
second, explicitly named `cycle` variant terminates only such exact cycles
early. Within a fixed step, q_next = F(q) has fixed geometry, loads, mass,
background flow, timestep, normalization and solver selection. For the audited
deterministic cold portfolio, repeating the full finite binary64 velocity
after the unchanged convergence check has failed proves that further iteration
will repeat the same failed cycle. Raise the original nonconvergence error and
use the original timestep-halving rule; never accept or average a cycle.

This guard is off by default for arbitrary injected solvers. Its convenience
factory exposes only the audited cold portfolio. Compare full velocity bytes,
including signed zero, reset history on every attempted physical step and
recheck momentum/contact gates normally on successful steps. This establishes
failure of that numerical iteration, not absence of a physical solution.
Qualify exact-cycle and non-cycle examples, replay captured failed steps and
compare the original-start common physical prefix before using the saved time
to extend beyond the previous budget boundary. Re-run the bounded three-level
qualification for the new variant; retain the superseded partial BLAS-only
refinement batch explicitly as interrupted evidence.

The compiled loop may differ in floating-point summation despite equivalent
equations. Measure reaction and body-velocity changes and qualify complete
trajectories. Do not describe it as bitwise identical without evidence.

Verification: kernel limits and original/half-dt frozen systems (the latter
are algebraic proxies), existing manufactured/event tests, a paired 0.002 s
seed-2 mechanical continuation, the original-start seed-2 crossing through
2.42162479172013 s with the existing 300 s budget, and actual 0.02 s saved-state
continuations at three numerical levels. Scale displacement, relaxation,
angular and maximum-step bounds together; compare common simulated times.
Preserve 0.01 minor-radius position and 0.001 rad fine/medium criteria. Partial
or budget-censored runs fail completion. All unsuccessful work is retained.

Dependencies are isolated under this directory: Numba 0.62.1 and llvmlite
0.45.1, using the existing Python/NumPy/SciPy. Installation does not change
the system environment. Record cold compilation separately from warm execution
and report total command cost where available. Keep timing comparisons serial.

This is numerical bottleneck resolution for a fixed-bed, one-way, rigid-body
conditional-transport model. It supplies no new physical release, retention,
morphology or evolving-permeability validation.
