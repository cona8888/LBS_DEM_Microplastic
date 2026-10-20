# Reviewed algorithm candidates

This directory preserves the historical Stage 41–66 files. Read
[ALGORITHM_REVIEW.md](ALGORITHM_REVIEW.md) for the final decision and
[SCIENTIFIC_REVIEW.md](SCIENTIFIC_REVIEW.md) for the physical assumptions and
study limitations. All implementations use the existing local stage modules;
this is not a standalone package.

## Conservative integration path

From Python, put `algorithm_review_20260912/src` on `sys.path`, then use:

```python
from wall_field_exact_v1 import WallCellFieldExact
import trajectory_explicit_v1

field = WallCellFieldExact.from_field(existing_field)
result = trajectory_explicit_v1.integrate(field, exact_geometry, ...)
```

The arguments match the preceding trajectory functions, with optional explicit
`contact_model`. Without that argument, Stage 53 is the contact solver. The
new path corrects the first-exit and terminal-Re checks and makes recovery
selection local to each trajectory. The frozen-force integrator, physical
parameters and contact acceptance thresholds are retained. Existing result
files do not change, and the new detector can legitimately change an affected
exit classification.

`trajectory_recovery_v1` enables analytic recovery after rejection and timestep
reduction. `trajectory_prefix_optional` instead tries analytic contact after
200 unchanged cold-PGS sweeps. Both are experimental; a residual pass does not
certify unchanged frictional solution selection or trajectory convergence.
Neither is a replacement for the study's qualified default.

## Reproduce bounded checks

Run from `C:/MATDEM_MICROPLASTIC` with the installed Python environment. Every
output directory must be new. These commands exercise different scopes:

```powershell
python algorithm_review_20260912/src/verify_wall_field_exact_v1.py --output algorithm_review_20260912/evidence/field_repeat
python algorithm_review_20260912/src/verify_analytic_contact_v1.py --output algorithm_review_20260912/evidence/contact_repeat
python algorithm_review_20260912/src/verify_events_v1.py --output algorithm_review_20260912/evidence/events_repeat
python algorithm_review_20260912/src/verify_integration_v1.py --mode smoke --output algorithm_review_20260912/evidence/smoke_repeat
python algorithm_review_20260912/src/verify_prefix_optional.py --mode crossing --seeds 3 --fractions 0.1 --budget 300 --output algorithm_review_20260912/evidence/crossing_repeat
python algorithm_review_20260912/src/verify_integration_v1.py --mode saved --seeds 1 2 3 --fractions 0.1 0.05 0.025 --horizon 0.02 --budget 120 --output algorithm_review_20260912/evidence/continuation_repeat
```

The last command intentionally reproduces a qualification test that can fail.
A nonzero exit code records failed gates; it does not invalidate the preserved
failure evidence. Budgets are checked at physical-step boundaries and may be
exceeded by one expensive step. Displacement and relaxation bounds are refined
together; angular, maximum-step and flow-resolution sensitivity remain separate
qualification requirements. A saved-state continuation starts a fresh dwell
monitor and measures a short mechanical trajectory, not population residence.

Results include source/input hashes, configuration and environment where
applicable. Local solver timings and field-sampling timings are not full-run
speedup estimates. Concurrent development checks share CPU resources.
