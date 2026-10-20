# Stage33F — core hydraulic-method qualification pilot contract (V1)

**Status:** prospective, standards-grounded design only; no laboratory observations, instrument identities, operator identities or production keys are present.  
**Date:** 2026-09-01  
**Parent:** independently audited and hostile-tested Stage33E empirical-readiness handoff.

## Research question and evidence role

Can the complete laboratory measurement chain be shown fit for its intended use before any confirmatory temperature-conditioned PET batch is consumed: traceable apparatus, matched LBS packing, dry-mass recovery and fibrous splitting, saturated constant-head measurement, and detection of PET leaving the fixed-solid specimen?

Stage33F is a **method-development and independent-qualification design**, not a PET-treatment experiment. Its future outputs may populate only these Stage33E core evidence roles:

1. `hydraulic_apparatus_calibration_release`;
2. `pet_mass_budget_and_split_qualification`;
3. `effluent_pet_detection_method_release`.

Even a future empirical Stage33F pass cannot by itself authorize the Stage33D campaign. Stage33A scope-resolved closure, a newly audited production operational toolchain, distinct real roles and a real cross-release commitment remain separate blockers.

## System boundary

- Material: the matched Leighton Buzzard Sand fraction and nonconfirmatory clean/representative PET material only.
- Hydraulic state: saturated rigid-wall constant-head testing at target total-solid void ratio `e = 0.744 ± 0.010` and water temperature `20.0 ± 0.5 °C`.
- PET loading used to exercise the chain: the frozen Stage33D target `0.09841784362759924 wt%` dry PET/dry sand, with achieved mass recorded rather than tuned.
- Phases resolved: apparatus and calibration; specimen preparation/packing; solid mass and aliquot splitting; water/effluent collection; PET identity/detection; raw flow and dimensional measurements; derived `K20` and matched log ratio.
- Deliberately omitted: confirmatory treatment comparisons, real Stage33D batch endpoints, chemical degradation, molecular molar mass, flexible-fibre mechanics, particle mobility, migration/clogging claims, deformation, DEM/LBM execution and hydro-mechanical coupling.

## Qualification sequence and independence

The future laboratory program has four immutable transitions:

1. `Q0_REQUIREMENTS_FROZEN`: intended instruments, cells, operators, working ranges, SOPs, risk assessment, prospective capability rules, uncertainty models and validation sample counts are completed and independently reviewed before data.
2. `Q1_DEVELOPMENT_PILOT_COMPLETE`: nonconfirmatory shakedown data may be used to revise procedures or derive defensible thresholds. Q1 is development evidence and can never pass the final qualification.
3. `Q2_INDEPENDENT_QUALIFICATION_FROZEN`: procedures and thresholds are re-frozen, then a new independent material/run set is executed without threshold retuning. Q1 specimens, measurements and acceptance decisions are not reused.
4. `Q3_CORE_METHOD_EVIDENCE_ELIGIBLE`: every module and cross-module closure passes the predeclared Q2 rules and an independent audit reproduces calculations and hashes. Eligibility still requires a new Stage33E transition release and human/institutional authorization.

No state may be skipped, replayed or edited in place. A failure remains evidence; it is not silently replaced after an outcome is viewed.

### Candidate minimum independent holdout

The planning basis is a **27-column candidate minimum**, subject to Q0 adoption only after actual capability and sentinel-range evidence are bound. Three qualification blocks/days each contain three independently remade clean columns, three columns split from one independent long/coarse-PET parent batch, and three columns split from one independent short/fine-PET parent batch. This gives nine clean columns, nine columns at each morphology bound, and six independent PET parent batches. It mirrors the later three-column technical structure, exercises three days, preserves at least two clean controls in a block after one invalid control, and challenges splitting/effluent capture at both morphology bounds.

This is not an executed or presently frozen sample count. Q0 must demonstrate that the two sentinels bracket intended use and bind the actual cells, operators, ranges, uncertainty, failure risk and Q1/Q2 counts. If thresholds need development, Q1 is a separate shakedown and none of its observations may be reused in the 27-column Q2 holdout.

## Current authoritative method framework

The following publications define method structure or reporting comparators. They do not supply missing apparatus-specific capability numbers, and access to an institutional/licensed full standard must be confirmed before execution.

