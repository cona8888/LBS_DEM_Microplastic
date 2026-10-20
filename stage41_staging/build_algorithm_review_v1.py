"""Build the final audit from saved verification and timing evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stage41_evaluations"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    paths = {
        "contact": OUT / "contact_optimization_01/results.json",
        "geometry": OUT / "geometry_exact_verification_03/results.json",
        "manufactured": OUT / "trajectory_verification_03/results.json",
        "refinement": OUT / "matrix_replay_refinement_02/results.json",
        "profile": OUT / "matrix_profile_comparison_01/results.json",
        "coarse_diagnostic": OUT / "matrix_replay_verification_01/results.json",
    }
    data = {k: json.loads(p.read_text()) for k,p in paths.items()}
    accepted = {k: bool(data[k]["passed"]) for k in ("contact", "geometry", "manufactured", "refinement", "profile")}
    equivalence = all(v for k,v in data["refinement"]["checks"].items()
                      if k.endswith("_equivalent") or k.endswith("_health")
                      or k == "source_files_stable_during_run")
    optimization_verified = all(accepted[k] for k in ("contact", "geometry", "manufactured", "profile")) and equivalence
    source_checks = {}
    for kind in ("manufactured", "refinement", "profile"):
        for filename, digest in data[kind]["source_hashes"].items():
            source_checks[filename] = sha(filename) == digest
    if not all(source_checks.values()):
        raise RuntimeError("source files changed since final verification")
    rows = data["refinement"]["values"]["rows"]
    profile = data["profile"]["values"]["rows"][0]
    compared_keys = ("position_m", "orientation", "velocity_generalized", "steps",
                     "rejected", "history", "total_contact_iterations")
    saved_states_identical = all(
        row["pair"]["baseline"][key] == row["pair"]["candidate"][key]
        for row in [*rows, profile] for key in compared_keys)
    base, new = profile["pair"]["baseline"], profile["pair"]["candidate"]
    convergence = data["refinement"]["values"]["convergence"]
    coarse = data["coarse_diagnostic"]["values"]["convergence"]
    table = "\n".join(
        f"| {row['friction']:.1f} | {row['fraction']:.5f} | {row['pair']['baseline']['runtime_seconds']:.2f} | "
        f"{row['pair']['candidate']['runtime_seconds']:.2f} | {row['speedup']:.2f}x | "
        f"{row['endpoint_shift_m']:.3g} | {row['orientation_shift_rad']:.3g} |"
        for row in rows)
    convtable = "\n".join(
        f"| {row['friction']:.1f} | {row['fine_medium_shift_minor_radii']:.6g} | "
        f"{row['fine_medium_orientation_rad']:.6g} |" for row in convergence)
    decision = ("The implementation passes the declared code-equivalence, manufactured-event, and short real-state refinement gates."
                if all(accepted.values()) else
                "The law- and geometry-preserving optimization is verified, but the frictional trajectory still fails the predeclared orientation-refinement gate. Do not promote the full campaign."
                if optimization_verified else
                "The implementation has outstanding verification gates; use the per-suite results below and do not promote a campaign.")
    text = f"""# Algorithm review and optimization — 12 September 2026

{decision} It is a faster implementation of the existing prolate model, with corrected dwell and applicability checks. This is **not physical validation of PET release** and does not qualify a seven-pore-volume campaign.

## What changed and why

- **Preserved exact prolate geometry.** Swept collision searches reuse constant-motion factors and avoid calculating unused output normals. Contact queries cache closest points only at identical poses in immutable fixed grains. The closest-point equation, Brent tolerance, four sweep search intervals, periodic images, and penetration tolerance are unchanged.
- **Preserved cold Coulomb solution selection.** Contact frames/Jacobians are reused only during a frozen-pose inertial step; fixed tangential eigenvalues are computed once per contact solve instead of twice per contact per iteration. Every solve still starts from zero reactions, in the same order, with the same tolerances and 10,000-iteration ceiling. The compliance-dependent matrices are rebuilt every finite-Re iteration.
- **Corrected the meaning of dwell.** The earlier detector could treat slow contact as permanent trapping, ignore changes in bearing contacts, omit initial interval motion, and ignore accumulated rotation. The new monitor tracks both contact sets and a conservative surface-excursion bound. The trajectory rejects approach-only intervals from dwell credit by checking contact at both sampled endpoints. It continues after a dwell by default and can later exit. An optional early dwell stop is explicitly censored for later passage.
- **Closed diagnostic gaps.** Check Reynolds number before and after the step, and record exiting-step health and partial-interval dwell. Out-of-envelope motion returns `unresolved_model`; it is never counted as retention. Re <= 3 is the declared screening envelope, not hydrodynamic validation.
- **Made the implementation explicit.** The new trajectory imports the new components without rebinding older module globals. Final integration runs record transitive source hashes before and after execution and verify that sources stayed fixed. Earlier raw evidence remains intact.

