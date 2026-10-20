"""Benchmark Stage36CT against published transport endpoints without conflating observables."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "stage36_evaluations/stage36ct_matrix_release_evaluation_20260911/evaluation_01"
LIT_DIR = ROOT / "stage36_evaluations/literature_sphere_fibre_20260909"
GEOM = ROOT / "stage27_designs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/geometry_01/clean/geometry_cpd4.npz"
OUT = ROOT / "stage36_evaluations/stage36cu_external_release_benchmark_20260911/evaluation_01"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


OUT.mkdir(parents=True, exist_ok=False)
model_path = MODEL_DIR / "results.json"
literature_path = LIT_DIR / "published_endpoints.json"
model = json.loads(model_path.read_text())
literature = json.loads(literature_path.read_text())
assert model["passed"] is True

ameen = [
    x
    for x in literature["observations"]
    if x.get("doi") == "10.1002/jeq2.20618"
    and x.get("grain_range_mm") == [0.6, 1.3]
]
assert len(ameen) == 1
ameen = ameen[0]

with np.load(GEOM) as geom:
    diameters_mm = 2.0 * geom["sand_radii_m"] * 1e3

sphere_bound = model["all_start_release_bounds"]["sphere"]
fibre_bound = model["all_start_release_bounds"]["prolate"]
published_lo, published_hi = ameen["reported_range"]

# Matching is categorical and prospective: no score is used to rescue an incompatible endpoint.
match_table = [
    {"criterion": "porous medium grain scale", "matched": True,
     "model": f"LBS grains {diameters_mm.min():.3f}-{diameters_mm.max():.3f} mm",
     "literature": "quartz sand 0.6-1.3 mm"},
    {"criterion": "particle shape", "matched": True,
     "model": "equal-volume sphere", "literature": "sphere"},
    {"criterion": "particle size", "matched": False,
     "model": "158.7 um diameter", "literature": "10 or 20 um diameter"},
    {"criterion": "initial/loading condition", "matched": False,
     "model": "initially resident, clean-water flushing",
     "literature": "2-PV injection then 5-PV flushing"},
    {"criterion": "observable", "matched": False,
     "model": "certified release / initial resident count",
     "literature": "outlet recovery / injected mass"},
    {"criterion": "contact physics", "matched": False,
     "model": "interception censored; no attachment/detachment",
     "literature": "physical passage and retention"},
]

comparison = {
    "schema": "stage36cu.external-release-benchmark.v1",
    "passed": True,
    "decision": "magnitude_overlap_only_not_validation",
    "evidence_class": "numerically verified prediction externally benchmarked against a non-equivalent observable",
    "model": {
        "sphere_release_lower": sphere_bound["lower"],
        "sphere_release_upper_censored": sphere_bound["upper"],
        "fibre_release_lower": fibre_bound["lower"],
        "fibre_release_upper_censored": fibre_bound["upper"],
        "pore_volumes": 7.0,
        "sphere_diameter_um": 158.74010519681994,
        "fibre_full_length_um": 400.0,
        "fibre_diameter_um": 100.0,
        "fibre_aspect_ratio": 4.0,
        "sand_diameter_range_mm": [float(diameters_mm.min()), float(diameters_mm.max())],
    },
    "literature": {
        "doi": ameen["doi"],
        "reported_sphere_recovery_range": ameen["reported_range"],
        "sphere_sizes_um": ameen["sphere_sizes_um"],
        "sand_grain_range_mm": ameen["grain_range_mm"],
        "protocol": "2 pore volumes injection plus 5 pore volumes flushing",
        "range_is_confidence_interval": ameen["range_is_confidence_interval"],
    },
    "numerical_overlap": published_lo <= sphere_bound["lower"] <= published_hi,
    "absolute_gap_to_literature_midpoint": abs(
        sphere_bound["lower"] - 0.5 * (published_lo + published_hi)
    ),
    "matching": match_table,
    "matched_criteria_n": sum(x["matched"] for x in match_table),
    "total_criteria_n": len(match_table),
    "allowed_claim": (
        "The certified spherical release lower bound (12.5%) lies within a published "
        "12-14% injected-sphere recovery range in similarly coarse quartz sand."
    ),
    "prohibited_claim": (
        "This numerical overlap validates matrix release, calibrates contact physics, "
        "or demonstrates a general sphere-versus-fibre transport law."
    ),
    "fibre_validation_status": "no directly matched preloaded fibre-release comparator available",
    "next_identifiable_step": (
        "Implement and verify a contact-resolution law, then calibrate it only in a separately "
        "matched pulse-injection sphere configuration; retain resident-matrix release as prediction."
    ),
    "input_hashes": {
        str(model_path): sha256(model_path),
        str(literature_path): sha256(literature_path),
        str(GEOM): sha256(GEOM),
        str(Path(__file__)): sha256(Path(__file__)),
    },
}
(OUT / "results.json").write_text(json.dumps(comparison, indent=2))

fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.7), constrained_layout=True)
ax = axes[0]
ax.fill_between([0.72, 1.28], published_lo, published_hi, color="#7f8c8d", alpha=0.28)
ax.errorbar(
    0,
    sphere_bound["lower"],
    yerr=[[0], [sphere_bound["upper"] - sphere_bound["lower"]]],
    fmt="o",
    color="#2b6cb0",
    ecolor="#2b6cb0",
    alpha=0.9,
    capsize=5,
    lw=2,
    label="resident model: lower bound → censored upper",
)
ax.plot(1, 0.5 * (published_lo + published_hi), "s", color="#4a5568", ms=8,
        label="Ameen et al.: reported recovery range")
ax.set_xticks([0, 1], ["model\nresident release", "literature\ninjected recovery"])
ax.set_ylim(0, 1.03)
ax.set_ylabel("Fraction exported or recovered")
ax.set_title("Numerical overlap, different observables")
ax.grid(axis="y", alpha=0.2)
ax.legend(frameon=False, fontsize=8, loc="upper right")
ax.annotate("12.5%", (0, sphere_bound["lower"]), xytext=(8, 8), textcoords="offset points",
            color="#2b6cb0", fontweight="bold")
ax.annotate("12–14%", (1, published_hi), xytext=(8, 4), textcoords="offset points",
            color="#4a5568", fontweight="bold")

ax = axes[1]
criteria = [x["criterion"] for x in match_table]
values = [1 if x["matched"] else 0 for x in match_table]
colors = ["#4c956c" if v else "#c53030" for v in values]
y = np.arange(len(criteria))
ax.barh(y, [1] * len(criteria), color=colors, alpha=0.82)
ax.set_yticks(y, criteria)
ax.set_xticks([])
ax.set_xlim(0, 1)
ax.invert_yaxis()
ax.set_title("Comparator compatibility")
for yi, v in zip(y, values):
    ax.text(0.5, yi, "matched" if v else "not matched", ha="center", va="center",
            color="white", fontweight="bold", fontsize=9)
for spine in ax.spines.values():
    spine.set_visible(False)

fig.suptitle("External benchmark of release prediction", fontweight="bold")
fig.savefig(OUT / "external_release_benchmark.png", dpi=220)
plt.close(fig)

(OUT / "REPORT.md").write_text(
    "# Stage36CU external benchmark\n\n"
    "**Decision:** magnitude overlap only; this is not direct validation.\n\n"
    f"The Stage36CT spherical certified lower bound is `{sphere_bound['lower']:.3f}`. "
    f"It lies inside Ameen et al.'s reported `{published_lo:.2f}-{published_hi:.2f}` recovery "
    "range for 10/20 um spheres in 0.6-1.3 mm quartz sand. The grain scale and spherical "
    "shape are comparable, but particle size, loading condition, endpoint definition and "
    "contact physics are not. The apparent numerical agreement therefore supports only "
    "order-of-magnitude plausibility.\n\n"
    "The AR=4 fibre result remains a prediction: no directly matched preloaded fibre-release "
    "dataset is available in the verified evidence set. Interception is censored and must not "
    "be relabelled retention. A contact-resolution law must be verified before true retained "
    "or released fractions can be estimated.\n\n"
    "Primary comparator: [Ameen et al. (2024)](https://doi.org/10.1002/jeq2.20618).\n"
)

print(json.dumps({
    "passed": True,
    "decision": comparison["decision"],
    "numerical_overlap": comparison["numerical_overlap"],
    "matched_criteria": f"{comparison['matched_criteria_n']}/{comparison['total_criteria_n']}",
    "output": str(OUT),
}))