- ISO 17892-11:2019, *Laboratory testing of soil — Part 11: Permeability tests*, confirmed current in 2025.
- ASTM D2434-26, *Laboratory Measurement of Hydraulic Conductivity of Coarse-Grained Soils*, active constant-head standard.
- ISO/IEC 17025:2017, confirmed current in 2023, for laboratory competence, impartiality and consistent operation.
- JCGM 100:2008 and the GUM suite for measurement uncertainty; JCGM 106:2012 for prospectively stated conformity decision rules.
- Eurachem, *Fitness for Purpose of Analytical Methods*, third edition 2025; 2025 planning/reporting and blank supplements; and *Fitness for Intended Use of Analytical Equipment and Systems*, first edition 2025.
- ISO 24187:2023 for general principles of environmental microplastic analysis.
- ISO 5667-27:2025 for sampling suspended microplastics in water.
- ISO 16094-2:2025 for microscopy plus vibrational-spectroscopy identification of microplastics, including PET, in low-suspended-solid water.

The effluent method may adapt these principles to the controlled permeameter matrix, but must validate the complete sampling, transfer, filter and identification chain for the actual intended use. A standards citation alone is not qualification.

## Module M1 — apparatus, traceability and uncertainty

Every intended dry-sand balance, PET/aliquot/filter balance, effluent mass or volume device, thermometer, timer, head device, specimen diameter/length gauge, cell, leak/saturation apparatus and effluent train must be uniquely identified. Records bind reference certificates and hashes, traceability, working range, resolution, calibration points spanning intended use, observed/reference/correction values, as-found/as-left state, repeatability, drift, uncertainty and coverage factor, validity interval, environment, maintenance, software/firmware where relevant, SOP/hash, reviewer and decision rule.

The Q0 release must define measurement models and uncertainty budgets for:

- total-solid void ratio, including cell volume, dry sand mass, dry PET mass and both traceable solid densities;
- achieved PET dry-mass fraction;
- raw hydraulic conductivity and temperature-corrected `K20`;
- matched `log(K20_PET/K20_clean)`.

Uncertainty is included in conformity decisions through a declared rule/guard band. Stage33F does not invent a universal fraction-of-tolerance rule. Working ranges, calibration density, uncertainty targets and decision risks are justified from intended use and the frozen minimum relevant log-ratio effect, then fixed at Q0.

## Module M2 — packing, saturation, leak and steady-flow capability

Packing is qualified on nonconfirmatory material across every cell, operator and day intended for Q2. The design must avoid confounding operator, cell and day; randomize run order; include independently remade specimens; and record all attempted packings. Total-solid void ratio uses both sand and PET volumes. PET volume may not be treated as negligible.

Q0 must freeze the number of operators, cells, days and replicate packings based on intended deployment and the precision needed to judge the `±0.010` void-ratio window. Q1 estimates variance; Q2 uses a separately frozen sample count and capability rule. Report the raw distribution, mean, standard deviation, range, out-of-window fraction, within/between operator/cell/day components and void-ratio uncertainty. Condition-specific vibration, pressure, tamping or compaction retuning is forbidden.

Saturation, leak and stationarity are quantitative method releases rather than unchecked booleans:

- saturation: de-airing path, duration/pore volumes, endpoint, trapped-air evidence and validation data;
- leak/wall bypass: system blank, sidewall check, duration, lowest intended discharge, detection capability and prospective maximum leakage;
- stationarity: raw sequential collection windows plus head and temperature time series, with a pilot-derived slope/CV rule frozen before Q2;
- postflow state: prospectively bounded dimensional or void-ratio drift based on measurement capability.

## Module M3 — PET recovery, mass closure and fibrous split representativeness

Two non-double-counted dry-basis closures are mandatory for every batch:

1. process recovery: initial PET charge versus recovered PET plus separately quantified chamber, transfer, filter and other losses;
2. split allocation: recovered PET versus morphology, chemistry, hydraulic, archive, residual and split loss.

Balances, blank/moisture corrections, equations, uncertainty, acceptance interval and reviewer are frozen. All 15 future process batches remain separate and unpooled.

