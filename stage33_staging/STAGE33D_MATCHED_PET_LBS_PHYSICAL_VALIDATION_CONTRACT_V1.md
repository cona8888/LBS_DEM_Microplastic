# Stage33D — matched PET–LBS physical validation contract (V1)

**Status:** prospective design only; empirical inputs, operational blinding, laboratory execution and numerical execution remain closed.  
**Date:** 2026-09-01  
**System:** water-only temperature-conditioned PET wool/cotton mixed with Leighton Buzzard Sand (LBS), saturated constant-head flow.

## 1. Research question and claim boundary

At a fixed dry-PET/dry-sand mass fraction and matched LBS state, does the batch-level PET fragmentation phenotype produced by the frozen water-only treatment protocol change relative hydraulic conductivity, and is that response associated with the independently measured same-batch morphology distribution?

The permitted empirical wording is **temperature-conditioned fragmentation phenotype and matched hydraulic response**. PET length is a physical morphology response. It is not, by itself, a molecular degradation scale. A degradation-proxy claim additionally requires independently measured molar-mass loss, an orthogonal chain-scission/product endpoint, acceptable recovery/mass balance and replication in a new confirmation wave.

The treatment contains PET and water with no added catalyst or reagent. Water is nevertheless part of the hydrothermal system. Pressure is passive/autogenous and coupled to temperature unless it is independently controlled and recorded; no independent pressure effect may be claimed.

## 2. Evidence role

Stage33D is a frozen, pre-data matched physical-validation design. It reuses the verified Stage32 constant-head measurement kernel but does not modify or relabel the immutable F37 surrogate release. It binds the Stage33 morphology pipeline and acquisition qualification as software evidence only. Those synthetic tests are not empirical PET evidence.

Stage33D may later support three separate evidence statements:

1. a physical treatment-profile statement from matched laboratory specimens;
2. an associational same-batch morphology–hydraulic statement;
3. a numerical physical-validation statement only if PET-specific predictions are frozen before hydraulic outcomes are revealed.

No one statement substitutes for another.

## 3. System boundary

- PET conditions: `T20`, `T120`, `T140`, `T160`, `T180`; 12 h in 50 mL water with 1.0 g PET per independent process batch.
- `T20` is the process-matched water control. As-received PET remains descriptive and is not one of the five confirmatory levels.
- Replication: three independently charged, recovered and dried PET batches per condition in three complete reactor blocks.
- Sand: the same LBS Fraction B / 0.60–1.18 mm fraction and lot used by the matched Stage32 protocol.
- Hydraulic state: saturated specimen, de-aired water, `20.0 ± 0.5 °C`, target total-solid void ratio `e = 0.744 ± 0.010`.
- Loading: `0.09841784362759924 wt%` dry PET per dry sand, held identical across conditions. Achieved mass and volume fractions are recorded.
- Flow: steady constant head in the Darcy regime; intrinsic permeability and `K20` are calculated from raw dimensions, head, time, water mass and temperature.
- Fibres/fragments are intended to remain fixed during the primary measurement. Effluent capture is mandatory. Detected PET transport invalidates the fixed-solid interpretation for that specimen and is retained as a structured outcome.

The design deliberately omits mobile-sand mechanics, PET flexibility/deformation, migration mechanisms, evolving clogging, transient coupling and two-way hydro-mechanical coupling.

## 4. Experimental hierarchy and aliquot custody

The hierarchy is:

`reactor block → independent PET process batch → split aliquot → independently packed hydraulic column → repeated flow determination`.

The reactor batch is the treatment experimental unit. Images, objects, aliquots, packed columns and repeated flow readings are subsamples or technical replicates.

After frozen recovery, washing and drying, each PET batch is split without hand-picking into:

- a Stage33C-Q morphology aliquot;
- a molecular/orthogonal chemistry aliquot;
- a hydraulic aliquot sufficient for three columns;
- an archive/mass-balance aliquot.

The splitting method must be validated prospectively for fibrous material, use multiple systematic increments or a qualified rotary/riffle procedure, and retain all fractions. Batches are never pooled. Every transfer and dry mass is recorded. If the available mass or balance capability cannot support the frozen loading for all three columns plus reserved analyses, the operational release fails before any conductivity result is viewed.

## 5. Matched 54-column design

For every reactor block `b = 1..3` and technical replicate `r = 1..3`, prepare a six-column matched set:

- one clean LBS column `C0_br`;
- one PET-bearing column from each of `T20`, `T120`, `T140`, `T160`, `T180` in that block.

This yields 45 PET-bearing columns and nine clean controls. Each set shares sand lot, preparation day, apparatus calibration and replicate position. Set order and the six specimen positions are randomized prospectively. Clean controls remain distributed through the campaign.

Mixing and deposition are frozen before use. The nominal orientation is isotropic/random, but achieved orientation and visible segregation are recorded rather than assumed. Packing pressure or vibration is not tuned per condition. Eligibility is decided from state and integrity data without viewing conductivity or the treatment key.

## 6. Hydraulic measurement kernel

For collected water volume `V`, time `t`, specimen length `L`, cross-sectional area `A` and head difference `dh`:

`K_T = (V/t) L / (A dh)`.

Fresh-water density uses the Kell relation and dynamic viscosity uses

`mu = 2.414e-5 × 10^(247.8/(T + 133.15)) Pa s`.

The temperature correction is

`K20 = K_T (mu_T/mu_20) (rho_20/rho_T)`.

All calculations use SI units. Raw measurements remain immutable. Supplied conductivity values are cross-checks only and must agree with independent recomputation within 0.5%.

