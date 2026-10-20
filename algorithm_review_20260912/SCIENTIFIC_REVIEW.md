# Scientific and numerical review through Stage 66

Reviewed 12 September 2026. This review reads the archived Stage 41–66 code and evidence and performs one inexpensive event-function counterexample. It does not rerun a physical trajectory, certify unexecuted changes, or provide experimental validation. Earlier source and result files are preserved.

The accumulated work supports continued development of a rigid-body conditional transport mechanism model. The replicated morphology pilot remains unqualified. Faster contact resolution must preserve the discrete physical equations and be qualified separately from the hydrodynamic model, the event definitions, and the eventual population inference.

## What the existing evidence actually establishes

| Evidence | Defensible conclusion | Remaining limit |
|---|---|---|
| [Stage 41 optimization](../stage41_evaluations/ALGORITHM_REVIEW.md) | Exact-geometry and cold-contact implementation accelerated the measured historical path by 1.78 times with identical saved trajectories | That timing is not the speed of subsequent fallback algorithms or a seven-PV campaign |
| [Stage 42–46 status](../stage46_evaluations/STAGE42_TO_46_STATUS_20260912.md) | Increased cold-PGS ceiling recovered the short extra-fine replay; gap-remapping variants failed and were rejected | A short replay does not qualify longer contact transitions |
| [Stage 47 feasibility](../stage47_evaluations/saved_multicontact_feasibility_01/results.json), [Stage 49 direct-solver diagnostic](../stage49_evaluations/direct_contact_seed_diagnostic_01/results.json) | Normal feasibility and a successful same-equation frictional solution refute treating that particular failed iteration as a demonstrated jam | The condition number alone does not identify the cause, and feasibility is state-specific |
| [Stage 50 refinement](../stage50_evaluations/matrix_refinement_01/results.json) | The short extra-fine path matches Stage 42; fine-to-extra-fine shifts are 0.001564 minor radii and 0.00072685 rad | The fallback was invoked zero times, so this test does not verify fallback branch selection |
| [Stage 53 manufactured and saved states](../stage53_evaluations/trajectory_verification_01/results.json), [Stage 54 pilot](../stage54_evaluations/stitched_release_pilot_01/REPORT.md) | Direct residual recovery can finish the selected one-start 0.1-PV categorical pilot | The long-pilot coordinate shifts remain larger than the earlier trajectory-accuracy thresholds |
| [Stage 55 paired pilot](../stage55_evaluations/paired_three_packing_pilot_01/REPORT.md) | All six cases are accounted for; two spheres complete, one is budget-censored, all three prolates fail numerically | No morphology, retention, or release-fraction inference is available |
| [Stage 65 application](../stage65_evaluations/hybrid_fallback_application_01/results.json) | The no-recovery sphere path remains identical and the fibre maintains accepted-state health | Fibre reaches only 1.34947 s in 304.4 s; the application/cost check fails |
| [Stage 66 root probes](../stage66_evaluations/nonsmooth_roots_01/results.json) | Different nonlinear methods find admissible roots for three modified frozen algebraic systems | No single universally successful method, true half-step reconstruction, trajectory refinement, or population result is established |

The [Stage 66 decision](../stage66_evaluations/NEXT_DECISION.md) correctly keeps Stage 55 unpromoted. Its proposed recovery portfolio is an experiment to qualify, not an already accepted replacement.

## Ranked findings

### 1. P1 — The so-called half-step local probes do not rebuild half-step dynamics

[Stage 56](../stage56_staging/probe_contact_timestep_recovery_v1.py) and [Stage 66](../stage66_staging/probe_nonsmooth_root_methods_v1.py) change the saved `dt` while retaining `vfree`, `mobility`, and the saved contact set. This changes the position-stabilization term `gap/dt` in the complementarity equations. It is a useful algebraic sensitivity probe, but it is not the actual smaller time-step physical system.

The [inertial step](../stage41_staging/inertial_contact_cold_optimized_v1.py) computes

`B(dt) = inverse(M/dt + D(Re) + L)`

