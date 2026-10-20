"""Render the verified Stage26b two-fibre conditioning failure."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = PROJECT / "stage26_runs" / "stage26b_dry_multifibre_20260814" / "qualification_01" / "stage26b_f002_A"
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_dry_multifibre_20260814" / "tier1_yade_evaluation_01" / "evaluation.json"
OUTPUT = PROJECT / "stage26_renders" / "stage26b_dry_multifibre_20260814" / "tier1_yade_failure_render_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def load_history(path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sphere_surface(ax, centre, radius, color, alpha, resolution=6, edge=None):
    u = np.linspace(0, 2 * np.pi, 2 * resolution)
    v = np.linspace(0, np.pi, resolution)
    x = centre[0] + radius * np.outer(np.cos(u), np.sin(v))
    y = centre[1] + radius * np.outer(np.sin(u), np.sin(v))
    z = centre[2] + radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(x, y, z, color=color, alpha=alpha, linewidth=0.1 if edge else 0, edgecolor=edge, shade=True)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable failure render already exists")
    evaluation = load_json(EVALUATION)
    result_path = Path(evaluation["evidence"]["result_path"])
    if not evaluation.get("passed") or digest(result_path) != evaluation["evidence"]["result_sha256"]:
        raise RuntimeError("evaluation/result binding failed")
    result = load_json(result_path)
    conditioning = load_history(RUN / "conditioning_history.csv")
    free = load_history(RUN / "free_relaxation_history.csv")
    rows = conditioning + free
    x = np.arange(1, len(rows) + 1)
    release = len(conditioning) + 0.5
    contacts = np.array([json.loads(row["distinct_sand_contacts_by_fibre"]) for row in rows])
    stress = np.array([float(row["mean_effective_stress_pa_compression_positive"]) for row in rows])
    unbalanced = np.array([float(row["unbalanced_force"]) for row in rows])
    sand_contacts = np.array([float(row["sand_sand_real_contact_count"]) for row in rows])
    max_disp = np.array([float(row["maximum_nonaffine_sand_displacement_over_D50"]) for row in rows])

    fig = plt.figure(figsize=(16, 10.5))
    ax1 = fig.add_subplot(2, 2, 1)
    ax2 = fig.add_subplot(2, 2, 2)
    ax3 = fig.add_subplot(2, 2, 3)
    ax4 = fig.add_subplot(2, 2, 4, projection="3d")
    for ax in (ax1, ax2, ax3):
        ax.axvline(release, color="#555555", ls="--", lw=1.2)
        ax.grid(alpha=0.25)
    ax1.step(x, contacts[:, 0], where="mid", color="#d62728", label="fibre 1 (failed)")
    ax1.step(x, contacts[:, 1], where="mid", color="#2ca02c", label="fibre 2")
    ax1.axhline(2, color="#111111", ls=":", label="minimum gate")
    ax1.set_ylim(-0.2, max(4.2, contacts.max() + 0.5))
    ax1.set_xlabel("check block (release after 60)")
    ax1.set_ylabel("distinct sand contacts")
    ax1.set_title("Fibre engagement: fibre 1 loses both contacts")
    ax1.legend(loc="upper right")
    ax2.plot(x, stress, color="#1f77b4", lw=1.0, label="mean stress")
    ax2.axhspan(98, 102, color="#1f77b4", alpha=0.12, label="stress gate")
    ax2.set_xlabel("check block")
    ax2.set_ylabel("mean effective stress (Pa)", color="#1f77b4")
    ax2b = ax2.twinx()
    ax2b.plot(x, unbalanced, color="#d62728", lw=0.9, alpha=0.8, label="unbalanced")
    ax2b.axhline(0.02, color="#d62728", ls=":")
    ax2b.set_ylabel("unbalanced force", color="#d62728")
    ax2.set_title("Controller recovers, but contact failure persists")
    ax3.plot(x, sand_contacts, color="#6b4f1d", label="sand-sand contacts")
    ax3.axhline(361 * 0.90, color="#6b4f1d", ls=":", label="90% retention gate")
    ax3.set_xlabel("check block")
    ax3.set_ylabel("sand-sand real contacts", color="#6b4f1d")
    ax3b = ax3.twinx()
    ax3b.plot(x, max_disp, color="#9467bd", label="maximum sand displacement")
    ax3b.axhline(0.20, color="#9467bd", ls=":")
    ax3b.set_ylabel("maximum sand displacement / D50", color="#9467bd")
    ax3.set_title("Sand network remains load-bearing")

    terminal_contacts = [set(value) for value in result["terminal"]["contacted_sand_body_ids_by_fibre"]]
    contacted_all = set().union(*terminal_contacts)
    lengths = np.array(result["terminal"]["cell_dimensions_m"]) * 1000.0
    for particle in result["particles"]:
        centre = np.array(particle["position_m"]) * 1000.0
        radius = particle["radius_m"] * 1000.0
        if particle["phase"] == "sand":
            is_contact = particle["body_id"] in contacted_all
            sphere_surface(ax4, centre, radius, "#2878b5" if is_contact else "#d7b56d", 0.82 if is_contact else 0.10,
                           resolution=6, edge="#164b73" if is_contact else None)
        else:
            fibre_index = particle["fibre_index"]
            sphere_surface(ax4, centre, radius, "#d62728" if fibre_index == 0 else "#2ca02c", 0.94, resolution=6, edge="#4f1b1b")
    ax4.set_xlim(0, lengths[0]); ax4.set_ylim(0, lengths[1]); ax4.set_zlim(0, lengths[2])
    ax4.set_box_aspect(lengths)
    ax4.set_xlabel("x (mm)"); ax4.set_ylabel("y (mm)"); ax4.set_zlabel("z (mm)")
    ax4.view_init(elev=22, azim=-52)
    ax4.set_title("Terminal actual geometry\nred fibre isolated; green fibre engaged; blue grains contacted")
    fig.subplots_adjust(left=0.065, right=0.96, bottom=0.12, top=0.88, hspace=0.30, wspace=0.25)
    fig.suptitle("Stage26b Tier-1 scientific failure: two-fibre placement is not conditioning-stable",
                 fontsize=17, weight="bold", y=0.965)
    fig.text(0.5, 0.045,
             "All four anchor contacts existed immediately after insertion. Fibre 1 lost both during the first fixed-conditioning block and never re-engaged.\n"
             "Verified dry small-assembly failure only; no permeability, physical mixing, polymer calibration, migration or coupled-flow claim.",
             ha="center", va="center", fontsize=10)
    OUTPUT.mkdir(parents=True)
    image_path = OUTPUT / "stage26b_two_fibre_conditioning_failure.png"
    fig.savefig(image_path, dpi=210, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage26b-tier1-yade-failure-render.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": True,
        "source_hashes": {"evaluation": digest(EVALUATION), "result": digest(result_path),
                          "conditioning_history": digest(RUN / "conditioning_history.csv"),
                          "free_history": digest(RUN / "free_relaxation_history.csv"),
                          "probe": evaluation["evidence"]["probe_sha256"], "renderer": digest(Path(__file__))},
        "image_path": str(image_path), "image_sha256": digest(image_path),
        "claim_boundary": evaluation["claim_boundary"],
        "visual_semantics": "Actual terminal particle coordinates and radii with equal physical data-unit scaling in the 3-D panel; transparency only exposes the fibres.",
    }
    with (OUTPUT / "render_manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "image_sha256": digest(image_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