At least one clean and one PET sentinel in every reactor block receive three distinct positive head gradients. Discharge rate versus gradient must have `R² ≥ 0.99`, determination-level `K20` CV must be `≤5%`, and the declared particle Reynolds number must be `≤1`. Leakage, saturation failure, pressure drift, temperature failure or nonstationary flow is reason-coded.

## 7. Primary estimand and analysis

For PET condition `t`, block `b` and matched replicate `r`:

`z_btr = log(K20_btr) − log(K20_0br)`.

The batch endpoint is

`R_bt = mean_r(z_btr)`

over valid, prospectively eligible matched sets. `exp(R_bt)` is the geometric-mean matched conductivity ratio.

The confirmatory treatment profile uses the 15 batch endpoints in

`R_bt = mu + Block_b + Treatment_t + epsilon_bt`,

with fixed block and treatment terms. The unrestricted five-condition profile is primary; monotonicity is not an acceptance gate. Planned summaries are `T180 − T20` and the treated-only `T120`–`T180` slope per 20 °C. `T20` is never coded as zero temperature in that slope.

If the five assignments were genuinely randomized within each complete block, the omnibus test may use exact whole-batch randomization inference over `(5!)^3 = 1,728,000` assignments. Pairwise inference has only three independent paired block contrasts and is reported with that limitation. Column or object counts never replace batch replication.

The primary morphology covariate is the frozen same-batch `log(D50 maximum Feret)`. The batch-level association model is

`R_bt = alpha + Block_b + beta log(D50_bt) + epsilon_bt`.

This slope is associational and cannot establish that length alone caused the hydraulic response because width, count, shape, surface state and chemistry co-vary. Report raw batch points, uncertainty propagation from whole fields and complete matched column sets, and leave-one-block-out sensitivity. Object-level or column-level pseudo-replication is prohibited.

Secondary morphology summaries include D10/D50/D90 Feret, eligible-fibre contour length, width, aspect ratio, straightness, curvature, shape-class fractions and fragment abundance per recovered mass. Molecular `Mn`, an orthogonal hydrolysis/product endpoint, crystallinity and mass balance remain separate axes; no composite degradation index is created post hoc.

The minimum relevant hydraulic effect is frozen as `|log(0.95)| = 0.0512932944`. With only three blocks, Stage33D is primarily a method-locking and variance-estimation wave. Observed between-batch variance may plan a new independent confirmation wave; retrospective power cannot rescue an inconclusive result.

## 8. Empirical acceptance gates

All integrity gates are mandatory:

1. all 15 PET batches are independent, traceable, unpooled and linked to the correct reactor block;
2. empirical Stage33C-Q acquisition, two-reviewer adjudication and held-out morphology qualification pass before cross-domain unblinding;
3. every raw file, calibration, batch link, aliquot transfer, column record and analysis release is SHA-256 bound;
4. all five conditions in all three blocks have a batch endpoint; at least two valid matched column sets contribute to each endpoint;
5. at least two clean controls per block are valid and clean `K20` CV is `≤5%`;
6. eligible columns meet the frozen void-ratio, water-temperature, saturation, dimensional, PET-dose and raw-measurement rules;
7. achieved PET concentration is within `max(0.0005 wt%, 5% of target)` and no condition-specific dose retuning occurs;
8. all Darcy-linearity sentinels pass;
9. no primary specimen has PET above the validated effluent detection limit or another sign of changing solid geometry;
10. exclusions are determined blind to conductivity and treatment, remain visible, and only pre-measurement QA failures can trigger a predeclared reserve;
11. no missing batch is imputed or replaced after unblinding;
12. operational custodian, hydraulic operator, morphology analyst, hydraulic analyst and reveal officer roles satisfy the frozen separation rules.

If a block becomes incomplete, the confirmatory complete-block result is withheld and the retained data are descriptive. A failed measurement gate is a scientific/operational result, not permission to alter the protocol silently.

## 9. Required future inputs

This design intentionally leaves the following paths and hashes unpopulated:

- the real Stage33C-Q empirical qualification and adjudicated morphology release;
- the real batch/aliquot cross-release commitment generated outside the analyst workspace;
- apparatus, balance, dimensional, temperature and effluent-detection calibrations;
- completed PET mass-budget and split-qualification record;
- molecular/orthogonal chemistry release if a degradation-proxy claim is sought;
- PET-specific frozen numerical prediction ranges if a numerical physical-validation claim is sought.

Synthetic Stage33C-M/Q evidence cannot fill any empirical slot. Existing straight F37 numerical ranges are context only and cannot be relabelled as predictions for recovered PET.

## 10. Decision classes

- **Design pass:** protocol, matrix, templates, lineage, gates and independent audit pass; all execution authority remains closed.
- **Empirical measurement pass:** future operational release and all integrity/hydraulic gates pass. The treatment profile itself may show an effect, no relevant effect or be inconclusive.
- **Partial empirical pass:** universal Feret and hydraulics pass but topology-dependent morphology metrics fail; only the qualified domain is reported.
- **Fail:** provenance, blinding, batch completeness, state control, flow linearity, fixed-solid integrity or universal morphology gates fail.
- **Numerical validation pass/partial/fail:** evaluated only against PET-specific predictions frozen before reveal. It is not defined by this pre-data release.

## 11. Stop boundary

This release authorizes only design construction and independent audit. Stop before introducing a real treatment key, processing empirical microscopy, assigning operational specimen IDs, executing reactors or columns, unblinding data, launching DEM/LBM, retuning a model, or claiming molecular degradation, length calibration, absolute permeability validation, migration, clogging, deformation or coupling.