`q_free(dt) = B(dt) [M q_old/dt + D(Re) q_background + body_load]`.

Both depend on `dt`, and the finite-Re iteration updates the translational drag. A real retry also recomputes the predictive contact set using the smaller reach. Consequently, the recorded 944/3,899/170 evaluations and local pass outcomes cannot be promoted as consistent half-step solver or runtime evidence. The adaptive application trajectories rebuild the full step and provide separate evidence; their failures remain material.

**Required evidence:** capture the full pre-step pose, velocity, field/background, mass, drag, lubrication inputs and contact-query parameters. Rebuild all dependent quantities for each refinement, or extract a fresh rejected local system from the actual retry. Label the existing files as frozen-mobility gap-term probes in new summaries; preserve their raw contents.

### 2. P1 — A valid Coulomb residual is necessary, but does not guarantee unchanged solution selection

The [Stage 50](../stage50_staging/inertial_contact_seeded_lm_v1.py) and [Stage 53](../stage53_staging/inertial_contact_multistart_lm_v1.py) LM methods target the same normal-complementarity and tangential disk-projection equations as the cold PGS solver. At an accepted root, the normal force is nonnegative, the normal corrected velocity is nonnegative/complementary within tolerance, and the tangential force obeys the Coulomb maximum-dissipation relation within tolerance. Using LM as a root finder is therefore a potentially sound numerical change. It does not add material compliance, damping or a new friction coefficient.

An LM success flag or low least-squares gradient is insufficient: a nonsmooth least-squares problem can terminate at a nonzero residual. Keeping the original residual, cone, force-closure and frictional-work acceptance checks is essential. Their thresholds must not be relaxed to improve timing.

There is no general uniqueness certificate here. With three contacts, `J` is 9 by 6, so `A = J B J.T` has rank at most 6 even when `B` is positive definite. A condition number of approximately 2.23e17 is therefore compatible with expected redundant force coordinates. It does not, by itself, prove physical infeasibility, explain PGS failure, or prove that the body's generalized velocity is nonunique. Contact reactions may differ in the null space while their resultant and body velocity agree. Conversely, frictional root changes can sometimes affect body motion; that must be measured.

The original Stage 41 contract explicitly sought unchanged cold-solver selection. New solvers first used only after authoritative rejection preserve successful earlier paths by construction, but make no same-root promise on rejected paths. The zero-seeded and PGS-seeded recoveries are deterministic initializations within the current solve, not reaction-history transfer between physical steps. Document this distinction.

