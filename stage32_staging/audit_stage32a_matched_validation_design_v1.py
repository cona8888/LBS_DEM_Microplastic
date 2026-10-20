from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage32a_matched_constant_head_validation_20260828"
DESIGN = ROOT / "stage32_designs" / STUDY / "design_01"
OUT = ROOT / "stage32_evaluations" / STUDY / "design_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    protocol = load(DESIGN / "resolved_protocol.json")
    completion = load(DESIGN / "completion.json")
    with (DESIGN / "design_matrix.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with (DESIGN / "data_capture_template.csv").open(newline="", encoding="utf-8") as handle:
        capture = list(csv.DictReader(handle))
        capture_fields = handle.seek(0) or next(csv.reader(handle))
    source_checks = {key: Path(binding["path"]).is_file() and sha(Path(binding["path"])) == binding["sha256"]
                     for key, binding in protocol["source_bindings"].items()}
    counts = Counter(row["group_id"] for row in rows)
    run_order = [int(row["run_order"]) for row in rows]
    no_triples = all(not (rows[i]["group_id"] == rows[i + 1]["group_id"] == rows[i + 2]["group_id"]) for i in range(len(rows) - 2))
    expected_capture = {"dry_sand_mass_g", "fibre_mass_g", "initial_void_ratio", "final_void_ratio", "water_temperature_c",
                        "head_difference_m", "collection_time_s", "collected_water_mass_g", "K20_m_s", "valid", "rejection_reason"}
    checks = {
        "protocol_and_completion_passed": protocol.get("passed") is True and completion.get("passed") is True,
        "all_source_hashes_bound": all(source_checks.values()),
        "contract_bound": Path(protocol["contract"]["path"]).is_file() and sha(Path(protocol["contract"]["path"])) == protocol["contract"]["sha256"],
        "exact_38_rows": len(rows) == len(capture) == 38,
        "phase_counts_exact": sum(row["phase"] == "1" for row in rows) == 30 and sum(row["phase"] == "2" for row in rows) == 8,
        "phase1_groups_balanced": all(counts[group] == 6 for group in ("clean", "iso_0p004691", "iso_0p051576", "iso_0p098418", "iso_0p401820")),
        "phase2_groups_balanced": counts["parallel_0p401820"] == counts["transverse_0p401820"] == 4,
        "run_order_unique_complete": run_order == list(range(1, 39)),
        "randomization_no_three_identical_consecutive": no_triples,
        "capture_schema_complete": expected_capture.issubset(set(capture_fields)),
        "monotonicity_not_a_gate": protocol["design"]["monotonicity_is_not_acceptance_gate"] is True,
        "authority_narrow": not any(protocol["authority"].values()),
        "immutable_artifact_hashes": all(sha(DESIGN / name) == digest for name, digest in completion["artifacts"].items()),
    }
    passed = all(checks.values())
    audit = {"schema": "lbs.stage32a-matched-validation-design-audit.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": passed,
        "status": "passed_prospective_validation_design" if passed else "failed_prospective_validation_design",
        "checks": checks, "source_checks": source_checks, "group_counts": dict(sorted(counts.items())),
        "bindings": {"protocol_sha256": sha(DESIGN / "resolved_protocol.json"),
                     "completion_sha256": sha(DESIGN / "completion.json"),
                     "design_matrix_sha256": sha(DESIGN / "design_matrix.csv"),
                     "data_capture_template_sha256": sha(DESIGN / "data_capture_template.csv")},
        "decision": "Design is ready for laboratory planning; no physical validation claim exists until blinded data evaluation." if passed else "Fail closed; repair design before use.",
        "authority": {"laboratory_execution": False, "physical_validation_claim": False, "new_physics": False}}
    OUT.mkdir(parents=True)
    (OUT / "design_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "passed": passed, "checks": checks}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
