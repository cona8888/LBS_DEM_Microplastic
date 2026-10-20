"""Seal a planning-only release; does not import or run any physics engine."""
import copy
import hashlib
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RELEASE = ROOT / "stage36_designs/stage36a_release_transport_feasibility_20260906/release_01"
EXPECTED_SOURCES = {
    "stage31_staging/run_stage31c_replicated_nested_mechanics_v1.py": "bdcd5aedd1d5cb5384f4a00e9468be09f3f0fa53cb5cdf52f660e40ea4fcd255",
    "stage31_staging/run_stage31f_selected_replicated_cpd4_gpu_v1.py": "e3035c3cb6af4b00922d3b8636c3e475db5e094f93a403084d83b82bae5378cc",
    "src/simulate_microplastic_permeability_study.m": "3c08c252a94053719a16a8cc2ccf5ad258c2a4aad8f72c20d4abae3644d62702",
    "native_matdem/native_matdem_run_coupled_permeability.m": "502924d1b524f95f1425430e7a0aca2d99b09f7193ed2a315e0aad8eab09d321",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(design):
    require(design["status"] == "design_structure_frozen_not_execution_ready", "status")
    require(design["authority"] == {
        "planning_and_readonly_audit": True,
        "verification_simulation_execution": False,
        "soil_pilot_execution": False,
        "gpu_campaign_execution": False,
        "modify_prior_evidence": False,
    }, "authority")
    expected = set(itertools.product(
        ["n216_s1", "n216_s2", "n216_s3"], ["intact", "split2"], ["low", "high"]))
    observed = [(r["packing_id"], r["morphology"], r["flow_level"]) for r in design["groups"]]
    require(len(observed) == 12 and set(observed) == expected, "factorial coverage")
    require(len({r["group_id"] for r in design["groups"]}) == 12, "duplicate group")
    require(all(r["placement_repeats"] == ["A", "B", "C"] for r in design["groups"]), "repeats")
    require(design["proposed_realization_count"] == 36, "realization count")
    require(design["independent_packing_count"] == 3, "packing replication")
    require(len(design["unresolved"]) >= 10 and all(v is None for v in design["unresolved"].values()), "unresolved values concealed")


def main():
    target = RELEASE / "planning_audit.json"
    require(not target.exists(), "immutable planning audit already exists")
    design = json.loads((RELEASE / "design.json").read_text(encoding="utf-8"))
    validate(design)
    negative_tests = []
    for name in ("execution_flag", "missing_group", "fabricated_flow"):
        bad = copy.deepcopy(design)
        if name == "execution_flag":
            bad["authority"]["soil_pilot_execution"] = True
        elif name == "missing_group":
            bad["groups"].pop()
        else:
            bad["unresolved"]["flow_low_m_s"] = 1.0
        try:
            validate(bad)
        except ValueError:
            negative_tests.append(name)
        else:
            raise ValueError("negative test was not rejected: " + name)
    bindings = {}
    for relative, expected in EXPECTED_SOURCES.items():
        path = ROOT / relative
        actual = digest(path)
        require(actual == expected, "source changed: " + relative)
        bindings[relative] = actual
    for path in [ROOT / "config/native_matdem_hydromechanical_config.m",
                 ROOT / "stage26_staging/build_stage26n_safe_release_pilot_v1.py",
                 RELEASE / "design.json", RELEASE / "FEASIBILITY_AND_PILOT_CONTRACT.md",
                 Path(__file__).resolve()]:
        bindings[str(path.relative_to(ROOT))] = digest(path)
    result = {
        "status": "planning_package_checked_no_transport_simulation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "planning_checks_passed": True,
        "transport_verified": False,
        "pilot_execution_ready": False,
        "simulation_runs_started": 0,
        "group_count": 12,
        "proposed_realization_count": 36,
        "unresolved_fields": list(design["unresolved"]),
        "negative_design_tests_passed": negative_tests,
        "sha256_bindings": bindings,
    }
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