Code: [trajectory](../stage41_staging/trajectory_optimized_v1.py), [geometry](../stage41_staging/geometry_exact_v1.py), [contact solver](../stage41_staging/inertial_contact_cold_optimized_v1.py), [dwell monitor](../stage41_staging/trap_event_v3.py). Reproduction: [run instructions](../stage41_staging/README.md). Frozen criteria: [research contract](RESEARCH_CONTRACT.md).

## Verified evidence

| Suite | Outcome | Evidence |
|---|---|---|
| Contact primitives | {'PASS' if accepted['contact'] else 'FAIL'}: 36 exact comparisons; difficult three-grain steps; unchanged failure behavior; prior 13-gate suite | [results](contact_optimization_01/results.json) |
| Exact geometry | {'PASS' if accepted['geometry'] else 'FAIL'}: 896 scalar cases, 900 poses, 1,000 queries, 32 sweeps; dense independent sweep sampling | [results](geometry_exact_verification_03/results.json) |
| Manufactured trajectory/events | {'PASS' if accepted['manufactured'] else 'FAIL'}: {len(data['manufactured']['checks'])} gates including delayed exit after dwell, contact onset, rotation, initial Re, and three timestep levels | [results](trajectory_verification_03/results.json) |
| Final paired real-state refinement | {'PASS' if accepted['refinement'] else 'FAIL'}: both friction values at three finer controls | [results](matrix_replay_refinement_02/results.json) |
| Original-start 0.02-PV comparison | {'PASS' if accepted['profile'] else 'FAIL'}: same physical inputs and historical numerical controls | [results](matrix_profile_comparison_01/results.json) |

The final real-state replay uses the archived difficult packing-2 state for 0.02 seconds. It compares baseline and candidate sequentially. Exact equality of saved poses, velocities, history rows, accepted/rejected step counts and total contact iterations across all final paired runs: **{saved_states_identical}**. Displacement fraction f and relaxation fraction 5f are refined together. They bound the integration step; these tests do not isolate the two controls or establish a formal convergence order.

| Friction | f | Baseline wall s | Optimized wall s | Speedup | Endpoint difference m | Orientation difference rad |
|---:|---:|---:|---:|---:|---:|---:|
{table}

The geometry primitive benchmark was 1.68x faster; contact-step medians were 2.05x (friction zero) and 1.74x (friction 0.3). Full-trajectory costs above are more relevant than those primitive timings. They are short local benchmarks, not a campaign cost guarantee.

## Numerical accuracy is a separate gate

The initial 0.1/0.05/0.025 refinement diagnostic failed the frictional orientation criterion: its fine/medium difference was {coarse[1]['fine_medium_orientation_rad']:.6g} rad, exceeding the predeclared 0.001-rad gate. Optimized and baseline paths still matched. That failure was retained, and the tolerance was not relaxed.

Final controls are 0.025/0.0125/0.00625. Fine-versus-medium differences are:

| Friction | Endpoint difference / minor radius | Orientation difference rad |
|---:|---:|---:|
{convtable}

The thresholds remain 0.01 minor radii and 0.001 rad. The frictional orientation difference still exceeds its gate. This is a failure of solution qualification shared by the baseline and optimized implementation, not a discrepancy introduced by optimization. The stricter frictional case takes far longer than the coarse replay despite the speed gain. Further uniform step reduction should not be launched as a production solution without a cost/accuracy pilot; a more accurate pose/contact integration scheme and subsequent verification may be needed.

These are verification criteria for this short case, not experimental uncertainty or a universal physical accuracy claim. Longer trajectories, other starts, both shapes, and packing replication still need solution verification; swept rotation also remains a bounded numerical search rather than a globally certified minimum for arbitrary motion. The historical default timestep controls are retained for comparison, not recommended as quantitatively qualified controls.

## Original-start performance

