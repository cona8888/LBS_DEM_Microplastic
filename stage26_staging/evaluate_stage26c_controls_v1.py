"""Independently verify Stage26c fixed-prefilter control outcomes."""

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26c_fixed_prefilter_controls_execution_v1.json"
RUN_ROOT = ROOT / "stage26_runs/stage26c_revision3_fixed_prefilter_20260816/controls_01"
OUTPUT = ROOT / "stage26_evaluations/stage26c_revision3_fixed_prefilter_20260816/controls_outcome_evaluation_01/evaluation.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


cfg = load(CONFIG)
records = {}
checks = {}
for trial in cfg["trials"]:
    trial_id = trial["trial_id"]
    root = RUN_ROOT / trial_id
    result_path = root / "result.json"
    completion_path = root / "completion.json"
    history_path = root / "fixed_conditioning_history.csv"
    result = load(result_path)
    completion = load(completion_path)
    with history_path.open("r", newline="", encoding="utf-8") as stream:
        history = list(csv.DictReader(stream))
    checks[trial_id + "_bundle_exists"] = all(path.is_file() for path in (result_path, completion_path, history_path))
    checks[trial_id + "_result_hash"] = digest(result_path) == completion["result_sha256"]
    checks[trial_id + "_history_hash"] = digest(history_path) == result["artifacts"]["fixed_conditioning_history_csv_sha256"]
    checks[trial_id + "_source_hashes"] = result["source_hashes"]["config"] == digest(CONFIG) and result["source_hashes"]["runner"] == cfg["sources"]["runner_sha256"] and result["source_hashes"]["common"] == cfg["sources"]["common_sha256"] and result["source_hashes"]["stage25_checkpoint"] == cfg["sources"]["stage25_checkpoint_sha256"] and result["source_hashes"]["placement"] == trial["placement_sha256"]
    checks[trial_id + "_bounded_fixed_protocol"] = result["protocol"] == {"all_fibres_fixed": True, "free_release": False, "steps_per_block": 500, "blocks": 10} and len(history) == 10
    checks[trial_id + "_exact_insertion_contacts"] = result["insertion"]["distinct_sand_contacts_by_fibre"] == [2] * trial["fibre_count"] and result["insertion"]["declared_anchor_contacts_by_fibre"] == [2] * trial["fibre_count"]
    records[trial_id] = {"completion_path": str(completion_path), "completion_sha256": digest(completion_path), "result_path": str(result_path), "result_sha256": digest(result_path), "history_path": str(history_path), "history_sha256": digest(history_path), "control_reproduced": completion["control_reproduced"], "insertion_contacts": result["insertion"]["distinct_sand_contacts_by_fibre"], "block1_contacts": result["terminal"]["distinct_sand_contacts_by_fibre"] if not history else json.loads(history[0]["distinct_sand_contacts_by_fibre"]), "terminal_contacts": result["terminal"]["distinct_sand_contacts_by_fibre"], "terminal_anchors": result["terminal"]["declared_anchor_contacts_by_fibre"], "terminal_mean_stress_pa": result["terminal"]["mean_effective_stress_pa_compression_positive"], "terminal_unbalanced_force": result["terminal"]["unbalanced_force"], "maximum_sand_displacement_over_D50": max(float(row["maximum_nonaffine_sand_displacement_over_D50"]) for row in history)}

checks["positive_control_failed_persistence_as_recorded"] = records["positive_stage26a"]["control_reproduced"] is False and records["positive_stage26a"]["block1_contacts"] == [1] and records["positive_stage26a"]["terminal_contacts"] == [1]
checks["negative_control_reproduced_known_loss"] = records["negative_stage26b_failure"]["control_reproduced"] is True and records["negative_stage26b_failure"]["block1_contacts"] == [0, 2] and records["negative_stage26b_failure"]["terminal_contacts"] == [0, 2]
checks["candidate_not_executed"] = not (ROOT / "stage26_runs/stage26c_revision3_fixed_prefilter_20260816/candidate_01").exists()
passed = all(checks.values())
scientific_passed = records["positive_stage26a"]["control_reproduced"] is True and records["negative_stage26b_failure"]["control_reproduced"] is True
evaluation = {"schema": "lbs.stage26c-fixed-prefilter-controls-outcome-evaluation.v1", "passed": passed, "scientific_outcome_passed": scientific_passed, "status": "verified_control_gate_failure_candidate_blocked" if passed and not scientific_passed else "unexpected_control_outcome", "checks": checks, "records": records, "diagnosis": "Both controls created exactly their declared contacts at insertion. The negative control reproduced known loss, but the positive Stage26a initial placement lost one anchor during block 1 and never recovered it; therefore this positive control does not qualify the fixed-conditioning protocol.", "authority": {"prefilter_redesign_authorized": passed and not scientific_passed, "candidate_yade_execution_authorized": False, "two_fibre_free_release_authorized": False, "flow_execution_authorized": False}, "claim_boundary": cfg["claim_boundary"]}
OUTPUT.parent.mkdir(parents=True, exist_ok=False)
OUTPUT.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": passed, "scientific_outcome_passed": scientific_passed, "evaluation_sha256": digest(OUTPUT)}, sort_keys=True))
if not passed:
    raise SystemExit(1)
