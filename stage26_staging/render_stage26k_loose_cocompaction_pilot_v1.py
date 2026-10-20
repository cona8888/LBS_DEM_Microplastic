#!/usr/bin/env python3
"""Render the verified Stage26k pilot mechanics history."""

from __future__ import annotations

import argparse, csv, hashlib, json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    with Path(path).open("r", encoding="utf-8") as stream: return json.load(stream)


def main():
    p = argparse.ArgumentParser(); p.add_argument("--evaluation", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, required=True); p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args(); ev = load(a.evaluation)
    assert ev["passed"] is True and ev["sand_skeleton_recovered"] is True and ev["fibre_support_qualified"] is False
    hp = a.run_dir / "cocompaction_history.csv"; assert sha256(hp) == ev["source_hashes"]["history"]
    with hp.open("r", encoding="utf-8", newline="") as stream: rows = list(csv.DictReader(stream))
    block = [int(x["block"]) for x in rows]
    stress = [float(x["mean_effective_stress_pa_compression_positive"]) for x in rows]
    void = [float(x["sand_skeleton_void_ratio"]) for x in rows]
    contacts = [int(x["sand_sand_real_contact_count"]) for x in rows]
    fibre = [min(json.loads(x["distinct_sand_contacts_by_fibre"])) for x in rows]
    a.output_dir.mkdir(parents=True, exist_ok=False)
    fig, ax = plt.subplots(2, 2, figsize=(13, 8.2), constrained_layout=True)
    ax[0,0].plot(block, void, color="#2878B5"); ax[0,0].axhspan(0.68858,0.78858,color="#59A14F",alpha=.15,label="reference ±0.05")
    ax[0,0].set(xlabel="check block",ylabel="sand-skeleton void ratio",title="Loose-state isotropic compression"); ax[0,0].legend(fontsize=8)
    ax[0,1].plot(block, stress,color="#D95319"); ax[0,1].axhline(100,color="black",ls="--",lw=1,label="target")
    ax[0,1].set(xlabel="check block",ylabel="mean effective stress (Pa)",title="Target stress recovered"); ax[0,1].legend(fontsize=8)
    ax[1,0].plot(block,contacts,color="#6A3D9A"); ax[1,0].axhline(361,color="black",ls="--",lw=1,label="pure-sand reference")
    ax[1,0].set(xlabel="check block",ylabel="sand-sand contacts",title="Sand network rebuilt"); ax[1,0].legend(fontsize=8)
    ax[1,1].plot(block,fibre,color="#E15759"); ax[1,1].axhline(3,color="black",ls="--",lw=1,label="required minimum")
    ax[1,1].set(xlabel="check block",ylabel="minimum contacts per fibre",title="Fixed-fibre support did not qualify"); ax[1,1].set_ylim(-.1,4.2); ax[1,1].legend(fontsize=8)
    fig.suptitle("Stage26k loose-state co-compaction: sand skeleton recovered; fixed-fibre support failed\nExact sand radii and 50 μm fibre geometry throughout; no held-out or flow execution",fontsize=14)
    image=a.output_dir/"stage26k_loose_cocompaction_pilot.png"; fig.savefig(image,dpi=180,facecolor="white"); plt.close(fig)
    manifest={"schema":"lbs.stage26k-loose-cocompaction-render-manifest.v1","passed":True,
              "status":"verified_pilot_failure_render","image":str(image).replace("\\","/"),"image_sha256":sha256(image),
              "source_hashes":{"evaluation":sha256(a.evaluation),"history":sha256(hp),"renderer":sha256(Path(__file__))},
              "claim_boundary":ev["claim_boundary"]}
    mp=a.output_dir/"render_manifest.json"
    with mp.open("x",encoding="utf-8",newline="\n") as stream: json.dump(manifest,stream,indent=2,sort_keys=True); stream.write("\n")
    print(json.dumps({"image":str(image),"image_sha256":sha256(image)},sort_keys=True))


if __name__ == "__main__": main()
