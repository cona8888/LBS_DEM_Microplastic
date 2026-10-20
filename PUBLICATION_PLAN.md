# Publication plan — shape-aware microplastic motion in saturated sand

Updated 17 September 2026. Outline and proposed captions only: no manuscript, figures, parameter fitting or new simulations.

**Evidence-status update — 6 October 2026:** Stage219 has five complete 0.1-PV observations and one interrupted fibre observation, with no campaign terminal evaluation. This is two placements at one packing/flow with numerical refinements. Do not present it as six independent samples, a completed verification campaign, a population release curve or an established shape ranking. Use the [master plan](MASTER_PLAN.md) for the recovery and inference gates and the [interruption review](stage219_evaluations/normal_gap_campaign_20261001/interruption_review_20261006_01/results.json) for the saved status. The original outline below remains a proposed publication structure.

**Numerical-evidence update:** the [Stage220 full-path screen](stage220_evaluations/checkpoint_recovery_20261006/existing_pair_screen_01/results.json) passes the original selected/fine position, orientation, endpoint/mean velocity, dwell and terminal checks for both sample-0 shapes over 4.682166803 s. The [checkpoint restart test](stage220_evaluations/checkpoint_recovery_20261006/restart_qualification_01/results.json) is exact, and the missing sample-124 fibre has a separate continuation. These support bounded numerical reproducibility and accuracy statements. Combined successor integrity/comparison evaluation remains pending; there is still no population shape or flow inference or empirical validation.

**Verified reference update — 7 October 2026:** the [Stage220 successor evaluation](stage220_evaluations/checkpoint_recovery_20261006/combined_evaluation_01/results.json) passed the original six-observation and both sample-0 full-path gates using authenticated inherited records and explicit recovery lineage. All observations are `present_at_horizon`; original Stage219 remains interrupted. The [complete cost ledger](stage221_evaluations/cost_review_20261007/complete_reference_02/results.json) records the difficult fibre's 22.54 producer hours over 4.682 s. The new bounded coarser-timestep investigation is active, not yet qualified over the full path. These are finite numerical verification and cost results, not population shape/flow trends, full-horizon spatial accuracy or empirical validation. The dated October-6 pending statuses above are historical.

## Paper position

- **Working title:** *Shape-aware pore-scale modelling of microplastic motion in saturated sand: numerical verification and literature-based comparisons*.
- **Audience:** geotechnical researchers studying porous-media transport and contamination. Do not imply demonstrated changes in soil strength, deformation or consolidation.
- **Question:** what does an elongated particle representation preserve that a spherical approximation omits, and what motion can the verified model currently resolve?
- **Contribution to establish:** controlled equal-volume sphere/prolate comparisons, explicit contact and orientation response, transparent numerical error and computational cost. Neither first-ever fibre modelling nor computational superiority is established by the present literature screen.
- **Comparison policy:** fixed physical parameters; physically defined normalisation; report agreement, disagreement and unresolved comparisons. No tuning to make published curves coincide.
- **Current readiness:** sufficient for an evidence-led outline and methods-focused framing; insufficient for a general shape/flow effect on population release or an experimentally validated permeability law. Literature context alone does not establish a simulated trend.

## Proposed contents

1. **Introduction: morphology and geotechnical relevance**
   - Textile-derived particles can be elongated; source morphology motivates a shape-aware representation. Avoid “most studies use spheres” without a systematic review.
   - Distinguish rigid elongation from flexible-fibre behaviour. Length is a morphology variable, not a unique chemical-degradation measure.
2. **Physical model and controlled comparison**
   - Fixed saturated sand, prescribed steady flow, dilute independent particle trajectories; equal-volume sphere and rigid AR4 prolate.
   - State gravity, fluid/material properties, actual contact and hydrodynamic laws, admissible starting positions, periodic continuation and the whole-body downstream observation plane.
   - Exclude bending, fraying, chemical ageing, adhesion, mobile sand and particle-induced flow feedback from the present model claims.
3. **Numerical method, verification and cost**
   - Geometry/contact checks, steady flow qualification, timestep and CPD4/CPD6 response comparisons, checkpoint reproducibility and measured runtime.
   - Show finite numerical screening budgets; do not equate them with asymptotic convergence or experimental validation. No new precision campaign is proposed here.
4. **Dimensionless observables and literature processing**
   - Use aspect ratio, equal-volume size, confinement where measured, density ratio, mean-flow and slip Reynolds numbers, and advective time Ut/L.
   - Keep K/K0, C/C0, injected recovery, tracked-fibre trapping and initial-resident export as distinct observables. Retain units, source coordinates, missing values and uncertainty.
5. **Results supported by the current archive**
   - Verified short-time sphere/prolate response for the matched seed/start; state the 0.5-s horizon and its limited sampling scope.
   - Normalised literature trends: conductivity reduction and enhancement, length-conditioned trapping, and sphere breakthrough. These are separate experimental contexts, not one collapsed validation curve.
6. **Discussion: mechanisms, discrepancies and applicability**
   - Discuss geometric constraint and orientation as mechanisms to test; distinguish them from repacking, weathering, attachment and flexibility in the literature.
   - Explain what fixed geometry and one-way forcing cannot predict. Separate model-form uncertainty, numerical sensitivity, sampling variability and digitisation uncertainty.
7. **Conclusions and reproducibility**
   - Conclude only from the qualified numerical observations and explicitly labelled literature evidence. Report absent release evidence rather than inferring retention from unfinished motion.
   - Provide frozen parameters, source/data citations, extraction code and evidence identifiers. No claim that the study is submission-ready solely because this outline is complete.

