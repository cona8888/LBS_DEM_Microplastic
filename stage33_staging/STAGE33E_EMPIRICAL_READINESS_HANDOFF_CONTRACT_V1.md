# Stage33E — empirical-readiness handoff contract (V1)

**Status:** prospective evidence-intake design only; all empirical slots are empty.  
**Date:** 2026-09-01  
**Parents:** hash-bound Stage33D matched PET–LBS design and independently audited Stage33D-O synthetic workflow qualification.

## Research purpose and claim

Stage33E defines the evidence that must exist before the matched PET–LBS constant-head study can enter a real operational release. It does not collect measurements, authorize specimen preparation, open a custodian key, or run DEM/LBM. Its purpose is to prevent software qualification, preliminary microscopy or a plausible protocol from being mistaken for experimental readiness.

The future hydraulic question remains: at a fixed dry-PET loading and matched LBS state, do independently prepared water-only temperature-conditioned PET batches change `K20/K20_clean`? The experimental unit is the independent PET process batch, not a column, image, fibre or flow determination.

## System boundary

- PET source protocol: water only, sealed passive/autogenous-pressure chamber, one ambient-water process control and 120/140/160/180 °C conditions.
- Hydraulic specimen: saturated fixed-solid LBS column at target total-solid void ratio `e = 0.744 ± 0.010` and water temperature `20.0 ± 0.5 °C`.
- Design: three independent reactor blocks, five PET batches per block, three matched technical columns per batch, and one clean control per matched set: 45 PET columns plus nine clean controls.
- Primary observable: batch mean `log(K20_PET/K20_clean matched)`; treatment inference remains at 15 independent process batches.
- Omitted from this handoff: chemistry measurement, real microscopy processing, real hydraulic data, numerical prediction, particle mobility, migration, clogging, deformation and two-way coupling.

## Evidence states

Readiness is not one Boolean. The future evaluator must keep these states separate:

1. `laboratory_hydraulic_execution_ready`: material/process, PET mass/split, apparatus, effluent-detection and real custody evidence all pass.
2. `cross_domain_unblinding_ready`: hydraulic primary endpoints are frozen and both the empirical Stage33C-Q held-out gate and adjudicated morphology release pass.
3. `pet_specific_model_validation_ready`: a PET-specific numerical prediction release was frozen before empirical reveal and its independent numerical audit passed.
4. `degradation_proxy_claim_ready`: molecular molar-mass, an orthogonal chain-scission/product endpoint, recovery/mass balance and a new independent confirmation wave all pass locked directional and minimum-effect criteria.

No later state can substitute for an earlier failed state. A hydraulic experiment can never, by itself, establish molecular degradation or calibrate fibre length as a universal degradation scale.

In addition to the nine scientific evidence interfaces below, real operation has a separate software/governance blocker: `production_operational_toolchain_audit`. The Stage33D-O workflow proves only a test-only release path and deliberately rejects production mode. A new production-capable builder, fresh secret namespace, restricted-store procedure and independent hostile audit must pass before real identifiers or measurements may enter the workflow.

## Required Stage33D evidence interfaces

The handoff preserves the nine future inputs named by Stage33D:

| Evidence role | Hydraulic execution | Cross-domain reveal | Model validation | Degradation claim |
|---|---:|---:|---:|---:|
| Stage33A empirical-readiness closure | required | required | required | required |
| Stage33C-Q empirical held-out gate report | prior to reveal | required | required | required |
| Stage33C-Q adjudicated morphology release | prior to reveal | required | required | required |
| PET mass-budget and split qualification | required | required | required | required |
| Hydraulic-apparatus calibration release | required | required | required | required |
| Effluent-PET detection-method release | required | required | required | required |
| Real cross-release commitment | required | required | required | required |
| PET-specific frozen numerical predictions | not required | not required | required | not sufficient |
| Molecular and orthogonal chemistry release | not required for hydraulic response | not required for hydraulic response | not required | required |

Every populated evidence row must bind a unique regular file and exact SHA-256, declare its schema/release/status, include a passing independent audit where applicable, and be frozen before the state it authorizes. Blank or malformed fields are blocking, never interpreted as `not applicable` unless this contract explicitly marks the evidence conditional.

The Stage33A closure must be scope-resolved rather than treated as one opaque Boolean. It must disposition every Stage33A blocker with applicability, evidence and independent review. Material identity, baseline morphology, chamber/process control, recovery, analysis-mass allocation, blinded inference and governance are mandatory for the hydraulic branch. A mechanical-challenge method is required only if that challenge is part of the locked preparation/fragmentation question; molecular chemistry is required for the degradation-proxy branch, not to measure a strictly process-conditioned hydraulic response. An `OPEN`, silent omission or unjustified `not applicable` remains blocking for every state to which that blocker applies.

## Apparatus and hydraulic capability gates

The apparatus release must identify calibration/capability evidence for the dry-sand balance, PET/aliquot/filter balance, effluent collection balance or volumetric device, water-temperature measurement, timer, head sensor/gauge, specimen diameter and length gauges, saturation/leak assessment and the effluent collection train. Each record must bind instrument ID/model/serial, reference-standard certificate and hash, traceability, calibrated range and points covering the use range, resolution, observed/reference/correction values, as-found/as-left result, repeatability, drift, calibration uncertainty and coverage factor, validity interval, operating environment, SOP/hash, reviewer, prospective pass rule and guard-band decision. A derived uncertainty budget is required for void ratio, achieved PET dose, `K20` and matched log ratio.

