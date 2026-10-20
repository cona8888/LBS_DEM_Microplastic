"""One declared finer sphere timestep level on CPD4 and CPD6."""
from pathlib import Path
import copy, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage133_staging"), str(ROOT / "stage131_staging"), str(ROOT / "stage132_staging")]
import cpd6_response_refinement_v1 as prior6
import refine_cpd4_timesteps_v1 as prior4
import load_cpd6_stationary_field_v1 as cpd6

engine, api = prior6.engine, prior6.api
ORIGINAL_LOAD = api.fields.load
BASE = "sphere_combined_budget_refinement_20260916"
DESIGN = ROOT / "stage134_designs" / BASE / "design_01.json"
RUN = ROOT / "stage134_runs" / BASE / "sentinels_01"
EVAL = ROOT / "stage134_evaluations" / BASE


def expected_cases():
    source4 = next(c["spec"] for c in api.read(prior4.DESIGN)["cases"] if c["spec"]["shape"] == api.SHAPES[0])
    source6 = next(c["spec"] for c in api.read(prior6.DESIGN)["cases"] if c["spec"]["shape"] == api.SHAPES[0] and c["spec"]["refinement"] == .03125)
    cases = []
    for source in (source4, source6):
        spec = copy.deepcopy(source)
        spec["refinement"] *= .5
        for key in api.DT_CONTROLS:
            spec["config"]["numerics"][key] *= .5
        spec["case_id"] = f"s2_sphere_f1p0_cpd{spec['cpd']}_dt64_h0p5"
        cases.append({"id": "refined_" + spec["case_id"], "spec": spec, "source_checkpoint": None,
                      "initial_state_sha256": api.digest(spec["initial_state"])})
    return cases


def verify(design):
    api.require(design["binding"] == api.digest({k:v for k,v in design.items() if k != "binding"}), "binding drift")
    api.verify_mapping(design["source_hashes"]); api.verify_mapping(design["inputs"])
    api.require(design["cases"] == expected_cases() and design["physical_changes"] == [], "case drift")


def prepare():
    cases = expected_cases()
    sources = [Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m, "__file__", None) and Path(m.__file__).suffix == ".py" and ROOT in Path(m.__file__).resolve().parents]
    inputs = [prior4.DESIGN, prior6.DESIGN, prior4.EVAL / "independent_evaluation_01/completion.json", prior6.RUN / "completion.json"]
    design = {"stage": "Stage134", "cases": cases,
              "groups": [{"name": "sphere_CPD4_CPD6_dt64", "ids": [c["id"] for c in cases]}],
              "physical_changes": [], "numerical_changes": ["Halve all four sphere timestep controls once on CPD4 and CPD6."],
              "acceptance": api.read(prior4.DESIGN)["acceptance"], "event_acceptance": api.read(prior4.DESIGN)["event_acceptance"],
              "budget": {"segment_s": 45, "max_segments_per_case": 3, "stage_wall_s": 180, "stop_on_numerical_failure": True},
              "scope": "Two fresh sphere trajectories to 0.5 s to resolve the conservative combined numerical budget.",
              "source_hashes": {str(p): api.sha(p) for p in sorted(set(sources + list(Path(__file__).parent.glob('*.py'))))},
              "inputs": {str(p): api.sha(p) for p in inputs}}
    design["binding"] = api.digest(design)
    DESIGN.parent.mkdir(parents=True, exist_ok=True); api.write(DESIGN, design); verify(design)
    print("FROZEN", api.sha(DESIGN), "cases", len(cases))


def configure():
    engine.DESIGN, engine.RUN, engine.EVAL = DESIGN, RUN, EVAL
    engine.verify = verify; engine.__file__ = str(Path(__file__).resolve())
    api.fields.load = lambda seed, factor, cpd, **kwargs: cpd6.load() if int(cpd) == 6 else ORIGINAL_LOAD(seed, factor, cpd, **kwargs)


if __name__ == "__main__":
    if sys.argv[1] == "prepare": prepare()
    else:
        configure(); raise SystemExit(engine.run() if sys.argv[1] == "run" else engine.worker(sys.argv[2], int(sys.argv[3])))
