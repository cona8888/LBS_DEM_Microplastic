"""Independent pre-run audit for the offline placement campaign."""

import ast
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_revision2_placement_generation_execution_v1.json"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "placement_generation_prerun_evaluation_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable placement pre-run evaluation already exists")
    cfg = load_json(CONFIG)
    paths = {name: Path(value) for name, value in cfg["sources"].items() if not name.endswith("_sha256")}
    source_checkpoint = load_json(paths["generator_source_checkpoint"])
    preparation_checkpoint = load_json(paths["preparation_checkpoint"])
    network = load_json(paths["network"])
    with paths["trial_schedule"].open("r", newline="", encoding="utf-8") as stream:
        scheduled = [row for row in csv.DictReader(stream) if row["record_type"] == "candidate"]
    source_text = paths["generator"].read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imports.update(alias.name.split(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module.split(".")[0])
    candidates = cfg["candidates"]
    output = Path(cfg["execution"]["output"])
    checks = {
        "all_source_hashes_match": all(digest(path) == cfg["sources"][name + "_sha256"] for name, path in paths.items()),
        "source_and_preparation_checkpoints_passed": source_checkpoint.get("passed") is True and preparation_checkpoint.get("passed") is True,
        "exact_status_and_narrow_authority": cfg["status"] == "authorized_stage26b_revision2_placement_generation" and cfg["authority"]["placement_generation_authorized"] is True and all(value is False for name, value in cfg["authority"].items() if name != "placement_generation_authorized"),
        "host_python_only_no_yade": cfg["execution"]["host_python_only"] is True and cfg["execution"]["yade_invoked"] is False and "yade" not in imports and "subprocess" not in imports,
        "exact_twelve_candidates_and_seeds": (
            len(candidates) == 12
            and [row["candidate_index"] for row in candidates] == list(range(1, 13))
            and [row["seed"] for row in candidates] == [202608142100 + 17 * index for index in range(12)]
            and [row["candidate_id"] for row in candidates] == [row["trial_id"] for row in scheduled]
        ),
        "network_baseline_exact": network["sand_particle_count"] == 216 and network["sand_contact_count"] == 361 and network["load_bearing_particle_count"] == 175 and network["periodic"] is True,
        "predeclared_budget_and_gates_exact": (
            cfg["generator_contract"]["maximum_trials_per_candidate"] == 400000
            and cfg["generator_contract"]["maximum_initial_force_residual_relative"] == 0.05
            and cfg["generator_contract"]["maximum_initial_moment_residual_relative"] == 0.02
            and cfg["generator_contract"]["minimum_initial_fibre_fibre_clearance_m"] == 0.00041129327255147165
            and cfg["generator_contract"]["preserve_every_attempt_and_rejection"] is True
        ),
        "output_is_new_immutable": not output.exists() and cfg["execution"]["immutable_output"] is True,
        "exact_argv": cfg["execution"]["argv"] == ["python", "C:/MATDEM_MICROPLASTIC/stage26_staging/generate_stage26b_revision2_placements_v1.py", "--config", str(CONFIG).replace("\\", "/"), "--output", str(output).replace("\\", "/")],
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-revision2-placement-generation-prerun-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": passed,
        "status": "passed_exact_offline_placement_generation_prerun" if passed else "failed_placement_generation_prerun",
        "checks": checks,
        "evidence": {
            "config_path": str(CONFIG), "config_sha256": digest(CONFIG),
            "generator_path": str(paths["generator"]), "generator_sha256": digest(paths["generator"]),
            "source_checkpoint_path": str(paths["generator_source_checkpoint"]), "source_checkpoint_sha256": digest(paths["generator_source_checkpoint"]),
            "network_path": str(paths["network"]), "network_sha256": digest(paths["network"]),
            "auditor_sha256": digest(Path(__file__)),
        },
        "frozen_execution": cfg["execution"],
        "authority": {
            "authorized_next_activity": "Execute the exact offline placement campaign once, then independently verify and render all candidate outcomes before any YADE prefilter.",
            "placement_generation_authorized": passed,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False); stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(path)}, sort_keys=True))
    if not passed:
        print(json.dumps({"failed_checks": [name for name, value in checks.items() if not value]}, sort_keys=True)); raise SystemExit(2)


if __name__ == "__main__": main()
