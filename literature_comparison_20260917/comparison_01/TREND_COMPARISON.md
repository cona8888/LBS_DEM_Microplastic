# Literature trend comparison — no parameter fitting

17 September 2026. Source-derived data and comparison notes only; no manuscript, publication figure or new simulation.

## Decision

- Use control-normalised changes and mechanism comparisons. Keep all model parameters fixed; no optimisation, fitted contact parameters or experimental curve-matching loop.
- This is a trend-consistency assessment, not empirical validation. Normalisation removes units/baselines, not differences in packing, polymer, shape, chemistry or release denominator.
- Keep both agreeing and disagreeing trends. Do not force monotonicity or rescale concentration/time to make curves coincide.

## 1. Sand hydraulic data

[Aminzadeh et al. (2025)](https://doi.org/10.1038/s41598-025-30476-6), Figure 3a: 18 bars digitised (three controls repeated across two panels). Values below are treatment/control mean ratios.

| Sand | PE, 2% | PE, 5% | PVC, 2% | PVC, 5% |
|---|---:|---:|---:|---:|
| fine | 0.416 | 0.315 | 1.055 | 0.653 |
| medium | 0.477 | 0.262 | 0.826 | 0.607 |
| coarse | 0.919 | 0.420 | 0.956 | 0.815 |

- Predominantly lower conductivity; the fine-sand 2% PVC point is above its control. Bar digitisation sensitivity is ±2 native pixels, about ±0.00053 cm/s. Experimental errorbars are not represented by this digitisation bound.
- Sand was mixed/repacked at 2–5% mass loading; PE/PVC size and density differ. This is not an ideal sphere-versus-fibre experiment. Our historical fibre mass loadings are much lower; no common concentration slope is claimed.

## 2. Fibre and granule counterexample

[Yu et al. (2023)](https://doi.org/10.1021/acs.est.2c09822), SI Figure S6C: 23 plotted means/SDs recovered from vector errorbars; one field-weathered fibre point is unavailable. Each series uses its own zero-loading control.

| Material/condition | Concentration (% w/w) | K/K0 |
|---|---|---|
| PES fibre / pristine | 0, 0.06, 0.12, 0.24, 0.49, 0.98 | 1.00, 1.03, 1.48, 1.82, 1.85, 1.80 |
| PES fibre / field weathered | 0, 0.06, 0.12, 0.24, 0.49, 0.98 | 1.00, 1.01, 1.37, missing, 0.55, 0.39 |
| PP granule / pristine | 0, 0.3, 0.61, 1.22, 2.44, 4.88 | 1.00, 1.31, 1.59, 1.44, 1.39, 1.82 |
| PP granule / field weathered | 0, 0.3, 0.61, 1.22, 2.44, 4.88 | 1.00, 1.04, 0.58, 0.68, 0.57, 0.30 |

- Pristine polyester fibre conductivity rises at higher loading; the highest-loading weathered fibre point lies below its weathered control. A universal “microplastic always reduces permeability” statement is not supported.
- The source reports SD, n=3. Raw SDs are retained; uncertainty of normalised experimental means cannot be reconstructed fully without replicate/control covariance. Several weathered errorbars are large.
- Silt-loam packing and weathering can change structure and surfaces. The pristine/weathered comparison is not a direct calibration of our rigid-fibre length parameter or a unique degradation index.

## 3. Length and conditional trapping

[Cohen et al. (2025)](https://doi.org/10.1021/acs.est.5c12359), SI Table S2: exact count transcription, not plot digitisation.

| Fibre length (µm) | Trapped / analysed | Conditional trapped fraction |
|---|---:|---:|
| 20–50 | 10/40 | 25% |
| 50–80 | 30/40 | 75% |
| >80 | 39/40 | 97.5% |

- Supports length-dependent trapping in that experiment. Curved/flexible PP in a 2D device differs from our rigid PET body in 3D sand. Do not call the complementary fraction “release from the soil matrix.”

## 4. A directly observed sphere transport series

[Ameen et al. (2024)](https://doi.org/10.1002/jeq2.20618), Figure 3: 36 clearly identifiable interior circle markers digitised for 1-µm PS spheres, retaining the two plotted R1/R2 labels. The fitted dashed curves were excluded.
- Retain C/C0 and time; also calculate dimensionless throughput Qt/(AL) using the stated flow and column dimensions. This is **not PV** until divided by measured porosity. The selected points cover the rise/plateau/fall interior, not the complete tails; no cumulative recovery was integrated from them.
- Source-reported recovery is about 24.5% for the 1-µm spheres and 31% for roughly 1.4-µm fragments. This is injected-particle recovery, not initial-resident release, and the fragments are not fibres.
- The sphere/sand median size ratio is about 0.00105. Diffusion, attachment and solution chemistry may matter at this size; curve resemblance alone cannot establish validity of our nonadhesive rigid-body model.

## 5. Comparison against our existing evidence

| Existing output | What can be said now |
|---|---|
| Historical Stage31, 1 fibres, 0.00437% dry mass | Mean ratio 0.99714; range 0.99361–0.99848; 3 packings × 2 nested placements. |
| Historical Stage31, 2 fibres, 0.00874% dry mass | Mean ratio 0.99469; range 0.98750–0.99690; 3 packings × 2 nested placements. |
| Historical Stage31, 4 fibres, 0.01747% dry mass | Mean ratio 0.99026; range 0.98221–0.99540; 3 packings × 2 nested placements. |
| Corrected Stage134 sphere and AR4, one matched start | Both present at 0.5 s; finite numerical screen passed, but no population release curve or concentration response. |

**Important status distinction:** Stage113 later identified a persistent alternating mode in two archived Stage31 clean flow states. Historical Stage31 “passed” labels do not override that finding. The ratio summary above is archival context only, excluded from a claim of current experimental agreement. No repair or rerun is started by this comparison.

The defensible comparison today is a mechanism map: obstruction can lower conductivity; repacking/weathering can produce a different sign; fibre length can influence trapping. Our verified short-time trajectories are not yet enough to confirm a population-level experimental trend. Missing simulation outcomes stay missing rather than being fitted or inferred.

## 6. Dimensionless comparison rules

- Hydraulic response: Rk = K/K0; obstruction index B = 1 − Rk. For unchanged fluid properties, K/K0 = k/k0. A negative B is allowed and means enhancement.
- Concentration: preserve the reported mass basis. If w = mMP/(mMP + ms), solid-volume fraction is φMP = (w/ρMP)/[(w/ρMP)+(1−w)/ρs]. If c = mMP/ms, use (c/ρMP)/[(c/ρMP)+(1/ρs)]. Do not silently interchange these or infer unreported densities.
- Geometry: AR = fibre length/diameter; confinement ratios Lf/dthroat and df/dthroat; sphere ratio dMP/d50. Use actual paired measurements, not an invented common pore diameter. Aspect ratio alone does not capture curvature or flexibility.
- Transport time: t* = U t/L = Qt/(nAL) for constant mean interstitial U = Q/(nA). Ameen throughput Qt/(AL) is recorded separately because porosity was not extracted here. No fitted time shift or timescale.
- Release: FN(t*) = Nwhole-body-downstream(t*)/Ninitial-resident; a mass-based FM must use initial mass. Breakthrough C/Cin, injected recovery, conditional passage CDF and tracked-particle trapping are different observables and remain separate.
- Regime checks: Re = ρf |up−u| deq/μ, density ratio ρp/ρf, and settling ratio |ws|/U. Particle stiffness, friction/adhesion, curvature and dimensionless loading must also be stated if relevant. A dimensionless axis is not proof of dynamic similarity.

## Output and stopping point

- `measurements.json`: source coordinates, values, units, SD where reported, sensitivity envelopes, missingness and denominators.
- `simulation_comparison.json`: archival ratios plus source-bound current sentinel status, explicitly separated.
- `audit.json`: source/output hashes and checks. Originals and all simulation records remain unchanged.
- Next publication step is an evidence-led outline/caption plan using these distinctions. No calibration loop, new physics job, manuscript or publication figure has been started.