## Proposed figures and caption briefs — not generated

- **Figure 1 — Model geometry and comparison contract.** “Fixed sand geometry and equal-volume spherical and rigid prolate microplastics. The schematic defines particle dimensions, gravity and flow directions, common-admissible initial placement, periodic continuation and the downstream observation plane. The prolate represents elongation, not flexible textile-fibre deformation.”
  - Evidence: current frozen designs. Do not reuse the historical 37-node fibre illustration as the current mobile-body algorithm. Exclude the PET preparation slides from an experimental-results section.
- **Figure 2 — Numerical verification at the reported endpoint.** “Timestep and spatial-resolution sensitivity of matched sphere and AR4 responses at 0.5 s. Position, orientation and velocity differences are compared with the declared finite screening budgets; computational cost is reported separately. These checks qualify the selected numerical response, not population release or experimental predictive accuracy.”
  - Evidence: Stage134 and its bound prior evaluations. Combined position allowances: 0.01853 and 0.01664 minor radii, respectively, against 0.02; not statistical confidence intervals.
- **Figure 3 — Matched short-time motion.** “Sphere and prolate trajectories and contact/orientation diagnostics from the same qualified packing and initial centre at fixed forcing. Both bodies remain in the observation window at 0.5 s. This single-start comparison illustrates resolved motion and does not estimate a population export fraction or universal shape ranking.”
  - Evidence: bound CPD6 records. Inspect trajectory units and diagnostic definitions before drawing; do not turn the sphere’s arbitrary orientation axis into a physical shape metric.
- **Figure 4 — Literature hydraulic-response context.** “Control-normalised conductivity from Aminzadeh et al. and Yu et al., separated by matrix, polymer and weathering condition. Source concentrations retain their reported mass basis. Digitisation sensitivity and reported experimental SD are distinguished; missing values are not interpolated. The panels retain both conductivity reduction and enhancement.”
  - Evidence: 18 raster bars and 23 vector-derived means. Some zero controls repeat. No historical Stage31 simulation overlay as currently qualified evidence.
- **Figure 5 — Distinct transport and trapping observables.** “Published fibre-trapping counts by length class and observed sphere breakthrough markers are shown in separate panels with their own denominators and experimental conditions. The sphere data are a selected interior subset, not a complete recovery integral. Neither panel is an initial-resident matrix-release measurement.”
  - Evidence: Cohen Table S2 and 36 Ameen observed markers. Use length-bin categories, including the open >80-µm bin; no invented bin midpoint or fitted transport curves.
- **Not in the current figure set:** a simulated population-release curve, a validated concentration–permeability curve, or a degradation–release law. These require missing outcomes or physics, not parameter fitting to existing literature.

## Proposed tables

- **Table 1 — Model assumptions and scales:** geometry, equal-volume dimensions, fluid/particle properties, contact assumptions, flow/boundaries, omitted mechanisms and dimensionless groups. Label inputs as prescribed or source-derived, not calibrated.
- **Table 2 — Literature comparability:** matrix, polymer, shape/size, loading basis, preparation, flow, observable/denominator, available uncertainty and applicable comparison level.
- **Table 3 — Evidence and claim limits:** numerical checks and cost, one-start sampling limit, source digitisation quality, unavailable release outcomes, and historical results excluded from current claims.

## Authoring rules and next action

- Keep permeability context secondary to the current transport model. A prescribed frozen flow cannot predict evolving conductivity or clogging.
- Earlier fixed-fibre hydraulic studies and current rigid-prolate transport are different model versions. The later alternating-flow-mode finding prevents automatic reuse of Stage31 hydraulic passes as qualified comparisons.
- No new experiments are part of this paper plan. PET treatment images may motivate geometry, but are not hydraulic measurements or a calibrated degradation law.
- The DEM research review keeps numerical verification, literature trend consistency and physical validation separate; it does not add a calibration requirement.
- **Source selection completed:** [panel evidence index](C:/MATDEM_MICROPLASTIC/publication_evidence_index.json) identifies the current records, data selections and remaining figure-specific checks. No additional simulation is launched by this plan. If population release remains a headline objective, that result is still missing; literature normalisation cannot supply it.

## Evidence index

- [Digitised data and comparison](C:/MATDEM_MICROPLASTIC/literature_comparison_20260917/comparison_02/TREND_COMPARISON.md), [measurements](C:/MATDEM_MICROPLASTIC/literature_comparison_20260917/comparison_02/measurements.json), [source audit](C:/MATDEM_MICROPLASTIC/literature_comparison_20260917/comparison_02/audit.json).
- [Current numerical evaluation](C:/MATDEM_MICROPLASTIC/stage134_evaluations/sphere_combined_budget_refinement_20260916/independent_evaluation_01/results.json), [source-bound simulation summary](C:/MATDEM_MICROPLASTIC/literature_comparison_20260917/comparison_02/simulation_comparison.json).
- Primary literature: [Aminzadeh 2025](https://doi.org/10.1038/s41598-025-30476-6), [Yu 2023](https://doi.org/10.1021/acs.est.2c09822), [Cohen 2025](https://doi.org/10.1021/acs.est.5c12359), [Ameen 2024](https://doi.org/10.1002/jeq2.20618).
- Historical [morphology brief](C:/MATDEM_MICROPLASTIC/stage35_publication/stage35c_fibre_morphology_rationale_20260905/release_01/MORPHOLOGY_PUBLICATION_BRIEF.md): motivation and prior-art context only; its old hydraulic-readiness wording does not supersede later findings. Original records and MASTER_PLAN.md remain unchanged.
