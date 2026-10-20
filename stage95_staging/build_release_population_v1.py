"""IID reference population on common admissible sphere/prolate placements.

Uniform centres in the periodic cell and isotropic proposed axes, conditioned
on both whole bodies lying within the axial observation slab and on exact
grain non-overlap. No quota, clearance cutoff, local-flow, or outcome selection.
Accepted axes need not remain isotropic after geometric conditioning.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging")]
import matrix_case_v1
import geometry_exact_v1

OUT = ROOT / "stage95_designs/common_admissible_population_01"
DESIGN = ROOT / "stage86_designs/near_outlet_conditional_pilot_v1.json"
PREREQ = ROOT / "stage94_runs/verified_near_outlet_pair_20260913/pair_01/results.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clear(geom, x, p, a, b):
    try:
        return not geom.contacts(x, p, a, b, 0.)
    except ValueError as exc:
        if str(exc) == "grain centre inside ellipsoid":
            return False
        raise


def independent_clear(geom, x, p, a, b):
    # All grains, no tree/cached contact selector. Bounding sphere exclusion is
    # exact for grains farther than a+radius; evaluate every remaining grain.
    for centre, radius in zip(geom.c, geom.r):
        d = centre-x
        d -= geom.L*np.round(d/geom.L)
        if np.linalg.norm(d) > a+radius:
            continue
        if geometry_exact_v1._gap_at_pose(x,p,a,b,x+d,radius) <= 0:
            return False
    return True


def main():
    result = json.loads(PREREQ.read_text())
    completion = json.loads((PREREQ.parent / "completion.json").read_text())
    if not result["passed"] or completion["results_sha256"] != sha(PREREQ):
        raise RuntimeError("Stage94 prerequisite failed")
    for key in ("input_hashes", "source_hashes", "artifact_hashes"):
        for path, digest in result[key].items():
            if sha(path) != digest:
                raise RuntimeError(f"Stage94 evidence drift: {path}")
    cfg = json.loads(DESIGN.read_text())
    a,b,_ = cfg["prolate_semiaxes_m"]
    sphere = (a*b*b)**(1/3)
    count, proposal_cap = 256, 131072
    protocol = {"population": "Uniform proposed centre and isotropic proposed axis conditioned on common admissible placements in each packing.",
                "packing_weights": {"1": 1/3, "2": 1/3, "3": 1/3},
                "samples_per_packing": count, "proposal_cap_per_packing": proposal_cap,
                "rng": "PCG64", "rng_seed_by_packing": {str(s): 95000+s for s in (1,2,3)},
                "acceptance": "Both whole bodies inside 0<x<L; both exact grain gaps strictly positive. Transverse boundaries periodic. No clearance or flow-speed selection.",
                "initial_velocity": "zero generalized velocity, as prior numerical design",
                "proposed_observation_horizon_pv": 2.,
                "horizon_rationale": "Twice one mean cell transit; covers maximum whole-body mean-distance proxy with margin. This does not guarantee exit in heterogeneous flow/contact.",
                "transport_execution": "not launched by this sampler",
                "feasibility_prefix": {"packing_seed": 2, "sample_id": 0},
                "claim_boundary": "Synthetic common-admissible reference population, not measured resident distribution or all shape-specific pore placements. Three fixed packings receive equal weight.",
                "input_hashes": {str(DESIGN): sha(DESIGN), str(PREREQ): sha(PREREQ)},
                "source_hashes": {str(p): sha(p) for p in (Path(__file__),Path(matrix_case_v1.__file__),Path(geometry_exact_v1.__file__))}}
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / "protocol.json").write_text(json.dumps(protocol,indent=2))
    packs = []
    for seed in (1,2,3):
        field, old, length, _, inputs = matrix_case_v1.load(seed)
        geom = geometry_exact_v1.GrainGeometry.from_geometry(old)
        rng = np.random.Generator(np.random.PCG64(95000+seed))
        rows = []
        rejected = {"axial_boundary": 0, "sphere_overlap": 0, "fibre_overlap": 0}
        for proposal in range(proposal_cap):
            draw = rng.random(5)
            x = draw[:3]*length
            z = 2*draw[3]-1
            phi = 2*np.pi*draw[4]
            p = np.array([np.sqrt(max(0.,1-z*z))*np.cos(phi),
                          np.sqrt(max(0.,1-z*z))*np.sin(phi), z])
            extent = float(np.sqrt(b*b+(a*a-b*b)*p[0]*p[0]))
            bound = max(extent,sphere)
            if x[0] <= bound or x[0]+bound >= length:
                rejected["axial_boundary"] += 1
                continue
            if not clear(geom,x,p,sphere,sphere):
                rejected["sphere_overlap"] += 1
                continue
            if not clear(geom,x,p,a,b):
                rejected["fibre_overlap"] += 1
                continue
            if not independent_clear(geom,x,p,a,b) or not independent_clear(geom,x,p,sphere,sphere):
                raise RuntimeError("independent all-grain geometry audit failed")
            velocity,_ = field.sample(x)
            rows.append({"id": len(rows), "proposal_index": proposal,
                         "position_m": x.tolist(), "orientation": p.tolist(),
                         "initial_velocity_generalized": [0.]*6,
                         "weight_within_packing": 1/count, "weight_across_three_packings": 1/(3*count),
                         "sphere_mean_exit_distance_pv": float((length+sphere-x[0])/length),
                         "fibre_mean_exit_distance_pv": float((length+extent-x[0])/length),
                         "initial_local_flow_velocity_m_s": velocity.tolist()})
            if len(rows) == count:
                break
        if len(rows) != count:
            raise RuntimeError(f"insufficient common-admissible samples in packing {seed}")
        path = OUT / f"starts_s{seed}.json"
        path.write_text(json.dumps(rows,indent=2))
        gap = np.array([max(r["sphere_mean_exit_distance_pv"],r["fibre_mean_exit_distance_pv"]) for r in rows])
        pack = {"packing_seed": seed, "samples": count, "proposals": proposal+1,
                "rejected": rejected, "cell_length_m": length,
                "horizon_2pv_s": 2*length/cfg["target_mean_interstitial_velocity_m_s"],
                "paired_mean_exit_distance_pv_quantiles": dict(zip(("min","median","p90","max"), np.quantile(gap,[0,.5,.9,1]).tolist())),
                "independent_geometry_checks_passed": 2*count,
                "input_hashes": {str(p):sha(p) for p in inputs}, "starts_sha256": sha(path)}
        packs.append(pack)
        print(json.dumps(pack),flush=True)
    weights = sum(1/(3*count) for _ in range(3*count))
    record = {"passed": abs(weights-1) < 1e-12, "packings": packs,
              "weight_sum": weights, "total_paired_starts": 3*count,
              "input_hashes": {**protocol["input_hashes"], **{p:h for pack in packs for p,h in pack["input_hashes"].items()}},
              "source_hashes": protocol["source_hashes"],
              "artifact_hashes": {str(p):sha(p) for p in OUT.glob("*.json")},
              "claim_boundary": protocol["claim_boundary"]}
    path = OUT / "results.json"
    path.write_text(json.dumps(record,indent=2))
    (OUT / "completion.json").write_text(json.dumps({"status":"complete_passed", "results_sha256":sha(path)},indent=2))


if __name__ == "__main__":
    main()
