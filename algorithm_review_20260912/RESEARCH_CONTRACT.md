# Review and optimization of the Stage 66 state

## Research question and scope

Can improved scaling and derivatives reduce the cost of solving the same
three-dimensional unilateral Coulomb contact problem without modifying the
particle geometry, physical parameters, near-wall model, or acceptance gates?
The immediate deliverable is verified implementation and bounded recovery
evidence, not a release-fraction or permeability campaign.

The broader questions remain fixed-fibre effects on sand permeability and the
conditional passage/residence of initially mobile microplastics. A periodic,
fixed-sand, one-way-flow trajectory does not represent total soil-column release
or evolving permeability. The separate empirical and coupling requirements
identified in Stage 41 still apply.

## Preserved assumptions

- Rigid prolate/sphere geometry, dimensions, volume and density; frozen periodic
  sand and archived CPD2 steady velocity fields; identical initial states.
- Finite-Re correction to anisotropic Stokes drag, declared added mass,
  quasi-steady rotation, normal-only regularized lubrication and buoyant weight.
- Original signed gaps, contact order, force and torque scaling and Coulomb
  coefficient. No gap clipping, adhesion, softening, artificial damping or
  tolerance relaxation. No reaction persistence between physical solves.
- Stage 53 remains the default path. A recovery algorithm is considered only
  after an explicit contact-solver rejection followed by timestep reduction.
  Solver recovery state is local to a trajectory, never a mutable global binding.
- Nonabsorbing finite contact dwell and separate failure/budget/domain censoring.

## Acceptance before integration

1. Derivative checks at smooth sliding/sticking/separated states and declared
   treatment of nonsmooth boundaries; unit-rescaling checks where feasible.
2. All three immutable captured systems, distinguishing the original system
   from the frozen-coefficient half-step proxy. A proxy halves the gap/dt term
   only; true step recovery must rebuild inertia, compliance, free velocity,
   active contacts and finite-Re iteration consistently.
3. Complementarity/projection residual <= 1e-10, nonnegative normal forces,
   Coulomb-cone allowance 1e-12 times total reaction magnitude, force closure
   <= 1e-8 and non-generative friction under the existing relative scale.
   Finite state is mandatory. Optimizer success alone never accepts a solution.
4. Default-path manufactured trajectories remain identical to Stage 53 where
   recovery is unused; the frozen 17-gate event/physics suite passes.
5. Actual saved-state continuation and the short packing-3 crossing use the
   complete inertial/contact solve, exact swept geometry and original bounds.
   Position/orientation agreement across numerical refinements uses the existing
   0.01 minor-radius and 0.001-rad limits. Failure remains visible.

## Performance and inference

Time complete solves and trajectories, including unsuccessful attempts; do not
claim campaign speed from fixed-system equation evaluations. Use immutable new
output directories, record source/input hashes, resolved configuration and
versions. Keep previous stages unchanged. A new solution of a nonunique Coulomb
problem is not automatically trajectory-equivalent: benchmark solver-selection
and refinement sensitivity before using morphology contrasts. Recovery speed
must be judged alongside independent near-wall hydrodynamic adequacy, which this
work does not establish.

## Separate optional prefix experiment

The recovery-only candidate remains the contract above. A second, explicitly
experimental candidate preserves the first 200 cold-PGS sweeps exactly, then
tries the same-equation analytic solver for one to three contacts and retains
Stage 53 as fallback. The cap of 200 is a computational choice, not a material
parameter. This candidate can change the selected root on hard calls that the
original default eventually accepts; it is not covered by the default-path
identity guarantee. Keep its evidence and promotion decision separate. A
passing coarse crossing establishes feasibility at that setting only. Matched
time refinement, cross-packing robustness and physical qualification are still
required before study use.
