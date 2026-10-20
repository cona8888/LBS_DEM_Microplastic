# Revised execution plan after bottleneck resolution

The original packing-2 crossing now reaches 2.421624792 seconds in 263.401 seconds
under its original 300-second budget. The audited common physical prefix is
unchanged. Use the compiled NumPy-BLAS loops and exact-cycle rejection as the
maintained diagnostic implementation for this qualified runtime.

**Keep the six-case transport pilot and population campaign deferred.** Packing
2's medium and fine continuations and packing 3's fine continuation remain
budget-censored at the declared 120 seconds per case. Six of nine cases completed
the 0.02-second target; only packing 1 completed and passed both successive
refinement comparisons. Full timestep agreement has not been established.
A completed crossing and exact implementation optimization do not
replace numerical convergence or physical validation.

## Numerical work

1. Preserve the completed crossing, all refinement outcomes, failed experiments,
   source/input/runtime bindings and independent audits. Use the final
   [report](REPORT.md) as the outcome ledger. Do not infer retention from a
   numerical failure or a budget-censored trajectory.
2. Restrict the next numerical investigation to changing contact systems from
   the failed refined episodes, starting with packing 2. Capture one representative accepted
   and one rejected Krylov solve, with the complete physical-step/prepared
   inputs, failed residual/Jacobian-vector evaluation counts, active-contact
   geometry, body velocity and resultant force/torque. Separate outer coupling
   failure, inner contact failure and geometric step rejection. Inspect scaled
   conditioning and residual components before proposing a formulation change.
3. Keep exact-cycle rejection enabled only for the audited deterministic cold
   portfolio. Do not average cycles, loosen tolerances, reorder solvers, change
   material parameters or introduce reaction warm starts to obtain a pass.
   Screening repeated drag coefficients found only 0.283% potentially reusable
   solver time in the failed medium case; do not add a memoization experiment.
4. Any future contact-formulation change needs original physical gates, a
   controlled replay and three-level, common-horizon qualification across all
   packings. Frozen half-dt algebraic systems remain unit probes. Rebuild mass/dt,
   drag, mobility, free velocity and contact geometry for actual refinement.
   Keep position changes at most 0.01 minor radii and orientation changes at
   most 0.001 radians for the declared comparisons. Unequal-time endpoints
   provide no timestep-convergence result.
5. Preserve the 300-second short-crossing and 120-second local-check records as
   executed. A future budget revision must be prospective and symmetric; it
   cannot relabel these failures. Add internal deadline propagation before a
   longer campaign, returning the last accepted state without accepting an
   unconverged inner solve. Current budgets are checked at physical-step
   boundaries and can overshoot.

The next transport promotion requires robust refined continuations for every
packing, original-start crossing checks for the other packings, and event/time
verification appropriate to the eventual observable. The current 0.02-second
checks reset dwell and recovery history; they do not establish full-history
residence statistics or convergence throughout the entire crossing. Only after
those gates consider the existing six-case 0.1-PV feasibility pilot with its
original 1,800-second per-case budgets and complete outcome ledger. Do not
expand solver caps or population starts while the present gate remains open.

## Keep the hydraulic study moving independently

The study objective remains the effect of fixed and mobile microplastics on
saturated sand permeability under constant- and falling-head tests. Conditional
passage and finite contact dwell support that objective; they do not replace it.

- Recompute and bind the existing fixed-solid conductivity contrasts and their
  uncertainty. Preserve three independent packings and two placement contexts;
  six contexts are not six independent specimens. Retain the low-dose numerical
  trend and keep the unpromoted fragmentation/CPD6 expansion inactive.
- Map each branch's geometry, void-ratio definition, polymer dose basis, axes,
  fluid scaling and boundaries. Keep the original 50 × 20 mm, e=0.625 target,
  the fixed DEM/LBM scenarios and the proposed Stage33D e=0.744 PET experiment
  distinct. Design and synthetic data are not measured validation. The external
  clean-K comparison concerns its own e=0.744 scenario.
- Pass a frozen accepted conductivity through the existing constant-/falling-
  head protocol equations. Verify SI units, k↔K conversion, recovered discharge
  and conductivity, storage balance and constant-K exponential head decay.
  Label this protocol verification using prescribed constant permeability.
- Audit existing pressure-gradient scaling first. If absent, the smallest new
  hydraulic sentinel is one clean and one obstructed accepted fixed geometry at
  three gradients with established flow-convergence and balance gates. Prepare
  matched calibration and held-out validation conditions independently.

See the preserved [Stage72 hydraulic scope](../CURRENT_PLAN.md) and
[fixed-solid synthesis](../stage35_outputs/stage35a_publication_evidence_synthesis_20260904/release_03/MANUSCRIPT_RESULTS.md).

## Physical-adequacy gate for mobile predictions

Use a small matched AR4 free/near-wall/throat pose set to test translational and
angular velocity and flow obstruction against an independent hydrodynamic
calculation. Reserve held-out poses. Existing AR2 force/torque-free Stokes
checks do not validate the present gravity-bearing, finite-Re AR4 trajectories.
Assess finite-body flow sampling, tangential/rotational wall resistance,
rigidity, settling/inertia and the one-way frozen-flow approximation.

Retain contact residual ≤1e-10, force/momentum closure ≤1e-8, swept gap ≥−1e-5b
and sampled Re ≤3. Exact geometry, friction, roughness, density, mass/inertia,
added mass, fluid properties and gravity remain fixed. Endpoint/event Re checks
do not certify every interior instant. Define physical inventory and
mobilization/remobilization before claiming release; verify hydraulic feedback
before claiming evolving permeability. No parameter is fitted to conceal a
numerical failure.
