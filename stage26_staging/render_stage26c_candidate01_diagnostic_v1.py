"""Render the accepted-controls and candidate01 fixed-prefilter histories."""

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "stage26_runs/stage26c_revision3_fixed_prefilter_20260816"
OUT = ROOT / "stage26_renders/stage26c_revision3_fixed_prefilter_20260816/candidate01_diagnostic_02"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def history(path):
    rows = []
    with path.open(newline="") as stream:
        for raw in csv.DictReader(stream):
            row = {key: value for key, value in raw.items()}
            row["block"] = int(row["block"])
            row["distinct_sand_contacts_by_fibre"] = json.loads(row["distinct_sand_contacts_by_fibre"])
            row["declared_anchor_contacts_by_fibre"] = json.loads(row["declared_anchor_contacts_by_fibre"])
            for key in (
                "relative_mean_stress_error", "maximum_principal_stress_error",
                "unbalanced_force", "sand_sand_contact_retention_fraction",
            ):
                row[key] = float(row[key])
            rows.append(row)
    return rows


def main():
    paths = {
        "positive": RUN / "controls_02/positive_stage26a/fixed_conditioning_history.csv",
        "negative": RUN / "controls_02/negative_stage26b_failure/fixed_conditioning_history.csv",
        "candidate": RUN / "candidate_01/revision3_candidate01/fixed_conditioning_history.csv",
    }
    data = {key: history(value) for key, value in paths.items()}
    OUT.mkdir(parents=True, exist_ok=False)
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), constrained_layout=True)

    ax = axes[0]
    colors = ["#006ba4", "#ff800e"]
    for fibre in range(2):
        ax.step(
            [row["block"] for row in data["candidate"]],
            [row["distinct_sand_contacts_by_fibre"][fibre] for row in data["candidate"]],
            where="mid", color=colors[fibre], linewidth=2,
            label=f"Revision-3 candidate fibre {fibre + 1}",
        )
    ax.step(
        [row["block"] for row in data["positive"]],
        [row["distinct_sand_contacts_by_fibre"][0] for row in data["positive"]],
        where="mid", color="#3e9651", linestyle="--", label="positive control",
    )
    ax.step(
        [row["block"] for row in data["negative"]],
        [row["distinct_sand_contacts_by_fibre"][0] for row in data["negative"]],
        where="mid", color="#cc2529", linestyle=":", linewidth=2, label="negative-control failing fibre",
    )
    ax.axvspan(50.5, 60.5, color="#e6e6e6", label="terminal persistence window")
    ax.axhline(1, color="black", linewidth=0.8)
    ax.axhline(2, color="black", linewidth=0.8, linestyle="--")
    ax.set(xlim=(1, 60), ylim=(-0.15, 3.4), ylabel="Distinct sand contacts per fibre",
           title="Temporal engagement passes for Revision-3 candidate01")
    ax.legend(ncol=2, fontsize=9, loc="lower right")
    ax.grid(alpha=0.25)

    ax = axes[1]
    candidate = data["candidate"]
    block = [row["block"] for row in candidate]
    series = {
        "mean-stress error / limit": [row["relative_mean_stress_error"] / 0.02 for row in candidate],
        "principal-stress error / limit": [row["maximum_principal_stress_error"] / 0.03 for row in candidate],
        "unbalanced force / limit": [row["unbalanced_force"] / 0.05 for row in candidate],
        "retention deficit ratio": [(1.0 - row["sand_sand_contact_retention_fraction"]) / 0.10 for row in candidate],
    }
    for label, values in series.items():
        ax.plot(block, values, linewidth=1.8, label=label)
    ax.axhline(1.0, color="black", linewidth=1.2, linestyle="--", label="acceptance boundary")
    ax.axvspan(50.5, 60.5, color="#e6e6e6")
    ax.set(xlim=(1, 60), xlabel="Fixed-conditioning block (500 YADE steps each)",
           ylabel="Normalized diagnostic", title="Sand-health gate fails at block 60")
    ax.set_ylim(bottom=0)
    ax.legend(ncol=2, fontsize=9)
    ax.grid(alpha=0.25)
    fig.suptitle(
        "Stage26c Revision-3 candidate01 — fixed-fibre diagnostic only\n"
        "Contacts persist, but the qualified sand state is not restored; no release or flow authorized",
        fontsize=14,
    )
    image = OUT / "stage26c_candidate01_temporal_and_sand_health.png"
    fig.savefig(image, dpi=180)
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26c-candidate01-diagnostic-render.v1",
        "passed": True,
        "status": "rendered_verified_negative_prefilter_outcome",
        "image": str(image),
        "image_sha256": digest(image),
        "sources": {str(path): digest(path) for path in paths.values()},
        "outcome_checkpoint": str(ROOT / "stage26_checkpoints/stage26c_revision3_fixed_prefilter_20260816/candidate01_outcome_checkpoint_01/checkpoint_manifest.json"),
        "outcome_checkpoint_sha256": digest(ROOT / "stage26_checkpoints/stage26c_revision3_fixed_prefilter_20260816/candidate01_outcome_checkpoint_01/checkpoint_manifest.json"),
        "claim_boundary": "Diagnostic fixed-fibre history only; no accepted two-fibre DEM state, free release, permeability, or coupled-flow result.",
    }
    (OUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(image)


if __name__ == "__main__":
    main()
