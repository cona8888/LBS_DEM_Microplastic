# Stage33A PET fragmentation characterization contract

## Status and evidence role

Stage33A is a prospective experimental-characterization preflight. It converts the two-slide PET treatment concept into an auditable design and laboratory capture system. It does not reinterpret the slide annotations as raw data, authorize laboratory execution, freeze DEM/LBM length classes, modify Stage32, or make a degradation or permeability-validation claim.

## Research question

Under one fixed 12 h water/catalyst formulation and one PET grade/lot, do process-matched ambient control, 120, 140, 160 and 180 degC treatments produce reproducibly different molecular states and different fragmentation responses to a standardized mechanical challenge?

Fibre or fragment length is an operational descriptor of physical fragmentation state. It is not a direct or universal molecular-degradation scale.

## System boundary

- Material: one chemically confirmed PET grade and lot, with measured density, moisture, additive/finish status, feed carbon fraction, initial length and width distributions.
- Conditions: as-received descriptive reference plus process-matched 20 degC water control and 120, 140, 160 and 180 degC treatments, all treatment vessels at 12 h.
- Blanks: condition-matched water/reagent process blank at every treatment temperature in every block.
- Experimental unit: independently weighed, charged, processed, recovered and dried reactor/vessel batch. Images, fields, objects and analytical injections are technical subsamples.
- Split plot: each recovered PET batch is homogenized gently and divided by mass into unchallenged and standardized-challenge aliquots.
- Primary evidence domain: fixed formulation, reactor, recovery train, imaging method, challenge protocol and analytical methods.

## Wave-1 design

Wave 1 is a method-locking feasibility and variance-estimation campaign:

- three complete blocks;
- five PET process conditions per block: 20, 120, 140, 160 and 180 degC;
- five matched no-PET blanks per block;
- three as-received PET reference subsamples outside the reactor-temperature inference;
- 15 independent PET process batches, 15 process blanks and 3 descriptive as-received units;
- 18 PET-bearing units split into 36 pre/post-challenge aliquots.

Within each block, vessel/run order is randomized and condition is rotated across reactor IDs. Imaging order and challenge order are randomized separately. Sample codes remain blinded through acquisition, segmentation and primary QC.

Wave 1 does not by itself support a confirmatory statement that length reflects degradation level. After methods and minimum relevant differences are frozen, an independent confirmation wave is required. If methods change after Wave 1, Wave 1 remains development evidence.

## Co-primary endpoints

1. Batch-level number-weighted median maximum-Feret dimension after the standardized challenge, analysed as `log(D50_Feret_um)`.
2. One predeclared molecular chain-scission endpoint, preferably `log(Mn_g_mol)` by SEC/GPC. Intrinsic viscosity may replace SEC only if frozen before unblinding.

Both endpoints must support a categorical treatment effect before the phrase “treatment-associated degradation and fragmentation” is used. Treatment temperature is categorical; monotonicity is not an acceptance gate.

The mechanistic secondary endpoint is the batch fragmentation-susceptibility index

`FSI = log(D50_Feret_pre / D50_Feret_post)`.

Positive FSI denotes shortening under the fixed challenge. Additional endpoints are D10/D90/IQR and ECDF, fibre-contour length, width, aspect ratio, morphology fractions, broken ends, object count per recovered PET mass, Mw/dispersity, intrinsic viscosity, carboxyl/end-group or validated FTIR measures, DSC/XRD crystallinity, liquid products and carbon balance.

## Imaging and object rules

- Raw images are immutable and individually SHA-256 bound.
- Fields use a systematic-random or other predeclared probability-sampling rule. Zero-object fields remain recorded.
- All objects use maximum Feret dimension as the universal size measure.
- Skeletonized geodesic contour length is reported only for accepted, unbranched elongate objects with two endpoints and no branch points.
- Compact fragments use maximum Feret dimension; clusters and ambiguous objects do not enter the primary object-length distribution.
- Width uses a validated distance-transform method along the skeleton for elongate objects. Maximum/minimum Feret ratio is reported separately.
- Border-clipped objects are right-censored; below-detection material creates left truncation. Neither is silently deleted or assigned zero.
- An initial sampling gate is at least 10 pixels along measured length and 3 pixels across width, subject to optical validation.
- Detection completeness is established by calibration objects, spikes or synthetic-image injection. The smallest observed object is not the detection limit.
- Around 75 accepted objects per aliquot and at least 200 per condition/challenge is a precision-planning target, not the inferential sample size. Sampling is by predeclared area/fields and cannot stop after a favourable object count.

## Mass and carbon balance

Primary closure is a carbon balance because PET hydrolysis incorporates water and monomer masses cannot be summed directly against PET feed mass.

For each reactor:

`C_in_mg = dry_PET_mass_g * measured_feed_carbon_fraction * 1000 + carbon_from_co_reagents_mg`

`C_out_mg = solid_carbon_mg + aqueous_DOC_carbon_mg + gas_carbon_mg + wall_carbon_mg`

