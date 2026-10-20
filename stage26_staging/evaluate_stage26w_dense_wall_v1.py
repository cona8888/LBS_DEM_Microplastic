from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_designs" / "stage26w_dense_wall_shrink_regrow_20260823" / "design_01" / "config.json"
RUN = ROOT / "stage26_runs" / "stage26w_dense_wall_shrink_regrow_20260823" / "pilot_01"
OUT = ROOT / "stage26_evaluations" / "stage26w_dense_wall_shrink_regrow_20260823" / "evaluation_01"
EVALUATOR = ROOT / "stage26_staging" / "evaluate_stage26w_dense_wall_v1.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable Stage26w evaluation exists")
    result_path = RUN / "result.json"
    completion_path = RUN / "completion.json"
    history_path = RUN / "history.csv"
    state_path = RUN / "qualified_dense_wall_state.yade.gz"
    for path in (CONFIG, result_path, completion_path, history_path):
        if not path.is_file():
            raise RuntimeError(f"missing required evidence: {path}")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    with history_path.open("r", newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    terminal = result["terminal"]
    checks = {
        "config_hash_matches_result": result["source_hashes"]["config"] == sha256(CONFIG),
        "runner_hash_matches_config": result["source_hashes"]["runner"] == cfg["sources"]["runner"]["sha256"],
        "input_state_hash_matches_config": result["source_hashes"]["input_state"] == cfg["sources"]["input_state"]["sha256"],
        "completion_binds_result": completion["result"]["sha256"] == sha256(result_path),
        "result_binds_history": result["artifacts"]["history"]["sha256"] == sha256(history_path),
        "state_exists": state_path.is_file(),
        "result_binds_state": state_path.is_file() and result.get("artifacts", {}).get("state", {}).get("sha256") == sha256(state_path),
        "result_passed": result.get("passed") is True,
        "completion_passed": completion.get("passed") is True,
        "qualified_status": result.get("status") == "qualified_dense_wall_state" and completion.get("status") == "qualified_dense_wall_state",
        "all_runner_checks_pass": all(result.get("checks", {}).values()),
        "history_nonempty": len(rows) > 0,
        "history_terminal_matches_result": bool(rows) and int(rows[-1]["record"]) == int(terminal["record"]),
        "particle_count": int(terminal["particle_count"]) == 216,
        "no_leakage": int(terminal["leaked_particle_count"]) == 0,
        "authority_remains_bounded": not any(result.get("authority", {}).get(name, False) for name in (
            "pore_throat_extraction_authorized",
            "fibre_execution_authorized",
            "mobile_sand_execution_authorized",
            "flow_execution_authorized",
            "permeability_claim_authorized",
            "production_parametric_study_authorized",
        )),
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26w-dense-wall-independent-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "dense_wall_state_accepted" if passed else "dense_wall_state_not_accepted",
        "passed": passed,
        "checks": checks,
        "terminal": terminal,
        "claim_boundary": cfg["claim_boundary"],
        "sources": {
            "config": {"path": str(CONFIG), "sha256": sha256(CONFIG)},
            "result": {"path": str(result_path), "sha256": sha256(result_path)},
            "completion": {"path": str(completion_path), "sha256": sha256(completion_path)},
            "history": {"path": str(history_path), "sha256": sha256(history_path)},
            "state": {"path": str(state_path), "sha256": sha256(state_path)} if state_path.is_file() else None,
            "evaluator": {"path": str(EVALUATOR), "sha256": sha256(EVALUATOR)},
        },
        "authority": {
            "pore_throat_extraction_authorized": passed,
            "fixed_sand_flexible_fibre_design_authorized": passed,
            "fixed_sand_flexible_fibre_execution_authorized": False,
            "mobile_sand_execution_authorized": False,
            "flow_execution_authorized": False,
            "permeability_claim_authorized": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=False)
    evaluation_path = OUT / "evaluation.json"
    evaluation_path.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
    checkpoint = {
        "schema": "lbs.stage26w-dense-wall-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "stage26w_dense_state_accepted" if passed else "stage26w_closed_nonaccepting",
        "evaluation": {"path": str(evaluation_path), "sha256": sha256(evaluation_path)},
        "next_gate": "Read-only pore-throat extraction is authorized; fibre execution requires a separately frozen design." if passed else "No extraction or fibre execution is authorized.",
    }
    checkpoint_path = OUT / "checkpoint_manifest.json"
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2) + "\n", encoding="utf-8")
    print(evaluation_path)
    print(sha256(evaluation_path))
    print(checkpoint_path)
    print(sha256(checkpoint_path))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
