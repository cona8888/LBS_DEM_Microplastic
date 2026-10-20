# Exact outer-iteration cycle rejection

The guard removes redundant work from an already failing fixed-point iteration. It does not accept a new contact solution, relax a residual, or diagnose a physical jam.

Within one physical-step attempt, the old velocity, background fluid velocity, body load, Stokes and lubrication matrices, mass matrix, contact Jacobian and gaps, timestep, friction, fluid properties, length scale, and tolerances are fixed. The recovery/default branch is selected before entering the outer iteration. The outer input `q_k` affects only the Reynolds-dependent drag multiplier; the resulting compliance and free velocity are passed to the selected prepared contact solver. The complete operation is therefore a map `q_(k+1) = F(q_k)` when that prepared solver is deterministic and stateless with respect to its numerical result.

The caller must explicitly attest that condition using `deterministic_stateless_cold_solver=True`. It holds for the current cold Stage53/Stage70 portfolio and compiled equivalents: reactions start cold, every SciPy root call constructs fresh solver state, branch decisions depend on the fixed inputs and physical acceptance gates, and counters/timers do not select a numerical branch. It must not be enabled for warm starts, randomized solvers, changing contact history, or methods whose work counters affect selection. Reproducibility is conditional on the same binary64 arithmetic environment.

For each candidate, the original normalized fixed-point convergence test is evaluated first. If it fails, all six binary64 components of `q_(k+1)` are compared by their bytes with previously seen map inputs. Signed zeros remain distinct. No norm-based, rounded, or approximate comparison is used.

Suppose `q_j = q_i` exactly for `j > i`. Determinism gives `F(q_j) = F(q_i)`, and induction repeats every transition from `q_i` through `q_j`. Every transition in that finite cycle has already failed the unchanged convergence test. The original iteration cannot subsequently pass that test. It would consume the remaining iteration budget and raise `inertial/contact fixed point did not converge`. The guard raises precisely that same exception immediately, retaining actual work counts, first/repeated state indices, cycle length, and inner-solve diagnostics. The existing physical timestep retry is consequently unchanged. The seen-state table is rebuilt for every physical-step attempt.

This proves failure of this particular deterministic iteration at this timestep. It does not prove absence of a solution to the contact equations, imply a unique physical contact force, or establish material entrapment.

## Verification performed

- `evidence/cycle_guard_01/results.json`: 13 checks passed. Exact manufactured cycles, opt-in/default behavior, near but unequal states, signed zero, adjacent binary64 values, original convergence before lookup, unchanged successful-step velocity/health, and actual failed-work accounting were checked.
- Captured crossing attempt 5426 was rebuilt from its physical pose, field, load, mass, and geometry. The unguarded replay reproduced all 80 archived updated velocities exactly. The guarded replay reproduced the first seven exactly, then detected the period-2 cycle. Local elapsed time was 9.705 seconds unguarded and 0.920 seconds guarded.
- `evidence/cycle_period3_01/results.json`: six checks passed. Captured attempt 5720 was independently rebuilt and cold-replayed twice. Both replays reproduced the archived seven-solve prefix exactly and reported the same period-3 cycle.

These are implementation and rejection-equivalence checks. Full trajectory and timestep-refinement qualification remain separate.
