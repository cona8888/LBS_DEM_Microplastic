from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29e_low_concentration_hydraulic_design_20260826"
EVAL_DIR = ROOT / "stage29_evaluations" / STUDY / "hydraulic_evaluation_01"
EVALUATION = EVAL_DIR / "evaluation.json"
CHECKPOINT = EVAL_DIR / "checkpoint_manifest.json"
OUT = ROOT / "stage29_renders" / STUDY / "hydraulic_screen_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if not (evaluation.get("passed") and evaluation["authority"]["rendering"] and checkpoint.get("passed")):
        raise RuntimeError("independent Stage29e checkpoint does not authorize rendering")

    s = evaluation["branch_summary"]
    effects = evaluation["effects_k_over_k0"]
    x = np.array([0.0, s["single_isolated"]["dry_mass_percent"], s["two_fibre_separated"]["dry_mass_percent"], s["four_fibre_zero_contact"]["dry_mass_percent"]])
    y_zero = np.array([s["clean"]["ratio"], s["single_isolated"]["mean"], s["two_fibre_separated"]["ratio"], s["four_fibre_zero_contact"]["mean"]])
    yerr_zero = np.array([0.0, s["single_isolated"]["sample_standard_deviation"], 0.0, s["four_fibre_zero_contact"]["sample_standard_deviation"]])
    x_contact = np.array([s["two_fibre_crossing"]["dry_mass_percent"], s["four_fibre_one_contact"]["dry_mass_percent"]])
    y_contact = np.array([s["two_fibre_crossing"]["ratio"], s["four_fibre_one_contact"]["mean"]])
    yerr_contact = np.array([0.0, s["four_fibre_one_contact"]["sample_standard_deviation"]])

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2), constrained_layout=True)
    ax = axes[0]
    ax.errorbar(x, y_zero, yerr=yerr_zero, color="#2672bd", marker="o", capsize=4, linewidth=2, label="zero-contact branch")
    ax.errorbar(x_contact, y_contact, yerr=yerr_contact, color="#d54a3a", marker="s", capsize=4, linewidth=2, label="contact branch")
    ax.axhline(1.0, color="#555555", linewidth=1, linestyle="--")
    ax.set_xlabel("F37 dry-mass concentration (%)")
    ax.set_ylabel("Paired permeability ratio, k/k₀")
    ax.set_title("Concentration and topology")
    ax.legend(frameon=False)
    ax.grid(alpha=0.22)

    ax = axes[1]
    labels = ["1 isolated\n(mean, n=3)", "2 separated", "2 crossing", "4 zero contact\n(mean, n=3)", "4 one contact\n(mean, n=3)"]
    ratios = [s["single_isolated"]["mean"], s["two_fibre_separated"]["ratio"], s["two_fibre_crossing"]["ratio"], s["four_fibre_zero_contact"]["mean"], s["four_fibre_one_contact"]["mean"]]
    obstruction = 100.0 * (1.0 - np.asarray(ratios))
    colors = ["#6aa5d8", "#78b76a", "#d54a3a", "#2672bd", "#e38273"]
    ax.bar(np.arange(len(labels)), obstruction, color=colors)
    ax.set_xticks(np.arange(len(labels)), labels, rotation=25, ha="right")
    ax.set_ylabel("Permeability reduction from clean (%)")
    ax.set_title("Raw mechanism effects")
    ax.grid(axis="y", alpha=0.22)

    ax = axes[2]
    blocks = list("ABC")
    contrast = np.array([effects["four_one_minus_zero_paired"][b] for b in blocks])
    ax.bar(blocks, 100.0 * contrast, color="#8a57b5")
    ax.axhline(0.0, color="#555555", linewidth=1)
    ax.set_xlabel("Four-fibre context block")
    ax.set_ylabel("100 × (k/k₀ one-contact − zero-contact)")
    ax.set_title("Paired topology contrast")
    ax.grid(axis="y", alpha=0.22)
    for i, value in enumerate(100.0 * contrast):
        ax.text(i, value + 0.02, f"{value:+.3f}", ha="center", va="bottom", fontsize=9)

    fig.suptitle("Stage29e CPD2 fixed-packing hydraulic screen\n216-grain periodic LBS; static fibres; error bars are sample SD across available context blocks", fontsize=14)
    OUT.mkdir(parents=True)
    image = OUT / "stage29e_low_concentration_cpd2_screen.png"
    fig.savefig(image, dpi=220, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage29e-low-concentration-cpd2-render.v1",
        "passed": True,
        "status": "rendered_independently_verified_cpd2_screen",
        "image": {"path": str(image), "sha256": sha(image)},
        "source_bindings": {"evaluation_sha256": sha(EVALUATION), "checkpoint_sha256": sha(CHECKPOINT)},
        "claim_boundary": "One fixed 216-grain periodic LBS packing with static mechanics-qualified fibres at CPD2; not laboratory permeability validation or population inference.",
    }
    (OUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **manifest}, indent=2))


if __name__ == "__main__":
    main()