At historical controls, the original packing-2 AR4 body was followed for {data['profile']['values']['horizon_s']:.6f} s physical time (0.02 PV). Baseline wall time was **{base['runtime_seconds']:.2f} s**; optimized time was **{new['runtime_seconds']:.2f} s**, a **{profile['speedup']:.2f}x speedup**. Both statuses were `{base['status']}` / `{new['status']}`; endpoint difference was {profile['endpoint_shift_m']:.3g} m and orientation difference was {profile['orientation_shift_rad']:.3g} rad. Candidate steps: {new['steps']}; contact iterations: {new['total_contact_iterations']}. Minimum gap: {new['minimum_gap_m']:.6g} m; maximum Re: {new['max_reynolds']:.6g}; maximum momentum/contact residuals: {new['max_momentum_residual']:.3g} / {new['max_contact_residual']:.3g}.

Linear scaling of this candidate timing alone would be approximately {new['runtime_seconds']*350/3600:.2f} hours for one seven-PV path. This is an extrapolation, not a measured runtime, and finer controls/contact-state changes can substantially increase cost. The replicated campaign therefore remains computationally unqualified.

## Can this answer the study question?

| Intended claim | Current status | Required next evidence |
|---|---|---|
| Fixed fibres alter sand permeability | Separate existing fixed-solid DEM/LBM evidence; untouched here | Preserve its packing, resolution and external-benchmark limits |
| Shape affects conditional mobile passage/residence | Computational mechanism study is possible within declared assumptions | Tangential/rotational near-wall resistance, finite-body flow sampling, friction/roughness and gravity sensitivity; trajectory refinement across shapes/packings |
| Fraction released from contaminated soil | Not supported by this periodic-window model | Physical inlet/outlet, initially resident/mobile population and weights, independently specified detachment, and held-out recovery data |
| Migration changes permeability or causes clogging | Not supported by a frozen clean-sand velocity field | Flow recomputation as bodies obstruct pores, coupling/timescale and mass-balance verification, independent transient hydraulic comparison |

Do not replace the 400 by 100 micrometre prolate with an equal-dimension capsule as a speed shortcut: it raises volume, mass and buoyant weight by 37.5%, changing the controlled experiment. A capsule can be a separately qualified morphology model, with its own volume, inertia, curvature and drag.

The most consequential unqualified mechanisms are normal-only near-wall lubrication and pointwise sampling of a flow that varies over a finite body. Surface roughness and PET-sand friction remain physical uncertainty parameters; they must not be adjusted for speed. Added-mass and quasi-steady-rotation assumptions require trajectory-level bounds. Near-wall rotational resistance is a distinct physical contribution ([Cooley and O'Neill](https://doi.org/10.1093/imamat/4.2.163)); resolved collision studies demonstrate the need for targeted contact/lubrication benchmarks ([Costa et al.](https://arxiv.org/abs/1506.01880)). Neither source validates this prolate closure.

The [full scientific review](scientific_review_20260912.md) provides eight prioritized findings, primary sources and dimensional checks. The latest replicated far-field bound remains 8/192 sphere passages and 6/192 prolate passages, with 370/384 near-wall censored and 100% upper bounds; it cannot establish a morphology effect. See the [Stage 37 handoff](../stage37_evaluations/STAGE4_HANDOFF_20260912.md).

## Development audit trail

Geometry audit01 stopped at a JSON serialization error; audit02 found undefined-normal exception differences; audit03 corrected those and passed. Manufactured trajectory audit02 had a fixture that failed to reach contact because lubrication slowed approach; the forcing was corrected and audit03 now exercises contact onset and passes. Audit01 was an earlier, smaller manufactured suite. The first matrix replay is preserved as a provisional coarse diagnostic: it overlapped code development and lacks before/after source binding. Final refinement and profile runs verify source stability explicitly and supersede it for implementation qualification. No failed or provisional audit is represented as accepted evidence.

Original MATLAB and Stage 37–40 solver/evidence files were not changed. Stage 41 introduces a new verified implementation and review, with a deliberately bounded scientific claim.
"""
    report = OUT / "ALGORITHM_REVIEW.md"
    if report.exists():
        raise FileExistsError(report)
    report.write_text(text, encoding="utf-8")
    summary = {"accepted_suites": accepted, "all_accepted": all(accepted.values()),
               "code_optimization_verified": optimization_verified,
               "solution_refinement_qualified": accepted["refinement"],
               "source_hashes_match": all(source_checks.values()),
               "saved_states_and_counts_identical": saved_states_identical,
               "profile_speedup": profile["speedup"],
               "report_sha256": sha(report), "input_hashes": {k:sha(p) for k,p in paths.items()},
               "builder_sha256": sha(__file__),
               "claim": "verified optimization and bounded short-case numerics; no physical release validation"}
    (OUT / "review_manifest.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
