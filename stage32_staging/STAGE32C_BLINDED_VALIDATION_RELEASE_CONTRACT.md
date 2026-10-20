# Stage32C Blinded Matched-Validation Release Contract

## Purpose and evidence boundary

Stage32C converts the frozen Stage32A prospective design into an immutable, blinded laboratory-data release. It does not execute an experiment, modify the DEM-LBM model, or make a physical-validation claim. Literature evidence from Stage32B is bound as external context only and is not substituted for matched observations.

The evaluator must answer the Stage32A question without changing predictions after measurements exist: can the frozen fixed-solid DEM-LBM model predict clean-sand `K20` and concentration-dependent relative `K20` for matched Leighton Buzzard Sand Fraction B specimens?

## Immutable inputs

- Stage32A `resolved_protocol.json`, `design_matrix.csv`, and independent `design_audit.json`.
- Stage32B `literature_dataset.json` and `literature_verification_report.md`.
- This contract, the release builder, evaluator, evaluator dry-run test, and release auditor.

Every input and release artifact is SHA-256 bound. Existing output directories are never overwritten.

## Separation and blinding

The release contains two distinct tables:

1. `preparation_schedule.csv` retains recipe, group, and frozen predictions for the specimen-preparation custodian.
2. `operator_capture.csv` retains only specimen identity, randomized order, phase/block, and raw measurement fields. It omits group labels, concentration labels, orientation labels, and all predictions.

The evaluator joins the blinded capture to the frozen design only after hashing the completed raw files. Raw observations are never edited in place.

## Objective specimen eligibility

Eligibility is determined before conductivity enters any state-control decision. A specimen is eligible only when all of the following hold:

- operator `valid` is an affirmative token;
- `final_void_ratio` is in `[0.734, 0.754]`;
- water temperature is in `[19.5, 20.5] degC`;
- dry-sand mass, specimen diameter and length, head difference, collection time, and collected-water mass are finite and positive;
- a non-clean achieved dry-mass concentration is within `max(0.0005 wt%, 5% of target)` of target;
- a clean specimen has no more than `0.001 g` fibre;
- every included mixture specimen has at least one eligible clean control with the same `batch_id`;
- an ineligible or operator-rejected row retains a non-empty rejection reason.

Conductivity is recomputed from raw constant-head measurements. Supplied `K_raw_m_s` or `K20_m_s`, if present, is treated only as a cross-check and must agree with the recomputation within `0.5%` relative tolerance.

## Frozen hydraulic calculation

For water volume `V`, collection time `t`, specimen length `L`, cross-sectional area `A`, and head difference `dh`:

`K_T = (V/t) * L / (A*dh)`.

Water density uses the Kell freshwater relation and dynamic viscosity uses `mu = 2.414e-5 * 10^(247.8/(T+133.15)) Pa s`. The correction is

`K20 = K_T * (mu_T/mu_20) * (rho_20/rho_T)`.

All calculations use SI units internally.

## Darcy-linearity control

`darcy_linearity_capture.csv` must contain at least three distinct positive head differences for one eligible clean specimen and one eligible `iso_0p401820` specimen. For each specimen:

- ordinary least-squares `R^2` for discharge rate versus hydraulic gradient must be at least `0.99`;
- the sample coefficient of variation of the recomputed `K20` determinations must not exceed `5%`.

Both controls must pass before Phase 2 can be released.

## Pre-registered statistical evaluation

- Use sample standard deviations and two-sided 95% Student-t intervals for group means.
- Relative `K20` for each mixture specimen is its `K20` divided by the mean eligible clean `K20` in the same batch.
- Phase 1 requires at least five eligible specimens per group; Phase 2 requires at least three per orientation group.
- Clean repeatability requires CV <=5%.
- Clean magnitude support requires the experimental mean-`K20` 95% interval to overlap the frozen numerical clean envelope.
- Relative support requires interval overlap with the frozen numerical range at two or more of `0.051576`, `0.098418`, and `0.401820 wt%`, and the upper 95% interval at `0.401820 wt%` must be below one.
- `0.004691 wt%` is a descriptive detection-floor group and cannot fail the model alone.
- Monotonicity is descriptive, not an acceptance gate.
- Phase 2 is released only if Phase-1 minimum counts, state controls, clean repeatability, clean magnitude, and both Darcy-linearity controls pass. Relative-model support is reported independently and is not used to suppress the holdout.
- Orientation support at `0.401820 wt%` requires `parallel mean ratio < isotropic mean ratio < transverse mean ratio`.

## Fail-closed behavior

The evaluator refuses duplicate/missing specimen identities, lineage mismatches, altered randomized order, malformed numeric input, unsupported validity tokens, missing batch-clean bindings, premature Phase-2 evaluation, and non-empty output directories. Failures remain explicit; they are not silently dropped.

## Stop boundary

Stage32C authorizes only release construction, independent audit, and synthetic dry-run testing. It does not authorize laboratory execution, an absolute-permeability validation claim, model recalibration, numerical reruns, mechanics reruns, mobile sand, migration, clogging, deformation, transient coupling, or two-way coupling.