Inherited Stage33D gates remain unchanged:

- recomputed-versus-supplied `K20` relative error `≤ 0.005`;
- clean-column CV `≤ 0.05` within reactor block;
- at least two valid clean controls per block and two valid matched sets per PET batch;
- all 15 batch endpoints for confirmatory complete-block inference;
- three distinct positive gradients per sentinel, discharge–gradient `R² ≥ 0.99`, `K20` CV `≤ 0.05`, and particle Reynolds number `≤ 1`;
- PET dose tolerance `max(0.0005 wt%, 5% of 0.09841784362759924 wt%)`;
- no saturation, leak, stationarity or premeasurement-eligibility failure.

Stage33E does not invent instrument uncertainty or reference-standard tolerances. Those values must be justified from the selected apparatus, method capability and intended minimum relevant effect, then frozen before any real specimen is measured. Missing capability thresholds block execution.

Packing capability must be qualified on nonconfirmatory material across the intended cells, operators and days. Total-solid void ratio must use measured cell volume and both sand and PET solid volumes with traceable densities; PET volume may not be silently neglected. The future release must report sample count, cell/operator/day coverage, mean, standard deviation, range, out-of-window fraction, density and dimensional uncertainty, void-ratio uncertainty and a prospective capability decision. Condition-specific vibration, pressure or compaction retuning is prohibited. Initial-to-postflow dimensional/void-ratio drift, saturation, leak and steady-flow acceptance must be based on separately validated quantitative procedures; no generic thresholds are invented here.

## PET mass budget, split and fixed-solid interpretation

The future mass/split release must keep two non-double-counted dry-basis closures: process recovery (charge versus recovered PET plus quantified process/filter/transfer losses) and split allocation (recovered PET versus morphology, chemistry, hydraulics, archive, residual and split loss). It must record moisture and blank corrections, bind balance calibration and prohibit pooling across the 15 independent process batches. Closure thresholds, rationale, uncertainty and acceptance bounds remain future capability-derived fields. The achieved hydraulic PET dose is calculated from measured dry PET and dry sand; it is not tuned by condition.

Because the material is fibrous, split qualification must also demonstrate representativeness rather than mass closure alone. Rotary/riffle or predeclared systematic-increment splitting must be tested with replicate daughter masses and morphology distributions (including Feret, width and class), bias, precision and uncertainty against a prospectively justified pass rule. Hand-picking is prohibited.

The effluent method must document PET identity, full-volume capture or validated subsampling, filter train/cutoffs, matrix and procedural blanks, positive controls, false-positive/false-negative handling, filter-plus-transfer recovery across representative PET size/shape/mass, precision, bias, sample volume, LoB/LoD/LoQ or a method-appropriate equivalent, mass-equivalent detection limit and the maximum PET fraction that could remain undetected. The fixed-solid interpretation passes only if the validated method makes undetected loss smaller than a prospectively frozen material-balance tolerance. PET detected at or above LoD, including detected-but-below-LoQ, fails the fixed-solid interpretation; below LoD means `nondetect`, never zero. A simple visual non-detect is insufficient.

## Morphology and degradation boundary

The Stage33C-Q synthetic qualification establishes only software and release behavior. Real cross-domain reveal requires an empirical held-out gate report and an adjudicated morphology release from the same independent PET batches. Morphology must remain batch-level for treatment inference; fibres, images and fields are subsamples.

Shorter maximum-Feret dimension, contour length or aspect ratio can describe a fragmentation phenotype. Calling length a degradation proxy additionally requires the conditional chemistry evidence and an independent confirmation wave. Temperature is a process condition, not a measured molecular-degradation axis.

## Custody and state transition

Real operator, analyst and custodian identities must be distinct. The real key and preparation/dose records remain restricted. Operator files contain raw hydraulics only; analyst files omit treatment/source identity. Primary endpoints and exclusions are frozen before a separately hash-bound reveal declaration, following the Stage33D-O-qualified two-phase sequence.

No real operational release may reuse the Stage33D-O test secret, opaque identifiers, synthetic measurements or synthetic morphology fixture. A separate production-capable builder and independent audit are required.

## Fail-closed requirements

A future readiness evaluator must reject missing evidence, hash/schema/status mismatch, duplicate evidence paths, self-audit, conditional evidence presented as hydraulic proof, expired calibration, missing uncertainty/capability fields, pooled batches, invalid dose arithmetic, unvalidated effluent non-detects, role overlap, premature reveal, synthetic/test identifiers in a real release, and any attempt to claim degradation from morphology alone.

## Current decision and stop boundary

This Stage33E release is intentionally `DESIGN_ONLY_ALL_EMPIRICAL_INPUTS_UNPOPULATED`. All four readiness states are false. Passing its independent audit means only that the intake contract and blank interfaces are internally consistent and hash-bound.

Stop before real evidence ingest, operational IDs/keys, specimen preparation, reactor or column execution, empirical image processing, treatment reveal, DEM/LBM, model validation, migration/clogging, deformation or coupling. Advancing requires the user to supply or authorize the real evidence named here and a new audited operational handoff.
