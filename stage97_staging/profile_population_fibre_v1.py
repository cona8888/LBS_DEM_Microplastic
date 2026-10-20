"""Local cost probe of the censored IID fibre; no physical continuation."""
import cProfile
import io
import json
import pstats
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT / "stage89_staging")]
import verify_short_seed_local_v1 as harness

CASE=ROOT / "stage96_runs/population_prefix_01/s2_i0_prolate_ar4.json"
OUT=ROOT / "stage97_evaluations/population_fibre_profile_01"


def main():
    previous=json.loads(CASE.read_text())["result"]
    if previous["status"]!="incomplete_budget":
        raise RuntimeError("expected censored fibre")
    cfg=json.loads(harness.DESIGN.read_text())
    OUT.mkdir(parents=True,exist_ok=False)
    profiler=cProfile.Profile()
    profiler.enable()
    try:
        result=harness.run_local(harness.candidate,cfg,previous,2,.002,20.)
    finally:
        profiler.disable()
    stream=io.StringIO()
    pstats.Stats(profiler,stream=stream).strip_dirs().sort_stats("cumulative").print_stats(55)
    profile=OUT / "profile.txt"
    profile.write_text(stream.getvalue())
    record={"diagnostic_only":True,"local_horizon_s":.002,"wall_budget_s":20.,"result":result,
            "input_hashes":{str(p):harness.sha(p) for p in (CASE,harness.DESIGN)},
            "source_hashes":{str(p):harness.sha(p) for p in (Path(__file__),Path(harness.__file__),Path(harness.candidate.__file__))},
            "profile_sha256":harness.sha(profile),
            "claim_boundary":"Local pose/velocity restart with reset time and dwell history. Numerical cost diagnostic only; not a continuation or release observation."}
    harness.dump(OUT / "results.json",record)
    harness.dump(OUT / "completion.json",{"status":"complete_profiled","results_sha256":harness.sha(OUT / "results.json")})
    print(json.dumps({"status":result["status"],"time_s":result["time_s"],"runtime_s":result["runtime_seconds"],
                      "steps":result["steps"],"rejected":result["rejected"]}))


if __name__=="__main__":
    main()
