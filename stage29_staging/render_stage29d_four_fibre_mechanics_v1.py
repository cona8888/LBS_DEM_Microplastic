from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29d_shared_pair_context_qualification_20260825"
RUN = ROOT / "stage29_runs" / STUDY / "mechanics_01"
EVALUATION = ROOT / "stage29_evaluations" / STUDY / "mechanics_evaluation_01" / "evaluation.json"
CHECKPOINT = ROOT / "stage29_evaluations" / STUDY / "mechanics_evaluation_01" / "checkpoint_manifest.json"
OUT = ROOT / "stage29_renders" / STUDY / "mechanics_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    evaluation = json.loads(EVALUATION.read_text())
    checkpoint = json.loads(CHECKPOINT.read_text())
    if not (evaluation.get("passed") and evaluation["authority"]["rendering"] and checkpoint.get("passed")):
        raise RuntimeError("mechanics checkpoint does not authorize rendering")
    colors = ["#d54a3a", "#2672bd", "#23934b", "#963dad"]
    fig = plt.figure(figsize=(12, 15), constrained_layout=True)
    rendered = []
    for row, block in enumerate("ABC"):
        for col, topology in enumerate(("zero_contact", "one_contact")):
            cid = f"s29d_f004_{topology}_context_{block}"
            case = json.loads((RUN / f"{cid}_result.json").read_text())
            ax = fig.add_subplot(3, 2, row * 2 + col + 1, projection="3d")
            for i, fibre in enumerate(case["terminal_fibres"]):
                initial = 1000.0 * np.asarray(fibre["initial_node_positions_m"])
                terminal = 1000.0 * np.asarray(fibre["terminal_node_positions_m"])
                ax.plot(initial[:, 0], initial[:, 1], initial[:, 2], color=colors[i], alpha=.24, linewidth=1.1, linestyle="--")
                ax.plot(terminal[:, 0], terminal[:, 1], terminal[:, 2], color=colors[i], linewidth=2.4, label=f"F{i+1}")
                ax.scatter(terminal[-1, 0], terminal[-1, 1], terminal[-1, 2], color=colors[i], s=18)
            edges = ", ".join(case["terminal_contact_edges"]) or "none"
            force = case["maximum_fibre_contact_normal_force_n"] * 1e6
            ax.set_title(f"Block {block} — {topology.replace('_', ' ')}\nterminal edges: {edges}; max contact force: {force:.2f} µN", fontsize=10)
            ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)"); ax.set_zlabel("z (mm)")
            ax.set_xlim(0, 4.65); ax.set_ylim(0, 4.65); ax.set_zlim(0, 4.65)
            ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=25, azim=38)
            ax.legend(loc="upper right", fontsize=7, frameon=False)
            rendered.append(cid)
    fig.suptitle("Stage29d four-fibre mechanics qualification\nsolid: terminal centreline; dashed: initial centreline; fixed 216-grain periodic LBS context", fontsize=15)
    OUT.mkdir(parents=True)
    image = OUT / "stage29d_four_fibre_mechanics.png"
    fig.savefig(image, dpi=220, facecolor="white")
    plt.close(fig)
    manifest = {
        "schema": "lbs.stage29d-four-fibre-mechanics-render.v1",
        "passed": True,
        "status": "rendered_verified_mechanics_evidence",
        "rendered_cases": rendered,
        "image": {"path": str(image), "sha256": sha(image)},
        "source_bindings": {"evaluation_sha256": sha(EVALUATION), "checkpoint_sha256": sha(CHECKPOINT)},
        "claim_boundary": "Visual evidence of the accepted mechanics pilot; not a permeability or physical-mixing validation.",
    }
    (OUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **manifest}, indent=2))


if __name__ == "__main__":
    main()
