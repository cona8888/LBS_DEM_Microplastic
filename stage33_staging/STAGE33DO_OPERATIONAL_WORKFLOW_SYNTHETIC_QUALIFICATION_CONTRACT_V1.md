# Stage33D-O — blinded hydraulic workflow synthetic qualification contract (V1)

**Status:** software/release-process qualification only.  
**Date:** 2026-09-01  
**Parent:** hash-bound Stage33D pre-data matched PET–LBS physical-validation design.

## Purpose

Stage33D-O qualifies the software boundary between the frozen 54-column design, restricted specimen custody, blinded hydraulic capture, batch-level evaluation and post-freeze reveal. It uses only synthetic measurements, test-only identifiers and a test-only secret. It does not populate any Stage33D empirical prerequisite and does not authorize laboratory or numerical execution.

The qualified workflow must demonstrate that:

1. 45 PET-bearing and nine clean-column slots are released as 54 unique opaque specimens;
2. the hydraulic operator package contains no condition, source-batch, morphology, chemistry or numerical-prediction field;
3. the analyst can identify clean versus PET specimens and matched sets without seeing treatment;
4. blinded specimen and 15 batch endpoints, an exclusion ledger, capture and linearity evidence are SHA-256 frozen before a separate reveal declaration can authorize treatment decoding;
5. `K20` is independently recomputed from raw constant-head measurements in SI units;
6. the evaluator produces one primary endpoint per independent PET process batch, never one treatment replicate per column or image;
7. every package, key, capture and result is hash-bound and immutable;
8. hostile lineage, leakage, duplication, state-control, linearity and key-commitment cases fail closed.

## Package separation

The synthetic release has three access domains:

- `restricted/`: custodian crosswalk, reveal key and cross-release commitment;
- `operator/`: opaque hydraulic capture and Darcy-linearity templates plus an operator manifest;
- `analyst/`: blinded specimen/matched-set roles, analyst batch codes, synthetic morphology fixture and an analyst manifest.

The operator package omits PET/clean role, condition, source batch, treatment temperature, morphology, chemistry and predictions. The analyst package may identify `clean_lbs_control` versus `pet_mixture` so matched ratios can be computed, but omits the five PET conditions and source batches. The reveal key maps analyst batch code to condition and reactor block. A commitment binds the packages before any synthetic measurement is generated.

Every nonrestricted schedule uses a fresh secret-derived operational permutation. Public-design run order, block, replicate, within-set order, source-batch slot, sentinel flag and any equivalent quasi-identifier are prohibited outside `restricted/`. A verifier must demonstrate that the public Stage33D design joined to all nonrestricted packages recovers zero treatment assignments. The six linearity sentinels use a separate `opaque_linearity_id` namespace; their raw records and pre-reveal attestation cannot be joined to specimen identities until the restricted primary freeze is complete.

The builder qualified here accepts only `synthetic_qualification` input and a conspicuously test-only secret. It is not production-capable. A future empirical operational release requires a separate builder and a new independent audit after all Stage33D future-input gates are populated.

## Hydraulic calculation

For water volume `V`, collection time `t`, specimen length `L`, cross-sectional area `A` and head difference `dh`:

`K_T = (V/t) L / (A dh)`.

Water density uses the Kell relation and viscosity uses

`mu = 2.414e-5 × 10^(247.8/(T + 133.15)) Pa s`.

`K20 = K_T (mu_T/mu_20) (rho_20/rho_T)`.

Synthetic fixtures are manufactured from prescribed `K20` values and then re-evaluated from raw water mass, dimensions, time, head and temperature. Agreement verifies code and units only; it is not an experimental or model result.

## Batch-safe endpoint

For PET batch `bt` and matched technical set `r`:

`z_btr = log(K20_btr) - log(K20_clean,br)`.

The evaluator averages valid `z_btr` values to one `R_bt` per independent batch. The positive synthetic fixture must yield 15 batch endpoints from 45 PET columns and nine clean columns.

Evaluation is strictly two phase. `pre_reveal` emits only opaque specimen results, exactly 15 endpoints keyed by `analyst_batch_code`, an exclusion ledger and a pre-reveal completion record; it must not read the reveal key or emit condition summaries. The restricted primary-freeze commitment binds those artifacts, sanitized and raw capture, raw linearity, the opaque-ID-only linearity attestation, synthetic morphology fixture, evaluator/configuration and the earlier premeasurement commitment. Only then may a separate reveal declaration bind that frozen commitment to the reveal-key hash. `post_reveal` requires both records before it can emit a condition summary. Synthetic morphology association is marked test-only and cannot qualify an empirical morphology–hydraulic relationship.

## Frozen gates exercised by the positive fixture

- `e = 0.744 ± 0.010`;
- water `20.0 ± 0.5 °C`;
- at least two valid matched sets per PET batch and two clean controls per block;
- clean-column CV `≤5%` within block;
- PET dose within `max(0.0005 wt%, 5% of 0.09841784362759924 wt%)`;
- three-gradient sentinels with discharge–gradient `R² ≥0.99`, determination `K20` CV `≤5%`, and particle Reynolds number `≤1`;
- recomputed versus supplied `K20` relative error `≤0.5%` when a supplied cross-check is present;
- no leakage, saturation failure, nonstationarity or PET detection in effluent.

## Required negative challenges

At minimum, the verifier must show rejection of:

1. duplicate or missing opaque specimen identities;
2. a capture whose hash or identity set is not bound to the release;
3. treatment/source/morphology/prediction leakage into the operator package;
4. a mutated reveal key or cross-release commitment;
5. an out-of-range pre-measurement void ratio;
6. failed Darcy linearity;
7. prohibited custody/analysis role overlap;
8. a non-test release attempt or test-secret leakage into operator/analyst packages.

The verifier must also prove non-joinability against the public Stage33D design and absence of specimen/sentinel mapping in every analyst-visible artifact.

Negative fixtures remain immutable diagnostic evidence. They are not deleted or converted into positive results.

## Evidence and claim boundary

Passing Stage33D-O supports only the statement that the blinded release, hydraulic arithmetic, batch aggregation and fail-closed software behave as specified on synthetic fixtures. It does not support:

- empirical PET morphology or permeability;
- a temperature effect;
- chemical or molecular degradation;
- length as a degradation proxy;
- agreement with PET-specific numerical predictions;
- absolute permeability validation;
- migration, clogging, deformation, transient coupling or two-way coupling.

## Stop boundary

Stop after independent audit of the synthetic qualification. Do not ingest a real key, real calibrated microscopy, empirical chemistry, real hydraulic measurements or PET-specific predictions. Do not execute reactors, columns, DEM, LBM or coupled mechanics. A separate, newly audited operational handoff is required after all Stage33D future-input gates are populated and passed.