Fibrous splitting must be qualified beyond total mass. Rotary/riffle or predeclared systematic-increment splitting is tested using replicate daughter portions. Q0 freezes comparisons for daughter mass, maximum-Feret/length, width and morphology-class distribution, with bias, precision, uncertainty and a prospective pass rule. Hand-picking is prohibited. Q1 may select the method; Q2 tests the frozen method on independent material.

## Module M4 — effluent PET sampling and detection

The validated measurement procedure covers the full effluent volume or a demonstrably representative subsample; sample vessel, cascade/filter train and cutoffs; contamination control; matrix and procedural blanks; positive controls; PET chemical identity; representative fibre/fragment size, shape and mass; transfer/filter recovery; false-positive and false-negative handling; precision; bias; working range; LoB/LoD/LoQ or a justified equivalent; sample volume; mass-equivalent detection limit; and maximum undetected fraction of initial PET.

Q0 freezes the maximum permissible mobile/undetected fraction from the fixed-solid claim and mass-balance capability. Q1 develops the method and Q2 independently tests it. Any PET signal at or above the validated LoD—including detected but below LoQ—fails the fixed-solid interpretation. Below LoD is reported as `nondetect`, never zero. Failed blanks, controls, recovery or identity invalidate the affected analytical batch. Visual inspection alone cannot pass this module.

## Module M5 — constant-head calculation and Darcy-linearity chain

The future Q2 qualification uses new clean and representative-PET sentinel specimens, not Stage33D confirmatory batches. Raw time, collected mass/volume, head, geometry and temperature remain immutable. Derived values are independently recomputed.

The following Stage33D numeric gates are inherited unchanged:

- supplied-versus-recomputed `K20` relative error `≤ 0.005`;
- at least three distinct positive gradients for one clean and one representative-PET sentinel for every intended cell/measurement configuration;
- discharge–gradient `R² ≥ 0.99`;
- within-sentinel determination `K20` CV `≤ 0.05`;
- declared particle Reynolds number `≤ 1` using a frozen definition and characteristic length;
- clean-column repeatability CV `≤ 0.05` within the defined qualification block;
- water temperature `20.0 ± 0.5 °C` and total-solid void ratio `0.744 ± 0.010`;
- PET dose tolerance `max(0.0005 wt%, 5% of 0.09841784362759924 wt%)`;
- no saturation, leak, stationarity, mass-balance or premeasurement-eligibility failure.

Monotonicity is not an acceptance gate. Q0 must separately freeze the actual gradient values/range, Reynolds-number formula, saturation/leak/stationarity thresholds and the failure scope before Q2.

## Cross-module completion gates

A future Stage33F empirical release is `Q3_CORE_METHOD_EVIDENCE_ELIGIBLE` only if:

- Q0, Q1 and Q2 are separate, ordered, hash-bound releases;
- Q1 did not contribute acceptance observations to Q2;
- every intended apparatus role, cell, operator and day is covered;
- all instrument validity intervals cover the measurements;
- uncertainty budgets and decision rules were frozen before Q2;
- packing, saturation, leak, stationarity, mass/split, effluent and hydraulic gates all pass;
- every raw attempt, failure, blank, spike and exclusion remains visible;
- the independent auditor reproduces mass, void-ratio, dose, `K20`, ratio, linearity, recovery and detection-limit calculations;
- no treatment identity or confirmatory Stage33D outcome entered method development.

Failure narrows or stops the method; it is never repaired by post-outcome threshold changes. Any revised method becomes a new version and requires a new independent Q2 wave.

## Current decision and stop boundary

The current Stage33F state is `DESIGN_ONLY_Q0_NOT_POPULATED`. All instrument, cell, operator, material, method, capability, threshold and evidence fields are blank. Every Stage33E empirical slot remains empty and all execution/claim authority remains false.

Stage33D-O remains synthetic software evidence only. Its test identifiers, secret/key material, fixtures and generated successful release are forbidden from this pilot and from any production handoff.

Passing the Stage33F design audit means only that the pilot and independent-qualification logic is internally consistent and standards-grounded. Stop before real inventory, identities, certificates, SOP adoption, material use, laboratory measurements, microscopy/chemistry, operational keys, Stage33D treatment work, empirical analysis, DEM/LBM, physical-validation claims, degradation claims, migration/clogging, deformation or coupling.