**Required evidence:** compare successful methods on the same freshly reconstructed system. Record generalized velocity, resultant force/torque, individual reactions, active/stick/slip states and short continuation. Check both recovery-needed and recovery-free cases. If distinct admissible velocities exceed the frozen numerical tolerance, classify solution-selection uncertainty; do not conceal it under identical residual scores. Root residuals certify equations at a fixed step, not uniqueness or temporal accuracy. The [Acary et al. formulation](https://doi.org/10.1002/zamm.201000073) explicitly couples conic subproblems with an additional fixed point and discusses existence assumptions; it does not supply a blanket uniqueness guarantee for these data.

### 3. P1 — A plain convex cone optimizer can silently change the physical friction law

Replacing the current normal complementarity plus tangential disk projection by minimization of `0.5 f.T A f + z.T f` over the entire Coulomb cone generally imposes an associated cone law. The original sliding contact permits zero normal velocity with nonzero tangential slip. The associated dual-cone condition can instead introduce artificial normal separation during sliding. This directly affects pore escape and cannot be sold as a solver-only optimization. This artifact is explicitly described in [Tasora et al., 2021](https://doi.org/10.1002/nme.6693).

An exact cone reformulation is possible with the appropriate non-associated coupling, such as the modified normal velocity and outer fixed-point treatment in [Acary et al.](https://doi.org/10.1002/zamm.201000073). An SOCP subproblem is not automatically equivalent to the full discrete Coulomb law. The current Fischer–Burmeister normal equation plus tangential projection avoids that particular model substitution if its original gates pass.

**Required evidence:** an analytical inclined/contact sliding test showing the same normal force, zero separation during sustained slip, and the same frictional dissipation as the declared law; then small multi-contact and real-state tests. A new regularized or compliant contact model could be scientifically justified separately, but would require its own parameters, convergence and calibration evidence.

### 4. P1 — The whole-body exit primitive misses an exit and return within a step

[The exit primitive](../stage37_staging/transport_contact.py) returns `None` whenever the end-of-step exit function is negative. For a rotating prolate, the support function is not monotone over an otherwise constant-motion step. The body can become wholly downstream and return before the endpoint. This is a first-passage counting error, including within the current 0.02-rad angle bound.

The following direct primitive counterexample was executed during this review (no trajectory or physical dataset was changed):

```python
import sys
import numpy as np
sys.path.insert(0, 'stage37_staging')
import transport_contact as m
a, b, dt, outlet = 2e-4, 5e-5, 1.0, 0.001
p = np.array([np.sin(0.01), np.cos(0.01), 0.0])
x = np.array([outlet + (b + m.support([1, 0, 0], p, a, b))/2, 0, 0])
q = np.array([0, 0, 0, 0, 0, a*0.02])
```

The exit function is -1.87423495e-8 m initially and finally, but +1.87423495e-8 m halfway through the interval. `linear_pose_exit_time(x,p,q,a,b,outlet,dt)` returns `None`. The same angular path can be rescaled to a smaller `dt`; its existence does not depend on allowing a one-second production step.

**Required evidence:** isolate extrema or use a certified bounded first-crossing search for the support motion, then test transient crossings, near tangencies, monotone translation, and a sphere limit. A dense sample is useful for checking an implementation but is not itself a proof that every narrow crossing is found. Earlier raw results remain conditional on the old detector until affected exit cases are checked.

### 5. P2 — The terminal Reynolds check uses the old fluid position

[Stage 64's trajectory](../stage64_staging/trajectory_hybrid_recovery_v1.py), inherited by Stage 65, computes `endpoint_reynolds` using `candidate[:3] - background[:3]`, but `background` was sampled at the initial pose. It then allows `full_window_exit` or `present_at_horizon` without sampling flow at the terminal position. The next loop catches the new local slip only for nonterminal steps. A spatially varying field can therefore yield an accepted terminal classification even when the actual terminal local slip exceeds the declared Re envelope.

**Required evidence:** sample the endpoint, or actual fractional exit position, for the applicability check; keep this separate from the frozen-force time integrator unless deliberately changing that discretization. Use a manufactured spatially varying field to exercise final-time and exit-time limits. This is a screening check: passing Re <= 3 still does not validate the drag closure.

### 6. P1 for study promotion — Categorical agreement does not establish trajectory convergence

The Stage 43 design froze a categorical feasibility gate before the pilot; Stage 54 applies that declared gate and discloses the coordinate differences. Its narrow categorical pass is legitimate. It must not be described as passing the original full trajectory-accuracy criteria: the coarse-to-medium shift is 0.0394775 minor radii and 0.0103363 rad, compared with Stage 41 limits of 0.01 and 0.001. Only two long-pilot levels were compared, and both remaining in the window is a weak discriminator when neither is close to a passage event.

The Stage 50 extra-fine short replay is useful independent evidence but invokes no LM fallback. The Stage 64/65 unchanged sphere path is also useful but does not verify the fibre recovery corridor. Stage 63's failed frictional manufactured trajectories show why primitive speedups cannot replace this evidence.

**Required evidence:** retain separate fields for evidence integrity, feasibility, equation residual, trajectory accuracy, event accuracy, cost and physical validation. Use three consistent time-step levels on recovery-active cases; compare exit/dwell times and at least short-term positions/orientations around contact changes. If the claimed scientific effect is comparable to the remaining numerical shift, no morphology inference is permitted. Do not retrospectively widen a tolerance until a run passes.

### 7. P1 for physical interpretation — The hydrodynamic and system-boundary assumptions remain unqualified

The preserved model contains exact rigid prolate geometry, physical PET density, one-way forcing from frozen clean-sand flow, an anisotropic Stokes tensor with scalar finite-Re correction, translational inertia, quasi-steady rotation, and regularized normal lubrication. Preserving these assumptions is necessary for comparing algorithms. It does not establish that each assumption is sufficient for the eventual study.

Normal lubrication alone does not supply tangential or rotational wall resistance, which affect rolling, sliding and escape. [Goldman, Cox and Brenner](https://doi.org/10.1016/0009-2509(67)80047-2) and [Cooley and O'Neill](https://doi.org/10.1093/imamat/4.2.163) treat translation/rotation near a wall as distinct hydrodynamic problems. They are sphere references and do not validate a multi-grain prolate closure. The resolved-flow collision study of [Costa et al.](https://arxiv.org/abs/1506.01880) demonstrates targeted lubrication/contact benchmark design, not validation of the present reduced model.

The fluid is sampled at the body centre with a local gradient although the 400-micrometre prolate spans about eight archived flow cells in the packing-2 case. Its one-point Jeffery background assumes locally linear flow; finite-body variation, wall proximity and flow-gradient discretization need their own bounds. Weak shear inertia can alter orientation even at small Reynolds number, as shown by [Einarsson et al.](https://arxiv.org/abs/1504.02849). Check rotational response and shear Reynolds number separately from translational slip Re. The existing added-mass tensor without general ambient-acceleration/history terms remains a declared reduced inertia model, not a complete unsteady hydrodynamic equation.

The outlet is an x observation plane in a periodic geometry/flow, while gravity is in -z. A periodic conditional passage statistic does not equal recovery from a vertical soil column. A frozen clean-sand flow also cannot predict time-dependent permeability loss as mobile bodies obstruct pore space.

**Required evidence:** near-grain normal/sliding/rotating benchmarks, finite-body and flow-resolution sensitivity, and independently justified friction/roughness and rigidity ranges. For column release, define physical boundaries, gravity alignment, an initially resident population, mobilization/detachment and sampling weights. For migration-induced permeability, recompute flow or qualify a two-way hydraulic closure. Keep these as separate research rungs; changing friction, roughness, shape dimensions or gravity solely to improve solver speed changes the study.

### 8. P1 for inference — Unequal failure and runtime censoring prevent a morphology conclusion

Stage 55 is a three-start feasibility design with one selected start per packing, not a sample from a defined resident-particle population. Selecting the start nearest mean clearance does not make it representative of a nonlinear passage probability. All three prolate failures and one sphere budget-censoring event remain unresolved outcomes; they cannot be pooled with retention or excluded from the denominator.

**Required evidence:** first complete the paired feasibility cases under symmetric accuracy and resource rules. Then freeze a probabilistic population/start design, paired shape comparisons, packing replication, horizon and outcome ledger. Keep whole-window first passage, present with finite dwell, present without dwell, applicability censoring, numerical failure and budget censoring distinct. Quantify uncertainty and whether missingness depends on morphology/contact state. A 0.1-PV successful pilot does not qualify a seven-PV population claim.

## Recommended next bounded decision

1. Correct the two event/applicability defects in a new version and verify their small counterexamples.
2. Implement deterministic same-equation contact acceleration behind the accepted default, with finite-candidate and original residual/cone/closure/dissipation gates. Prefer eliminating repeated algebra and interpreted-loop overhead where it preserves operation order; a recovery portfolio remains subject to branch and timestep checks.
3. Benchmark reconstructed fixed systems, then one short recovery-active crossing at three numerical levels. Record all attempts and evaluation counts as well as wall time. A solver that rapidly finds an inadmissible root has not accelerated the accepted algorithm.
4. Repeat the six-case feasibility pilot only after that bounded accuracy/cost evidence passes. Preserve failures as development evidence and make no population or morphology claim at this stage.
5. Qualify the physical assumptions and population/boundary design before an application campaign. Optimization advances feasibility; independent physical evidence determines whether the study question is answered.

No new physical transport run or experimental comparison was performed for this report. Any corrections produced concurrently by the implementation agent require their own new verification artifact; the findings above describe the archived Stage 41–66 state inspected here.
