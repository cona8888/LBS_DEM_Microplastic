#!/usr/bin/env python3
"""Hostile synthetic verification of the Stage33E design-only auditor."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STAGING = ROOT / "stage33_staging"
AUDITOR_PATH = STAGING / "audit_stage33e_empirical_readiness_handoff_v1.py"
DEFAULT_RELEASE = ROOT / "stage33_designs" / "stage33e_empirical_readiness_handoff_20260901" / "release_01"
DEFAULT_OUTPUT = ROOT / "stage33_evaluations" / "stage33e_empirical_readiness_handoff_20260901" / "synthetic_verification_01"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def mutate_json(path: Path, fn: Callable[[Any], None]) -> None:
    payload = load_json(path)
    fn(payload)
    write_json(path, payload)


def mutate_csv(path: Path, fn: Callable[[list[str], list[dict[str, str]]], None]) -> None:
    with path.open("r", newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    fn(headers, rows)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"), key=lambda p: str(p).lower())
        if path.is_file()
    }


def import_auditor():
    spec = importlib.util.spec_from_file_location("stage33e_auditor", AUDITOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import Stage33E auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mutation_map() -> dict[str, Callable[[Path], None]]:
    return {
        "mutated_stage33d_lineage": lambda root: mutate_json(
            root / "lineage_manifest.json",
            lambda j: j["sources"]["stage33d_resolved_design"].update({"sha256": "0" * 64}),
        ),
        "mutated_stage33do_lineage": lambda root: mutate_json(
            root / "lineage_manifest.json",
            lambda j: j["sources"]["stage33do_synthetic_verification"].update({"sha256": "1" * 64}),
        ),
        "failed_or_missing_parent_audit": lambda root: mutate_json(
            root / "lineage_manifest.json",
            lambda j: (j["sources"].pop("stage33d_design_audit"), j.update({"source_n": j["source_n"] - 1})),
        ),
        "synthetic_release_submitted_as_empirical": lambda root: mutate_json(
            root / "evidence_slot_registry.json",
            lambda j: j["slots"][0].update(
                {
                    "manifest_path": str(ROOT / "stage33_evaluations" / "stage33do_operational_workflow_synthetic_qualification_20260901" / "verification_01" / "verification.json"),
                    "manifest_sha256": "d01a2c589738f10b36787d11384ec6f042082a7db76c7a50257c004b204cbf36",
                    "populated": True,
                    "verified": True,
                    "decision": "accepted",
                }
            ),
        ),
        "prepopulated_or_inconsistent_slot": lambda root: mutate_json(
            root / "evidence_slot_registry.json",
            lambda j: j["slots"][3].update({"manifest_path": "C:\\REAL\\commitment.json", "populated": False}),
        ),
        "missing_duplicate_or_unknown_slot": lambda root: mutate_json(
            root / "evidence_slot_registry.json",
            lambda j: j["slots"][8].update({"slot_id": "unknown_evidence_slot"}),
        ),
        "state_advance": lambda root: mutate_json(
            root / "readiness_state_machine.json",
            lambda j: (j.update({"current_state": "S20"}), j["states"][1].update({"active": False}), j["states"][2].update({"active": True})),
        ),
        "authority_enabled": lambda root: mutate_json(
            root / "authority_matrix.json",
            lambda j: j["authority"].update({"laboratory_execution": True}),
        ),
        "optional_chemistry_or_prediction_unlocks_core_gate": lambda root: mutate_json(
            root / "readiness_gate_graph.json",
            lambda j: next(row for row in j["gates"] if row["gate_id"] == "G20")["prerequisites"].append("molecular_and_orthogonal_chemistry_release_for_degradation_claim"),
        ),
        "role_overlap_or_secret_leakage": lambda root: mutate_json(
            root / "roles_and_key_custody_template.json",
            lambda j: j.update({"operator_id": "ROLE-001", "analyst_id": "ROLE-001", "custodian_id": "ROLE-001", "real_secret_or_key_sha256": "2" * 64}),
        ),
        "extra_unmanifested_artifact": lambda root: (root / "unmanifested_payload.json").write_text("{}\n", encoding="utf-8"),
        "altered_threshold_or_monotonicity": lambda root: mutate_json(
            root / "evidence_requirements.json",
            lambda j: j["stage33d_acceptance_gates"].update({"maximum_clean_cv_within_block": 0.10, "monotonicity_is_not_a_gate": False}),
        ),
        "production_toolchain_falsely_enabled": lambda root: mutate_json(
            root / "production_operational_toolchain_audit_template.json",
            lambda j: j.update({"populated": True, "verified": True, "production_mode_supported": True, "status": "passed"}),
        ),
        "successful_release_path_in_lineage": lambda root: mutate_json(
            root / "lineage_manifest.json",
            lambda j: j["sources"]["stage33do_synthetic_verification"].update(
                {"path": str(ROOT / "stage33_evaluations" / "stage33do_operational_workflow_synthetic_qualification_20260901" / "verification_01" / "successful_release" / "release" / "release_manifest.json")}
            ),
        ),
        "source_mutation": lambda root: mutate_json(
            root / "lineage_manifest.json",
            lambda j: j["sources"]["stage33e_builder"].update({"sha256": "3" * 64}),
        ),
        "output_overwrite": lambda root: None,
        "prediction_timestamp_after_reveal": lambda root: mutate_json(
            root / "evidence_slot_registry.json",
            lambda j: next(row for row in j["slots"] if row["slot_id"] == "pet_specific_frozen_numerical_predictions_for_model_validation").update(
                {"freeze_utc": "2030-01-02T00:00:00Z", "receipt_utc": "2030-01-01T00:00:00Z", "populated": True, "verified": True, "decision": "accepted"}
            ),
        ),
        "chemistry_only_degradation_claim": lambda root: (
            mutate_json(root / "readiness_decision.json", lambda j: j["readiness"].update({"degradation_proxy_claim_ready": True})),
            mutate_json(
                root / "evidence_slot_registry.json",
                lambda j: next(row for row in j["slots"] if row["slot_id"] == "molecular_and_orthogonal_chemistry_release_for_degradation_claim").update({"populated": True, "verified": True, "decision": "accepted"}),
            ),
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    release = args.release.resolve()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"E33E_OVERWRITE_REFUSED: output exists: {output}")
    if not release.is_dir():
        raise RuntimeError(f"release missing: {release}")
    output.parent.mkdir(parents=True, exist_ok=True)

    auditor = import_auditor()
    release_before = tree_hashes(release)
    positive_audit, _, _ = auditor.audit_release(release)

    temp_root = Path(tempfile.mkdtemp(prefix=".stage33e_verify.", dir=str(output.parent)))
    results: dict[str, Any] = {}
    try:
        for challenge, mutate in mutation_map().items():
            challenge_root = temp_root / challenge / "release"
            challenge_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(release, challenge_root)
            if challenge == "output_overwrite":
                occupied = temp_root / challenge / "occupied_audit_output"
                occupied.mkdir(parents=True)
                proc = subprocess.run(
                    [sys.executable, str(AUDITOR_PATH), "--release", str(release), "--output", str(occupied)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                rejected = proc.returncode != 0 and "E33E_OVERWRITE_REFUSED" in proc.stderr
                error = proc.stderr[-1000:]
            else:
                mutate(challenge_root)
                try:
                    auditor.audit_release(challenge_root)
                except Exception as exc:
                    rejected = True
                    error = f"{type(exc).__name__}: {exc}"
                else:
                    rejected = False
                    error = "mutation unexpectedly accepted"
            results[challenge] = {
                "expected_rejection": True,
                "rejected": rejected,
                "passed": rejected,
                "error_tail": error[-1000:],
            }

        release_after = tree_hashes(release)
        if release_before != release_after:
            raise RuntimeError("E33E_INPUT_MUTATION: original release changed during hostile verification")
        failed = [name for name, result in results.items() if not result["passed"]]
        if failed:
            raise RuntimeError("E33E_HOSTILE_VERIFICATION_FAILED: " + ", ".join(failed))

        verification = {
            "schema": "pet.stage33e-empirical-readiness-handoff-synthetic-verification.v1",
            "stage": "Stage33E",
            "created_utc": now_utc(),
            "status": "passed_design_only_hostile_verification",
            "passed": True,
            "test_only": True,
            "no_empirical_data": True,
            "no_real_identifiers": True,
            "no_real_key": True,
            "no_laboratory_execution": True,
            "no_numerical_execution": True,
            "positive_audit": {
                "passed": positive_audit["passed"],
                "check_n": positive_audit["check_n"],
                "status": positive_audit["status"],
            },
            "negative_challenge_n": len(results),
            "negative_challenges_passed_n": sum(result["passed"] for result in results.values()),
            "negative_challenges": results,
            "input_mutation": False,
            "readiness": {
                "laboratory_hydraulic_execution_ready": False,
                "cross_domain_unblinding_ready": False,
                "pet_specific_model_validation_ready": False,
                "degradation_proxy_claim_ready": False,
            },
            "conclusion": "The design auditor accepted the exact empty release and rejected all hostile synthetic mutations. No empirical or production readiness was tested.",
            "stop_boundary": positive_audit["stop_boundary"],
        }

        out_temp = temp_root / "verification_output"
        out_temp.mkdir()
        write_json(out_temp / "verification.json", verification)
        write_json(
            out_temp / "completion.json",
            {
                "schema": "pet.stage33e-empirical-readiness-handoff-synthetic-verification-completion.v1",
                "stage": "Stage33E",
                "created_utc": now_utc(),
                "status": "complete",
                "passed": True,
                "verification_path": str(output / "verification.json"),
                "verification_sha256": sha256(out_temp / "verification.json"),
                "negative_challenge_n": len(results),
                "all_negative_challenges_rejected": True,
                "input_mutation": False,
                "all_authority_closed": True,
            },
        )
        os.replace(out_temp, output)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    print(json.dumps({"passed": True, "output": str(output), "negative_challenge_n": len(results)}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL-CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