`carbon_closure_fraction = C_out_mg / C_in_mg`.

For verified additive-free PET the theoretical repeat-unit carbon fraction is approximately 0.6250, but measured feed carbon is required for textile PET containing dye, finish, filler or another polymer. Product yields are reported molar relative to initial PET repeat units; they are not called conversion. Residual-PET conversion requires speciation of retained material so precipitated TPA/MHET/BHET/oligomers and catalyst are not counted as PET.

The quantitative recovery train retains coarse solids, staged fines, final filtrate, all rinses, filters, wall deposits/swabs and headspace where relevant. Operational filter fractions are not described as exact particle-size bins.

Provisional method-development gates, to be frozen after blank and uncertainty studies:

- closed-reactor charge change <=0.2%; investigate 0.2–0.5%; invalidate >0.5%;
- untreated procedural carbon recovery 95–105%;
- primary carbon closure 95–105% and consistent with 100% within expanded uncertainty;
- 90–95% or 105–110% is conditional and unsuitable for calibration without resolution;
- outside 90–110% fails;
- blank carbon below LOQ or <1% of initial PET carbon;
- target-analyte recovery normally 90–110%, with justified 85–115% only near LOQ;
- quantified species carbon cannot exceed DOC carbon beyond combined uncertainty;
- unidentified aqueous carbon >10% of initial PET carbon triggers further product analysis.

## Statistical plan

Wave-1 primary summaries are batch-level. Objects are not treated as independent replicates.

- Post-challenge morphology: `log(D50_Feret) ~ block + treatment`.
- Molecular endpoint: corresponding blocked categorical-treatment model.
- Fragmentation susceptibility: `FSI ~ block + treatment`.
- Descriptive split-plot model: `log(D50) ~ treatment * challenge + block + reactor(block:treatment)`.
- Use treatment-versus-control contrasts with multiplicity control, geometric-mean ratios, absolute differences, 95% intervals and raw batch values.
- With three blocks, emphasize effects and restricted randomization/permutation inference. Do not rely on pooled-object ordinary tests or fragile asymptotic mixed-model p-values.
- A hierarchical bootstrap may resample reactors first, then fields and objects for distribution uncertainty.
- Association of length with molecular markers is exploratory in Wave 1. No degradation clock or mediation model is fitted from 15 process batches.

## Objective exclusions

A reactor unit may be excluded only for wrong formulation, identity loss, leakage, failed temperature/pressure history, contamination or documented recovery failure. A challenge aliquot may be excluded only for failed calibrated dose, spill or identity loss. Images and analytical repeats follow frozen instrument-QC criteria.

Do not exclude statistical outliers, non-monotonic observations, zero-object fields, small objects near the detection limit, failed mass balances or inconvenient image fields. Every failure remains in the dataset with reason, timestamp and decision maker. Fewer than three included independent process batches in any condition fails Wave-1 readiness; technical replicates cannot replace them.

## Fail-closed blockers before execution

1. Resolve catalyst identity/loading or formally rename the process hydrothermal treatment.
2. Freeze PET grade, lot, density, feed carbon, purity/additives and original length/width distributions.
3. Identify the Slide-2 treatment and recover raw images and measurement data.
4. Freeze reactor, temperature/pressure/ramp logging, safety and quantitative-transfer procedures.
5. Freeze the standardized challenge in device, vessel, sample/liquid mass, fill fraction, speed/amplitude, duration or delivered energy, temperature and transfer count.
6. Freeze filter train, recovery, drying and anti-fragmentation handling controls.
7. Validate imaging calibration, probability-field sampling, object definitions, completeness curve, segmentation, border/censoring and PET-confirmation rules.
8. Validate SEC/IV and liquid-product methods, blanks, LOQs, recoveries and carbon attribution.
9. Complete an analysis-mass allocation showing that the available PET supports morphology, SEC/IV, DSC/XRD, spectroscopy and balance measurements.
10. Freeze blinded identifiers, randomization, numerical QC tolerances, exclusions, minimum relevant effects and confirmation-wave replication.
11. Confirm image/data ownership and permission for research and publication reuse.

Until every blocker is closed, the permissible term is “protocol-specific PET fragmentation state”.

## Relationship to Stage32 and future Stage33B

Stage32 remains byte-for-byte frozen as a blinded pre-data protocol for the 0.90 mm x 0.10 mm, 940 kg/m3 F37 polyethylene surrogate. Stage33A does not relabel it PET.

Only an audited Stage33A dataset may provide empirical PET length/width/shape distributions to a separate Stage33B fixed-solid numerical verification branch. Stage33B must use measured PET density, `100 * dry PET mass / dry sand mass`, exact solid-volume conservation, variable centreline resolution, short-fragment mask checks and new CPD2/CPD4/selected-CPD8 solution verification. It does not authorize migration, clogging, mobile sand or fibres, deformation, transient chemistry or two-way coupling.
