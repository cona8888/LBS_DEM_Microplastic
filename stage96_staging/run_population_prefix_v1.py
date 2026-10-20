"""Bounded first IID pair at the declared 2-PV release horizon.

The first sample in packing 2 was fixed before transport. A 300-second cap
per shape tests feasibility; incomplete observations stay explicitly censored.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage89_staging")]
import verify_short_seed_local_v1 as harness

POP = ROOT / "stage95_designs/common_admissible_population_01"
OUT = ROOT / "stage96_runs/population_prefix_01"


def main():
    population = json.loads((POP / "results.json").read_text())
    completion = json.loads((POP / "completion.json").read_text())
    if not population["passed"] or completion["results_sha256"] != harness.sha(POP / "results.json"):
        raise RuntimeError("population prerequisite failed")
    for section in ("input_hashes", "source_hashes", "artifact_hashes"):
        for path,digest in population[section].items():
            if harness.sha(path) != digest:
                raise RuntimeError(f"population lineage drift: {path}")
    cfg = json.loads(harness.DESIGN.read_text())
    start_path = POP / "starts_s2.json"
    start = json.loads(start_path.read_text())[0]
    length = next(p["cell_length_m"] for p in population["packings"] if p["packing_seed"] == 2)
    horizon = 2*length/cfg["target_mean_interstitial_velocity_m_s"]
    sources = {Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        name = getattr(module,"__file__",None)
        if name:
            path = Path(name).resolve()
            if path.suffix == ".py" and ROOT in path.parents:
                sources.add(path)
    protocol = {"seed":2,"sample_id":0,"horizon_pv":2.,"horizon_s":horizon,
                "wall_budget_s_per_shape":300.,"selection":"First IID accepted sample, frozen before transport.",
                "input_hashes":{str(p):harness.sha(p) for p in (POP / "results.json",start_path,harness.DESIGN)},
                "source_hashes":{str(p):harness.sha(p) for p in sorted(sources)},
                "claim_boundary":"Computational feasibility of one IID pair; no population release estimate from this prefix."}
    OUT.mkdir(parents=True,exist_ok=False)
    harness.dump(OUT / "protocol.json",protocol)
    rows = []
    previous = {"position_m":start["position_m"],"orientation":start["orientation"],
                "velocity_generalized":start["initial_velocity_generalized"]}
    for shape in cfg["shapes"]:
        config = copy.deepcopy(cfg)
        if shape == "equal_volume_sphere":
            a,b,_ = cfg["prolate_semiaxes_m"]
            radius = (a*b*b)**(1/3)
            config["prolate_semiaxes_m"] = [radius]*3
        result = harness.run_local(harness.candidate,config,previous,2,horizon,300.)
        numerical_health = bool(result["minimum_gap_m"] is not None
            and result["minimum_gap_m"] >= -5e-10 and result["max_contact_residual"] <= 1e-8
            and result["max_force_residual"] <= 1e-8 and result["max_momentum_residual"] <= 1e-8
            and result["max_reynolds"] <= 3)
        resolved = bool((result["status"] == "present_at_horizon" and abs(result["time_s"]-horizon)<=1e-12)
                        or (result["status"] == "full_window_exit" and 0<result["time_s"]<=horizon))
        row = {"packing_seed":2,"sample_id":0,"shape":shape,
               "weight_in_frozen_pool":start["weight_across_three_packings"],
               "health_passed":numerical_health,"resolved":resolved and numerical_health,
               "observed_pv":2*result["time_s"]/horizon,"result":result}
        rows.append(row)
        harness.dump(OUT / f"s2_i0_{shape}.json",row)
        print(json.dumps({"shape":shape,"status":result["status"],"observed_pv":row["observed_pv"],
                          "runtime_s":result["runtime_seconds"],"resolved":row["resolved"]}),flush=True)
    record = {"executions_accounted":len(rows)==2,"all_resolved":all(r["resolved"] for r in rows),
              "rows":rows,"input_hashes":protocol["input_hashes"],"source_hashes":protocol["source_hashes"],
              "artifact_hashes":{str(p):harness.sha(p) for p in OUT.glob("*.json")},
              "claim_boundary":protocol["claim_boundary"]}
    harness.dump(OUT / "results.json",record)
    harness.dump(OUT / "completion.json",{"status":"complete_resolved" if record["all_resolved"] else "complete_unresolved",
                                           "results_sha256":harness.sha(OUT / "results.json")})


if __name__ == "__main__":
    main()
