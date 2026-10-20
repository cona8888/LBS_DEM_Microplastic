from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stage35_outputs" / "stage35a_publication_evidence_synthesis_20260904" / "release_03"

INPUTS = {
    "stage31e_evaluation": ROOT
    / "stage31_evaluations"
    / "stage31e_replicated_nested_cpd2_gpu_20260826"
    / "gpu_evaluation_01"
    / "evaluation.json",
    "stage31f_evaluation": ROOT
    / "stage31_evaluations"
    / "stage31f_selected_replicated_cpd4_20260827"
    / "gpu_evaluation_02"
    / "evaluation.json",
    "stage34a_completion": ROOT
    / "stage34_literature"
    / "stage34a_literature_digitization_20260902"
    / "release_01"
    / "completion.json",
    "stage34a_report": ROOT
    / "stage34_literature"
    / "stage34a_literature_digitization_20260902"
    / "release_01"
    / "LITERATURE_BENCHMARK_REPORT.md",
    "stage34c_evaluation": ROOT
    / "stage34_evaluations"
    / "stage34c_cpd4_first_fragmentation_geometry_20260902"
    / "gpu_evaluation_02"
    / "evaluation.json",
    "stage35a_contract": ROOT
    / "stage35_staging"
    / "STAGE35A_PUBLICATION_EVIDENCE_SYNTHESIS_CONTRACT.md",
    "stage35a_builder": Path(__file__).resolve(),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    require(not OUT.exists(), f"Refusing to overwrite immutable release: {OUT}")
    for name, path in INPUTS.items():
        require(path.is_file(), f"Missing frozen input {name}: {path}")

    s31e = load_json(INPUTS["stage31e_evaluation"])
    s31f = load_json(INPUTS["stage31f_evaluation"])
    s34a = load_json(INPUTS["stage34a_completion"])
    s34c = load_json(INPUTS["stage34c_evaluation"])

    require(
        s31e.get("passed") is True and str(s31e.get("status", "")).startswith("passed_"),
        "Stage31E did not pass",
    )
    require(
        s31f.get("passed") is True and str(s31f.get("status", "")).startswith("passed_"),
        "Stage31F did not pass",
    )
    require(s34a.get("status") == "complete" and s34a.get("failure") is None, "Stage34A did not complete")
    require(
        s34c.get("passed") is True and str(s34c.get("status", "")).startswith("passed_"),
        "Stage34C did not pass",
    )

    OUT.mkdir(parents=True)

    concentration_rows: list[dict] = []
    mass_by_count: dict[int, float] = {}
    ratios_by_count: dict[int, list[float]] = {}
    for row in s31e["rows"]:
        count = int(row["fibre_count"])
        if count == 0:
            continue
        mass_by_count[count] = float(row["achieved_dry_mass_percent"])
        ratios_by_count.setdefault(count, []).append(float(row["paired_permeability_ratio"]))

    for count in sorted(ratios_by_count):
        values = ratios_by_count[count]
        summary = s31e["analysis"]["count_summaries"][str(count)]
        require(len(values) == 6, f"Expected six Stage31E observations for fibre count {count}")
        require(abs(statistics.mean(values) - float(summary["mean_ratio"])) < 1e-15, "Stage31E mean mismatch")
        concentration_rows.append(
            {
                "fibre_count": count,
                "achieved_dry_mass_percent": mass_by_count[count],
                "n_contexts": len(values),
                "mean_K_over_K0": statistics.mean(values),
                "sample_standard_deviation": statistics.stdev(values),
                "minimum_K_over_K0": min(values),
                "maximum_K_over_K0": max(values),
                "mean_reduction_percent": 100.0 * (1.0 - statistics.mean(values)),
                "individual_K_over_K0": ";".join(f"{value:.15g}" for value in values),
                "solver_resolution": "CPD2",
            }
        )

    selected_cpd4_max_shift = float(s31f["maximum_absolute_ratio_shift"])
    require(selected_cpd4_max_shift <= 0.002, "Stage31F selected CPD4 stability gate failed")

    fragmentation_rows: list[dict] = []
    promotion_threshold = 0.005
    families = [
        ("split2_minus_intact", "frag2_minus_frag1"),
        ("split3_minus_intact", "frag3_minus_frag1"),
        ("split3_minus_split2", "frag3_minus_frag2"),
    ]
    contexts = list(s34c["contrasts"].keys())
    require(len(contexts) == 4, "Expected four Stage34C contexts")
    promotion_results: dict[str, dict] = {}
    for publication_name, field in families:
        values = [float(s34c["contrasts"][context][field]) for context in contexts]
        positive = sum(value > 0 for value in values)
        negative = sum(value < 0 for value in values)
        sign_agreement = max(positive, negative)
        median_absolute = statistics.median(abs(value) for value in values)
        practical_count = sum(abs(value) >= promotion_threshold for value in values)
        passes = median_absolute >= promotion_threshold and sign_agreement >= 3
        promotion_results[publication_name] = {
            "median_absolute_shift": median_absolute,
            "sign_agreement_count": sign_agreement,
            "practical_context_count": practical_count,
            "passes_promotion_rule": passes,
        }
        for context, value in zip(contexts, values):
            fragmentation_rows.append(
                {
                    "contrast": publication_name,
                    "context": context,
                    "delta_K_over_K0": value,
                    "absolute_delta_K_over_K0": abs(value),
                    "meets_practical_threshold": abs(value) >= promotion_threshold,
                    "median_absolute_shift_for_contrast": median_absolute,
                    "majority_sign_agreement_count": sign_agreement,
                    "contrast_passes_promotion_rule": passes,
                    "solver_resolution": "CPD4",
                }
            )

    any_fragmentation_promotion = any(item["passes_promotion_rule"] for item in promotion_results.values())
    require(not any_fragmentation_promotion, "Fragmentation promotion unexpectedly passed")

    lit = s34a["key_results"]
    claim_rows = [
        {
            "topic": "Clean LBS hydraulic magnitude",
            "evidence_status": "supported as bounded external benchmark",
            "publication_wording": "The frozen clean-sand model is consistent with the order of magnitude of digitized Leighton Buzzard Sand conductivity at e=0.744.",
            "boundary": "Not a matched experiment or direct validation.",
        },
        {
            "topic": "Low-dose fibre count",
            "evidence_status": "replicated CPD2 effect with selected CPD4 stability",
            "publication_wording": "Mean K/K0 decreased across the tested 1, 2 and 4-fibre categories in all six packing/placement blocks, while effect magnitude varied among contexts.",
            "boundary": "Fibre count is categorical and the range is 0.00437-0.01747 dry-mass percent; no universal concentration law.",
        },
        {
            "topic": "Numerical resolution",
            "evidence_status": "selected response stable",
            "publication_wording": f"Selected CPD2-to-CPD4 K/K0 shifts were at most {selected_cpd4_max_shift:.6f}.",
            "boundary": "This verifies selected numerical contrasts, not absolute field permeability.",
        },
        {
            "topic": "Idealized fragmentation",
            "evidence_status": "context-dependent; promotion gate failed",
            "publication_wording": "At fixed solver-resolved PET volume, split-state effects changed sign among matched contexts and their median absolute shifts remained below 0.005.",
            "boundary": "No universal fibre-length effect and no inference of chemical degradation.",
        },
        {
            "topic": "External PET comparison",
            "evidence_status": "qualitative context only",
            "publication_wording": "A primary sandy-soil study at approximately 0.4 wt% PET reported the same obstruction direction but a substantially larger reduction than the model.",
            "boundary": "Different soil, fibre morphology, preparation and boundaries preclude calibration.",
        },
    ]

    synthesis = {
        "schema": "pet.stage35a-publication-evidence-synthesis.v1",
        "status": "complete",
        "completed_at": "2026-09-04",
        "research_scope": "computational fixed-solid DEM/LBM evidence synthesis; no new simulation executed",
        "questions": [
            "clean-sand external magnitude plausibility",
            "replicated low-concentration fibre-count response",
            "selected CPD2-to-CPD4 numerical stability",
            "fragmentation promotion decision",
        ],
        "clean_literature_benchmark": {
            "target_void_ratio": 0.744,
            "literature_K20_m_per_s": lit["clean_literature_K20_at_e_0p744_m_s"],
            "declared_digitization_extrapolation_uncertainty_m_per_s": lit[
                "clean_literature_declared_digitization_extrapolation_uncertainty_m_s"
            ],
            "model_mean_K20_m_per_s": lit["clean_model_mean_K20_m_s"],
            "model_mean_difference_percent": lit["clean_model_mean_difference_percent"],
            "model_realization_difference_percent_range": lit[
                "clean_model_realization_difference_percent_range"
            ],
            "interpretation": "bounded external magnitude benchmark, not direct experimental validation",
        },
        "replicated_low_concentration": {
            "resolution": "CPD2",
            "contexts_per_nonzero_count": 6,
            "count_summaries": concentration_rows,
            "all_six_blocks_strictly_decreasing_across_1_2_4": all(
                item["strictly_decreasing_observed"]
                for item in s31e["analysis"]["descriptive_monotonicity_only"].values()
            ),
            "interpretation": "replicated categorical trend over the tested low-dose range; context variability retained",
        },
        "selected_resolution_confirmation": {
            "resolution": "CPD4",
            "maximum_absolute_CPD2_to_CPD4_ratio_shift": selected_cpd4_max_shift,
            "predeclared_limit": 0.002,
            "passed": selected_cpd4_max_shift <= 0.002,
        },
        "fragmentation": {
            "resolution": "CPD4",
            "fixed_quantity": "solver-resolved PET volume",
            "practical_threshold_absolute_ratio": promotion_threshold,
            "promotion_rule": "median absolute paired shift >= 0.005 and at least 3/4 signs agree",
            "contrast_results": promotion_results,
            "any_contrast_passes_promotion_rule": any_fragmentation_promotion,
            "cpd6_authorized": False,
            "concentration_by_fragmentation_campaign_authorized": False,
            "interpretation": "context-dependent response below the preregistered median practical-effect threshold",
        },
        "external_pet_context": {
            "model_concentration_dry_mass_percent": lit["pet_model_concentration_wt_percent"],
            "model_K_over_K0": lit["pet_model_K_over_K0"],
            "neubert_sandy_soil_K_over_K0": lit["pet_neubert_sandy_soil_K_over_K0"],
            "reduction_gap_percentage_points": lit["pet_reduction_gap_percentage_points"],
            "interpretation": "same obstruction direction in one sandy soil; magnitude is not directly comparable",
        },
        "decision": {
            "new_gpu_run_started": False,
            "freeze_fragmentation_branch": True,
            "next_action": "integrate the bounded results and limitations into the manuscript; any new physics requires a separate contract",
        },
        "claim_boundary": [row for row in claim_rows],
        "input_sha256": {name: sha256(path) for name, path in INPUTS.items()},
    }

    write_csv(
        OUT / "concentration_summary.csv",
        [
            "fibre_count",
            "achieved_dry_mass_percent",
            "n_contexts",
            "mean_K_over_K0",
            "sample_standard_deviation",
            "minimum_K_over_K0",
            "maximum_K_over_K0",
            "mean_reduction_percent",
            "individual_K_over_K0",
            "solver_resolution",
        ],
        concentration_rows,
    )
    write_csv(
        OUT / "fragmentation_summary.csv",
        [
            "contrast",
            "context",
            "delta_K_over_K0",
            "absolute_delta_K_over_K0",
            "meets_practical_threshold",
            "median_absolute_shift_for_contrast",
            "majority_sign_agreement_count",
            "contrast_passes_promotion_rule",
            "solver_resolution",
        ],
        fragmentation_rows,
    )
    write_csv(
        OUT / "claim_matrix.csv",
        ["topic", "evidence_status", "publication_wording", "boundary"],
        claim_rows,
    )
    dump_json(OUT / "synthesis.json", synthesis)

    manuscript = f"""# Stage35A manuscript-ready results and claim boundary

## Results

The frozen clean Leighton Buzzard Sand model gave a mean hydraulic conductivity of `{lit['clean_model_mean_K20_m_s']:.4e} m/s` at the target void ratio, `{lit['clean_model_mean_difference_percent']:+.2f}%` relative to the digitized primary-literature value of `{lit['clean_literature_K20_at_e_0p744_m_s']:.4e} m/s`. The three modeled realizations spanned `{lit['clean_model_realization_difference_percent_range'][0]:+.2f}%` to `{lit['clean_model_realization_difference_percent_range'][1]:+.2f}%` relative to that comparator. This is an external magnitude benchmark, not a matched experimental validation.

Across six matched packing/placement contexts, mean CPD2 `K/K0` was `{concentration_rows[0]['mean_K_over_K0']:.5f}` at one fibre (`{concentration_rows[0]['achieved_dry_mass_percent']:.5f} dry-mass %`), `{concentration_rows[1]['mean_K_over_K0']:.5f}` at two fibres (`{concentration_rows[1]['achieved_dry_mass_percent']:.5f}%`), and `{concentration_rows[2]['mean_K_over_K0']:.5f}` at four fibres (`{concentration_rows[2]['achieved_dry_mass_percent']:.5f}%`). All six blocks showed decreasing `K/K0` across the tested one-, two-, and four-fibre categories, while the spread among contexts increased with fibre count. Selected CPD4 confirmation changed the paired ratios by at most `{selected_cpd4_max_shift:.6f}`, supporting numerical stability of those contrasts.

At fixed solver-resolved PET volume, idealized fragmentation did not produce a context-stable practical response. The median absolute CPD4 shifts were `{promotion_results['split2_minus_intact']['median_absolute_shift']:.6f}` for split-2 minus intact, `{promotion_results['split3_minus_intact']['median_absolute_shift']:.6f}` for split-3 minus intact, and `{promotion_results['split3_minus_split2']['median_absolute_shift']:.6f}` for split-3 minus split-2. Although each contrast had a three-to-one majority sign, none reached the preregistered median threshold of `0.005`; only one of four contexts reached the individual practical threshold for either split state relative to intact. The CPD6 and concentration-by-fragmentation branches are therefore not promoted.

## External PET context

At approximately `0.4 wt%`, the fixed-geometry model yielded `K/K0={lit['pet_model_K_over_K0']:.3f}`, whereas Neubert et al. reported `K/K0={lit['pet_neubert_sandy_soil_K_over_K0']:.2f}` for an 87%-sand Albic Luvisol. The shared obstruction direction is qualitative context only: the `{lit['pet_reduction_gap_percentage_points']:.1f}` percentage-point reduction gap and differences in soil, fibre morphology, preparation, and hydraulic boundaries preclude direct calibration.

## Publication claim

Within a fixed-solid computational system, increasing modelled PET-fibre count produced a reproducible low-dose reduction in relative permeability, with magnitude controlled by packing and placement. Selected contrasts were stable under CPD4 refinement. By contrast, shortening an equal resolved PET volume into two or three straight fragments produced sign-changing, sub-threshold shifts across contexts. Fibre shortening can therefore be discussed as an idealized fragmentation phenotype, but not as a universal length law or evidence of chemical degradation.

## Evidence boundary

Use **numerically verified and externally benchmarked**, not **experimentally validated**. Do not infer field permeability, molecular PET degradation, migration, clogging, deformation, transient behavior, or two-way coupling from these results.

Primary literature context: Hird, Ni and Guymer (2006), Environment Agency report SC020074; Neubert et al. (2025), DOI `10.1002/vzj2.70044`.
"""
    (OUT / "MANUSCRIPT_RESULTS.md").write_text(manuscript, encoding="utf-8", newline="\n")

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "figure.facecolor": "#F7F4EE",
            "axes.facecolor": "#FCFBF8",
        }
    )
    fig = plt.figure(figsize=(13.2, 8.1), constrained_layout=False)
    grid = fig.add_gridspec(2, 3, left=0.06, right=0.97, top=0.84, bottom=0.14, wspace=0.31, hspace=0.36)
    ax_a = fig.add_subplot(grid[0, 0])
    ax_b = fig.add_subplot(grid[0, 1:])
    ax_c = fig.add_subplot(grid[1, 0:2])
    ax_d = fig.add_subplot(grid[1, 2])

    navy = "#17324D"
    teal = "#218380"
    coral = "#E85D4A"
    gold = "#D6A84B"
    grey = "#69737D"
    green = "#3B7A57"

    fig.text(0.06, 0.945, "From clean-sand benchmark to a bounded microfibre claim", fontsize=22, weight="bold", color=navy)
    fig.text(
        0.06,
        0.900,
        "Immutable synthesis of primary literature, replicated CPD2 screening, selected CPD4 confirmation, and fragmentation decision",
        fontsize=11,
        color=grey,
    )
    fig.text(0.97, 0.945, "STAGE 35A", ha="right", fontsize=11, weight="bold", color=teal)
    fig.text(0.97, 0.910, "No new simulation run", ha="right", fontsize=9.5, color=grey)

    # A: clean benchmark
    clean_values = [lit["clean_literature_K20_at_e_0p744_m_s"] * 1e3, lit["clean_model_mean_K20_m_s"] * 1e3]
    bars = ax_a.bar([0, 1], clean_values, color=[gold, teal], width=0.62)
    ax_a.errorbar(
        [0],
        [clean_values[0]],
        yerr=[lit["clean_literature_declared_digitization_extrapolation_uncertainty_m_s"] * 1e3],
        color=navy,
        capsize=4,
        lw=1.4,
    )
    ax_a.set_xticks([0, 1], ["Digitized\nliterature", "Frozen model\nmean"])
    ax_a.set_ylabel("$K_{20}$  (10$^{-3}$ m s$^{-1}$)")
    ax_a.set_title("A  Clean LBS magnitude", loc="left", weight="bold", color=navy)
    ax_a.set_ylim(0, 9.5)
    ax_a.grid(axis="y", color="#D9D5CE", lw=0.7, alpha=0.8)
    ax_a.set_axisbelow(True)
    for bar, value in zip(bars, clean_values):
        ax_a.text(bar.get_x() + bar.get_width() / 2, value + 0.25, f"{value:.2f}", ha="center", weight="bold", color=navy)
    ax_a.text(0.5, 0.94, f"model {lit['clean_model_mean_difference_percent']:+.2f}%", transform=ax_a.transAxes, ha="center", va="top", color=grey)

    # B: replicated low-dose response
    rng = np.random.default_rng(3501)
    colors = {1: "#6CB6A8", 2: "#287D8E", 4: navy}
    for row in concentration_rows:
        count = int(row["fibre_count"])
        x = float(row["achieved_dry_mass_percent"])
        values = np.array(ratios_by_count[count])
        jitter = rng.normal(0, 0.00018, size=len(values))
        ax_b.scatter(x + jitter, values, s=33, color=colors[count], alpha=0.68, edgecolor="white", linewidth=0.5, zorder=3)
        ax_b.errorbar(
            x,
            float(row["mean_K_over_K0"]),
            yerr=float(row["sample_standard_deviation"]),
            fmt="o",
            ms=7,
            capsize=4,
            color=coral,
            mec="white",
            mew=0.8,
            zorder=5,
        )
        ax_b.text(x, float(row["minimum_K_over_K0"]) - 0.0012, f"{count} fibre{'s' if count > 1 else ''}", ha="center", va="top", fontsize=8.5, color=navy)
    ax_b.plot(
        [row["achieved_dry_mass_percent"] for row in concentration_rows],
        [row["mean_K_over_K0"] for row in concentration_rows],
        color=coral,
        lw=1.5,
        zorder=4,
    )
    ax_b.axhline(1.0, color=grey, lw=1, ls="--")
    ax_b.set_xlim(0.0025, 0.0192)
    ax_b.set_ylim(0.979, 1.0015)
    ax_b.set_xlabel("Achieved PET dry-mass concentration (%)")
    ax_b.set_ylabel("Paired relative permeability, $K/K_0$")
    ax_b.set_title("B  Replicated low-dose fibre-count response (CPD2)", loc="left", weight="bold", color=navy)
    ax_b.grid(color="#D9D5CE", lw=0.7, alpha=0.8)
    ax_b.set_axisbelow(True)
    legend = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=navy, markeredgecolor="white", markersize=7, label="six packing/placement contexts"),
        Line2D([0], [0], marker="o", color=coral, markerfacecolor=coral, markersize=6, label="mean ± sample SD"),
    ]
    ax_b.legend(handles=legend, frameon=False, loc="lower left", fontsize=8.5)
    ax_b.text(0.99, 0.97, f"selected CPD4 max |shift| = {selected_cpd4_max_shift:.6f}", transform=ax_b.transAxes, ha="right", va="top", color=green, weight="bold")

    # C: fragmentation contrasts
    labels = ["split-2 − intact", "split-3 − intact", "split-3 − split-2"]
    context_colors = ["#2364AA", "#3DA5D9", "#73BFB8", "#F18F01"]
    offsets = [-0.24, -0.08, 0.08, 0.24]
    for family_index, ((publication_name, field), label) in enumerate(zip(families, labels)):
        values = [float(s34c["contrasts"][context][field]) for context in contexts]
        for j, value in enumerate(values):
            ax_c.scatter(family_index + offsets[j], value, s=46, color=context_colors[j], edgecolor="white", linewidth=0.6, zorder=3)
        median_abs = promotion_results[publication_name]["median_absolute_shift"]
        ax_c.text(family_index, -0.00865, f"median |Δ|\n{median_abs:.4f}", ha="center", va="bottom", fontsize=8.2, color=grey)
    ax_c.axhspan(-promotion_threshold, promotion_threshold, color="#DCE8E2", alpha=0.72, zorder=0)
    ax_c.axhline(promotion_threshold, color=green, ls="--", lw=1.1)
    ax_c.axhline(-promotion_threshold, color=green, ls="--", lw=1.1)
    ax_c.axhline(0, color=navy, lw=1)
    ax_c.set_xticks(range(3), labels)
    ax_c.set_ylabel("Paired shift, Δ$(K/K_0)$")
    ax_c.set_ylim(-0.0095, 0.0095)
    ax_c.set_title("C  Idealized fragmentation is context-dependent (CPD4)", loc="left", weight="bold", color=navy)
    ax_c.grid(axis="y", color="#D9D5CE", lw=0.7, alpha=0.8)
    ax_c.set_axisbelow(True)
    ax_c.text(0.99, 0.96, "promotion requires median |Δ| ≥ 0.005\nand ≥ 3/4 signs agree", transform=ax_c.transAxes, ha="right", va="top", fontsize=8.6, color=green, weight="bold")
    context_legend = [Line2D([0], [0], marker="o", color="none", markerfacecolor=color, markersize=7, label=context.replace("n216_", "")) for context, color in zip(contexts, context_colors)]
    ax_c.legend(handles=context_legend, frameon=False, ncol=4, loc="upper left", bbox_to_anchor=(0, 0.89), fontsize=8)

    # D: decision panel
    ax_d.axis("off")
    ax_d.set_title("D  Evidence decision", loc="left", weight="bold", color=navy, pad=8)
    decision_lines = [
        ("SUPPORTED", green, "Clean-sand magnitude benchmark"),
        ("SUPPORTED", green, "Replicated low-dose obstruction"),
        ("VERIFIED", teal, "Selected CPD2→CPD4 stability"),
        ("NOT PROMOTED", coral, "CPD6 fragmentation"),
        ("NOT PROMOTED", coral, "Concentration × fragmentation"),
    ]
    y = 0.92
    for status, color, description in decision_lines:
        ax_d.text(0.0, y, status, transform=ax_d.transAxes, fontsize=8.0, weight="bold", color=color, va="top")
        ax_d.text(0.0, y - 0.058, description, transform=ax_d.transAxes, fontsize=9.0, color=navy, va="top")
        y -= 0.168
    ax_d.text(
        0.0,
        0.035,
        "Boundary: no experimental validation,\nchemical-degradation inference, or field transfer.",
        transform=ax_d.transAxes,
        fontsize=7.7,
        color=grey,
        va="bottom",
        linespacing=1.2,
    )

    fig.text(
        0.06,
        0.071,
        "Publication claim  •  In fixed-solid pore geometries, increasing fibre count reduced K/K₀ over the tested low-dose range;",
        fontsize=9.9,
        color=navy,
        weight="bold",
    )
    fig.text(
        0.06,
        0.046,
        "packing and placement controlled magnitude. Equal-volume fragmentation did not yield a robust length law.",
        fontsize=9.9,
        color=navy,
        weight="bold",
    )
    fig.text(
        0.06,
        0.017,
        "Sources: Hird, Ni & Guymer (2006), EA SC020074; Neubert et al. (2025), doi:10.1002/vzj2.70044. Points are model realizations; literature comparisons are contextual, not calibration.",
        fontsize=8.2,
        color=grey,
    )

    png = OUT / "stage35a_publication_evidence_synthesis.png"
    svg = OUT / "stage35a_publication_evidence_synthesis.svg"
    fig.savefig(png, dpi=220, facecolor=fig.get_facecolor())
    fig.savefig(svg, facecolor=fig.get_facecolor())
    plt.close(fig)

    artifact_names = [
        "synthesis.json",
        "concentration_summary.csv",
        "fragmentation_summary.csv",
        "claim_matrix.csv",
        "MANUSCRIPT_RESULTS.md",
        "stage35a_publication_evidence_synthesis.png",
        "stage35a_publication_evidence_synthesis.svg",
    ]
    completion = {
        "schema": "pet.stage35a-publication-evidence-synthesis-completion.v1",
        "status": "complete",
        "completed_at": "2026-09-04",
        "failure": None,
        "checks": {
            "all_frozen_inputs_passed": True,
            "all_inputs_hash_bound": True,
            "stage31e_has_six_contexts_per_nonzero_count": True,
            "stage31f_max_ratio_shift_le_0p002": selected_cpd4_max_shift <= 0.002,
            "fragmentation_medians_recomputed": True,
            "no_fragmentation_contrast_passes_promotion_rule": not any_fragmentation_promotion,
            "cpd6_not_authorized": True,
            "concentration_fragmentation_not_authorized": True,
            "no_new_simulation_executed": True,
            "claim_boundary_preserved": True,
        },
        "key_results": {
            "clean_model_difference_percent": lit["clean_model_mean_difference_percent"],
            "count_mean_K_over_K0": {str(row["fibre_count"]): row["mean_K_over_K0"] for row in concentration_rows},
            "selected_CPD4_max_absolute_ratio_shift": selected_cpd4_max_shift,
            "fragmentation_promotion": promotion_results,
        },
        "input_sha256": synthesis["input_sha256"],
        "artifact_sha256": {name: sha256(OUT / name) for name in artifact_names},
        "next_stage": "manuscript integration only; a new physics campaign requires a separate explicit contract",
    }
    dump_json(OUT / "completion.json", completion)
    print(json.dumps({"status": "complete", "output": str(OUT), "completion_sha256": sha256(OUT / "completion.json")}, indent=2))


if __name__ == "__main__":
    main()
