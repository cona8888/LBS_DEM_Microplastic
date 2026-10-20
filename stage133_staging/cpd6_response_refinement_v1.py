"""Matched CPD6 0.5-s particle responses at three timestep levels per shape."""
from pathlib import Path
import copy, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage131_staging"), str(ROOT / "stage132_staging")]
import refine_cpd4_timesteps_v1 as previous
import load_cpd6_stationary_field_v1 as cpd6

engine, api = previous.engine, previous.api
BASE = "cpd6_response_refinement_20260916"
DESIGN = ROOT / "stage133_designs" / BASE / "design_01.json"
RUN = ROOT / "stage133_runs" / BASE / "sentinels_01"
EVAL = ROOT / "stage133_evaluations" / BASE
SEAL131 = ROOT / "stage131_evaluations/cpd4_timestep_refinement_20260916/independent_evaluation_01/completion.json"
SEAL132 = ROOT / "stage132_evaluations/cpd6_particle_field_adapter_20260916/preflight_01/completion.json"


def expected_cases():
    old = api.read(previous.DESIGN)
    _, _, metadata = cpd6.load()
    cases = []
    for shape, levels in [(api.SHAPES[0], [.125, .0625, .03125]), (api.SHAPES[1], [.25, .125, .0625])]:
        template = next(c["spec"] for c in old["cases"] if c["spec"]["shape"] == shape)
        base = copy.deepcopy(template)
        for key in api.DT_CONTROLS:
            base["config"]["numerics"][key] /= template["refinement"]
        for level in levels:
            spec = copy.deepcopy(base)
            spec["cpd"] = 6
            spec["refinement"] = level
            spec["case_id"] = f"s2_{'sphere' if shape == api.SHAPES[0] else 'ar4'}_f1p0_cpd6_dt{round(1/level)}_h0p5"
            for key in api.DT_CONTROLS:
                spec["config"]["numerics"][key] *= level
            spec["config"]["target_mean_interstitial_velocity_m_s"] = metadata["achieved_mean_interstitial_velocity_m_s"]
            spec["field_metadata"] = metadata
            spec["horizon_s"] = .5
            spec["horizon_pv"] = .5 * metadata["pv_per_second"]
            cases.append({"id": "fresh_" + spec["case_id"], "spec": spec, "source_checkpoint": None,
                          "initial_state_sha256": api.digest(spec["initial_state"])})
    return cases


def verify(design):
    api.require(design["binding"] == api.digest({k:v for k,v in design.items() if k != "binding"}), "binding drift")
    api.verify_mapping(design["source_hashes"])
    api.verify_mapping(design["inputs"])
    api.require(design["cases"] == expected_cases(), "case drift")
    api.require(design["physical_changes"] == [] and len(design["cases"]) == 6, "scope drift")
    api.require(api.read(SEAL131)["qualified"] and api.read(SEAL132)["passed"], "predecessor not qualified")


def prepare():
    cases = expected_cases()
    sources = [Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m, "__file__", None) and Path(m.__file__).suffix == ".py" and ROOT in Path(m.__file__).resolve().parents]
    sources += list(Path(__file__).parent.glob("*.py"))
    inputs = [previous.DESIGN, SEAL131, SEAL132, cpd6.EVALUATION, cpd6.COMPLETION, cpd6.FIELD, cpd6.GEOMETRY]
    design = {"stage": "Stage133", "cases": cases,
              "groups": [{"name": shape, "ids": [c["id"] for c in cases if c["spec"]["shape"] == shape]} for shape in api.SHAPES],
              "physical_changes": [],
              "numerical_changes": ["Use the independently qualified mean-matched CPD6 field.", "Run three declared timestep levels per shape from identical fresh physical states."],
              "acceptance": api.read(previous.DESIGN)["acceptance"],
              "event_acceptance": api.read(previous.DESIGN)["event_acceptance"],
              "budget": {"segment_s": 45, "max_segments_per_case": 3, "stage_wall_s": 600, "stop_on_numerical_failure": True},
              "scope": "Six fresh seed-2 CPD6 trajectories to 0.5 s; numerical response comparison only.",
              "source_hashes": {str(p): api.sha(p) for p in sorted(set(sources))},
              "inputs": {str(p): api.sha(p) for p in inputs}}
    design["binding"] = api.digest(design)
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    api.write(DESIGN, design)
    verify(design)
    print("FROZEN", api.sha(DESIGN), "cases", len(cases))


def configure():
    engine.DESIGN, engine.RUN, engine.EVAL = DESIGN, RUN, EVAL
    engine.verify = verify
    engine.__file__ = str(Path(__file__).resolve())
    api.fields.load = lambda *args, **kwargs: cpd6.load()


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare()
    else:
        configure()
        raise SystemExit(engine.run() if sys.argv[1] == "run" else engine.worker(sys.argv[2], int(sys.argv[3])))
