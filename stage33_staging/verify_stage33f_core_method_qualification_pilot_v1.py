#!/usr/bin/env python3
"""Hostile synthetic verification of the Stage33F design-only auditor.

This verifier never creates laboratory observations, operational identifiers,
or numerical simulation results.  It accepts the exact immutable Stage33F
design release, copies that release into isolated temporary directories, and
requires the independent auditor to reject every hostile mutation.
"""

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
AUDITOR_PATH = STAGING / "audit_stage33f_core_method_qualification_pilot_v1.py"
DEFAULT_RELEASE = (
    ROOT
    / "stage33_designs"
    / "stage33f_core_method_qualification_pilot_20260901"
    / "release_01"
)
DEFAULT_OUTPUT = (
    ROOT
    / "stage33_evaluations"
    / "stage33f_core_method_qualification_pilot_20260901"
    / "synthetic_verification_01"
)


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def mutate_json(path: Path, fn: Callable[[Any], None]) -> None:
    payload = load_json(path)
    fn(payload)
    write_json(path, payload)


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def mutate_csv(
    path: Path, fn: Callable[[list[str], list[dict[str, str]]], None]
) -> None:
    headers, rows = load_csv(path)
    fn(headers, rows)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"), key=lambda item: str(item).lower())
        if path.is_file()
    }


def rebind_completion_to_copy(release: Path) -> None:
    """Bind completion records to an isolated copied release.

    The design completion deliberately stores absolute artifact paths.  A
    copied release would therefore be rejected for stale paths before the
    hostile mutation was reached.  Rebinding both paths and content metadata
    makes each negative challenge a semantic test of its named invariant.
    """

    completion_path = release / "completion.json"
    completion = load_json(completion_path)
    artifacts = completion.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise RuntimeError("completion.json has no artifact registry")
    for name, record in artifacts.items():
        if not isinstance(name, str) or not isinstance(record, dict):
            raise RuntimeError("completion artifact registry is malformed")
        artifact = release / name
        if not artifact.is_file():
            raise RuntimeError(f"completion artifact missing in copy: {name}")
        record["path"] = str(artifact)
        record["sha256"] = sha256(artifact)
        record["bytes"] = artifact.stat().st_size
    write_json(completion_path, completion)


def import_auditor() -> Any:
    if not AUDITOR_PATH.is_file():
        raise RuntimeError(f"Stage33F auditor missing: {AUDITOR_PATH}")
    spec = importlib.util.spec_from_file_location("stage33f_auditor", AUDITOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import Stage33F auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "audit_release", None)):
        raise RuntimeError("Stage33F auditor does not expose audit_release(release)")
    return module


def audit_payload(auditor: Any, release: Path) -> dict[str, Any]:
    result = auditor.audit_release(release)
    if isinstance(result, tuple):
        result = result[0]
    if not isinstance(result, dict):
        raise RuntimeError("Stage33F auditor returned a non-object result")
    return result


def first_dict(container: Any, preferred_keys: tuple[str, ...]) -> dict[str, Any]:
    if isinstance(container, dict):
        for key in preferred_keys:
            value = container.get(key)
            if isinstance(value, dict):
                return value
        for value in container.values():
            try:
                return first_dict(value, preferred_keys)
            except LookupError:
                pass
    elif isinstance(container, list):
        for value in container:
            try:
                return first_dict(value, preferred_keys)
            except LookupError:
                pass
    raise LookupError(f"no mapping found for preferred keys {preferred_keys}")


def first_list(container: Any, preferred_keys: tuple[str, ...]) -> list[Any]:
    if isinstance(container, dict):
        for key in preferred_keys:
            value = container.get(key)
            if isinstance(value, list):
                return value
        for value in container.values():
            try:
                return first_list(value, preferred_keys)
            except LookupError:
                pass
    elif isinstance(container, list):
        for value in container:
            try:
                return first_list(value, preferred_keys)
            except LookupError:
                pass
    raise LookupError(f"no list found for preferred keys {preferred_keys}")


def first_scalar_key(container: Any, keys: tuple[str, ...]) -> tuple[dict[str, Any], str]:
    if isinstance(container, dict):
        for key in keys:
            if key in container and not isinstance(container[key], (dict, list)):
                return container, key
        for value in container.values():
            try:
                return first_scalar_key(value, keys)
            except LookupError:
                pass
    elif isinstance(container, list):
        for value in container:
            try:
                return first_scalar_key(value, keys)
            except LookupError:
                pass
    raise LookupError(f"none of the scalar keys exists: {keys}")


def set_first_scalar(container: Any, keys: tuple[str, ...], value: Any) -> None:
    parent, key = first_scalar_key(container, keys)
    parent[key] = value


def mutate_lineage_source_hash(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        sources = first_dict(payload, ("sources", "source_bindings", "bindings"))
        source = next(value for value in sources.values() if isinstance(value, dict))
        set_first_scalar(source, ("sha256", "hash"), "0" * 64)

    mutate_json(release / "lineage_manifest.json", edit)


def mutate_stage33e_interface_hash(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        set_first_scalar(
            payload,
            (
                "stage33e_resolved_handoff_sha256",
                "resolved_handoff_sha256",
                "parent_completion_sha256",
                "source_sha256",
                "completion_sha256",
                "sha256",
            ),
            "1" * 64,
        )

    mutate_json(release / "stage33e_interface_bindings.json", edit)


def mutate_stage33e_interface_path(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        interfaces = first_list(payload, ("interfaces",))
        target = next(row for row in interfaces if isinstance(row, dict))
        target["source_path"] = str(
            ROOT
            / "stage33_evaluations"
            / "stage33do_operational_workflow_synthetic_qualification_20260901"
            / "verification_01"
            / "successful_release"
            / "release"
            / "release_manifest.json"
        )

    mutate_json(release / "stage33e_interface_bindings.json", edit)


def mutate_stage33e_parent_state(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        try:
            set_first_scalar(
                payload,
                ("parent_state", "stage33e_state", "current_state"),
                "S20_EVIDENCE_STAGED_UNVERIFIED",
            )
        except LookupError:
            payload["stage33e_state"] = "S20_EVIDENCE_STAGED_UNVERIFIED"

    mutate_json(release / "stage33e_interface_bindings.json", edit)


def mutate_stage33e_slot_autoaccept(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        interfaces = first_list(payload, ("interfaces",))
        target = next(row for row in interfaces if isinstance(row, dict))
        target.update(
            {
                "current_state": "POPULATED_AND_ACCEPTED",
                "automatic_population": True,
                "candidate_manifest_path": r"C:\REAL\evidence.json",
                "candidate_manifest_sha256": "2" * 64,
            }
        )
        payload["automatic_stage33e_acceptance"] = True

    mutate_json(release / "stage33e_interface_bindings.json", edit)


def mutate_pilot_state_advance(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        set_first_scalar(
            payload,
            ("current_state", "active_state"),
            "P20_REAL_PILOT_INPUTS_STAGED_UNVERIFIED",
        )
        try:
            states = first_list(payload, ("states",))
            for row in states:
                if isinstance(row, dict) and "active" in row:
                    row["active"] = False
            for row in states:
                if isinstance(row, dict) and str(row.get("state_id", row.get("name", ""))).startswith("P20"):
                    row["active"] = True
                    break
        except LookupError:
            pass

    mutate_json(release / "pilot_state_machine.json", edit)


def mutate_skipped_transition(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        requirements = payload.get("transition_requirements")
        if not isinstance(requirements, list) or not requirements:
            raise RuntimeError("state transition requirements are missing")
        requirements[-1] = (
            "state skips from P10 directly to P70 are allowed without prior evidence"
        )

    mutate_json(release / "pilot_state_machine.json", edit)


def mutate_authority_enabled(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        authority = first_dict(payload, ("authority", "authorities"))
        if authority:
            authority[next(iter(authority))] = True
        else:
            authority["laboratory_execution"] = True

    mutate_json(release / "authority_matrix.json", edit)


def mutate_real_identifier(release: Path) -> None:
    mutate_json(
        release / "q0_requirements_freeze_template.json",
        lambda payload: payload.update(
            {
                "operator_id": "REAL-OPERATOR-001",
                "instrument_id": "REAL-INSTRUMENT-001",
                "template_status": "POPULATED",
            }
        ),
    )


def mutate_real_key(release: Path) -> None:
    mutate_json(
        release / "q0_requirements_freeze_template.json",
        lambda payload: payload.update(
            {
                "real_secret_or_key_path": r"C:\RESTRICTED\production.key",
                "real_secret_or_key_sha256": "3" * 64,
            }
        ),
    )


def append_real_execution_row(headers: list[str], rows: list[dict[str, str]]) -> None:
    if not headers:
        raise RuntimeError("pilot execution manifest has no headers")
    row = {header: "" for header in headers}
    for header in headers:
        lowered = header.lower()
        if lowered.endswith("id") or "identifier" in lowered:
            row[header] = "REAL-PILOT-001"
        elif any(token in lowered for token in ("value", "mass", "time", "temperature", "head")):
            row[header] = "1.0"
        elif "status" in lowered:
            row[header] = "complete"
    rows.append(row)


def mutate_real_observation_row(release: Path) -> None:
    mutate_csv(
        release / "pilot_execution_manifest_template.csv", append_real_execution_row
    )


def mutate_deviation_row(release: Path) -> None:
    def edit(headers: list[str], rows: list[dict[str, str]]) -> None:
        if not headers:
            raise RuntimeError("deviation register has no headers")
        row = {header: "" for header in headers}
        row[headers[0]] = "REAL-DEVIATION-001"
        if len(headers) > 1:
            row[headers[1]] = "post-outcome threshold revision"
        rows.append(row)

    mutate_csv(release / "calibration_capture_template.csv", edit)


def mutate_invented_threshold(release: Path) -> None:
    def edit(headers: list[str], rows: list[dict[str, str]]) -> None:
        if not rows:
            raise RuntimeError("acceptance-rule registry has no rows")
        target = next(
            (
                row
                for row in rows
                if any(
                    token in " ".join(row.values()).lower()
                    for token in ("future", "blank", "derive", "q0", "unpopulated")
                )
            ),
            rows[-1],
        )
        required = {
            "operator",
            "threshold_value",
            "threshold_units",
            "threshold_source_role",
            "threshold_source_path",
            "threshold_source_sha256",
            "prospective_rule_frozen",
            "current_status",
        }
        if not required.issubset(headers):
            raise RuntimeError("acceptance-rule registry lacks method-rule fields")
        target.update(
            {
                "operator": "<=",
                "threshold_value": "0.123456",
                "threshold_units": "invented_units",
                "threshold_source_role": "unbound_assertion",
                "threshold_source_path": "",
                "threshold_source_sha256": "",
                "prospective_rule_frozen": "true",
                "current_status": "INVENTED_AND_FROZEN",
            }
        )

    mutate_csv(release / "pilot_acceptance_rule_registry.csv", edit)


def mutate_inherited_gate(release: Path) -> None:
    def edit(headers: list[str], rows: list[dict[str, str]]) -> None:
        if not rows:
            raise RuntimeError("acceptance-rule registry has no rows")
        target = next(
            (
                row
                for row in rows
                if any(
                    token in " ".join(row.values()).lower()
                    for token in ("0.005", "0.99", "0.05", "0.744", "20.0")
                )
            ),
            rows[0],
        )
        if "threshold_value" not in headers:
            raise RuntimeError("threshold_value field missing")
        target["threshold_value"] = "999"

    mutate_csv(release / "pilot_acceptance_rule_registry.csv", edit)


def mutate_monotonicity(release: Path) -> None:
    def edit(headers: list[str], rows: list[dict[str, str]]) -> None:
        target = next(
            (
                row
                for row in rows
                if "monotonic" in " ".join(row.values()).lower()
            ),
            None,
        )
        if target is None:
            raise RuntimeError("monotonicity rule row missing")
        if "threshold_value" not in headers:
            raise RuntimeError("threshold_value field missing")
        target["threshold_value"] = "false"
        target["current_status"] = "MONOTONICITY_REQUIRED"

    mutate_csv(release / "pilot_acceptance_rule_registry.csv", edit)


def mutate_missing_work_package(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        packages = first_list(payload, ("work_packages", "packages", "modules"))
        if not packages:
            raise RuntimeError("work-package registry is empty")
        packages.pop()
        for key in ("work_package_n", "package_n", "module_n"):
            if key in payload and isinstance(payload[key], int):
                payload[key] -= 1

    mutate_json(release / "pilot_work_package_registry.json", edit)


def mutate_duplicate_work_package(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        packages = first_list(payload, ("work_packages", "packages", "modules"))
        if not packages:
            raise RuntimeError("work-package registry is empty")
        packages.append(json.loads(json.dumps(packages[0])))
        for key in ("work_package_n", "package_n", "module_n"):
            if key in payload and isinstance(payload[key], int):
                payload[key] += 1

    mutate_json(release / "pilot_work_package_registry.json", edit)


def mutate_q1_reused_in_q2(release: Path) -> None:
    mutate_json(
        release / "effluent_method_plan_template.json",
        lambda payload: payload.update(
            {
                "q1_development_data_reuse_in_q2": True,
                "q2_independent_holdout_plan": "reuse Q1 development observations",
            }
        ),
    )


def mutate_confirmatory_material_allowed(release: Path) -> None:
    mutate_json(
        release / "resolved_pilot_design.json",
        lambda payload: payload.update(
            {
                "stage33d_confirmatory_material_allowed": True,
                "confirmatory_batch_reuse_allowed": True,
            }
        ),
    )


def mutate_test_asset_reuse(release: Path) -> None:
    mutate_json(
        release / "resolved_pilot_design.json",
        lambda payload: payload.update(
            {
                "stage33do_test_asset_path": str(
                    ROOT
                    / "stage33_evaluations"
                    / "stage33do_operational_workflow_synthetic_qualification_20260901"
                    / "verification_01"
                    / "successful_release"
                ),
                "stage33do_test_identifiers_reusable": True,
            }
        ),
    )


def mutate_evidence_autoaccept(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        products = first_list(payload, ("products", "evidence_products", "slots"))
        target = next(row for row in products if isinstance(row, dict))
        target.update(
            {
                "generated": True,
                "submitted": True,
                "verified": True,
                "automatic_stage33e_acceptance": True,
                "manifest_path": r"C:\REAL\candidate_evidence.json",
                "manifest_sha256": "5" * 64,
            }
        )

    mutate_json(release / "pilot_evidence_product_registry.json", edit)


def mutate_gate_autoaccept(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        gates = first_list(payload, ("gates",))
        target = next(
            row
            for row in gates
            if isinstance(row, dict) and row.get("current_status") == "blocked"
        )
        target["current_status"] = "pass"
        payload["passing_gate_n"] = int(payload.get("passing_gate_n", 1)) + 1

    mutate_json(release / "pilot_gate_graph.json", edit)


def mutate_readiness_promoted(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        payload["q0_requirements_populated"] = True
        payload["q1_development_executed"] = True
        payload["q2_independent_holdout_executed"] = True
        payload["q3_evidence_eligible"] = True
        payload["status"] = "qualified_core_method_evidence"

    mutate_json(release / "resolved_pilot_design.json", edit)


def mutate_completion_binding(release: Path) -> None:
    def edit(payload: dict[str, Any]) -> None:
        artifacts = first_dict(payload, ("artifacts", "artifact_hashes", "hash_bindings"))
        target = next(value for value in artifacts.values() if isinstance(value, dict))
        set_first_scalar(target, ("sha256", "hash"), "4" * 64)

    mutate_json(release / "completion.json", edit)


def mutate_completion_status(release: Path) -> None:
    mutate_json(
        release / "completion.json",
        lambda payload: payload.update(
            {
                "status": "complete_empirical_method_qualified",
                "laboratory_execution_authorized": True,
            }
        ),
    )


def mutate_extra_file(release: Path) -> None:
    (release / "unmanifested_real_payload.json").write_text(
        '{"real_measurement": 1.0}\n', encoding="utf-8"
    )


def mutate_hardlink_alias(release: Path) -> None:
    source = release / "resolved_pilot_design.json"
    alias = release / "hardlink_alias_to_resolved_design.json"
    os.link(source, alias)


def mutation_map() -> dict[str, Callable[[Path], None]]:
    return {
        "source_lineage_hash_mutation": mutate_lineage_source_hash,
        "stage33e_interface_hash_mutation": mutate_stage33e_interface_hash,
        "stage33e_interface_path_redirect": mutate_stage33e_interface_path,
        "stage33e_parent_state_advance": mutate_stage33e_parent_state,
        "stage33e_slot_autoaccepted": mutate_stage33e_slot_autoaccept,
        "pilot_state_advance": mutate_pilot_state_advance,
        "skipped_state_transition": mutate_skipped_transition,
        "execution_or_claim_authority_enabled": mutate_authority_enabled,
        "real_identifier_inserted": mutate_real_identifier,
        "real_key_or_secret_inserted": mutate_real_key,
        "real_observation_row_inserted": mutate_real_observation_row,
        "deviation_or_postoutcome_revision_inserted": mutate_deviation_row,
        "invented_method_specific_threshold": mutate_invented_threshold,
        "inherited_numeric_gate_changed": mutate_inherited_gate,
        "monotonicity_made_acceptance_gate": mutate_monotonicity,
        "missing_work_package": mutate_missing_work_package,
        "duplicate_work_package": mutate_duplicate_work_package,
        "q1_development_observations_reused_in_q2": mutate_q1_reused_in_q2,
        "confirmatory_material_or_batch_reuse": mutate_confirmatory_material_allowed,
        "stage33do_test_asset_reuse": mutate_test_asset_reuse,
        "evidence_product_autoaccepted": mutate_evidence_autoaccept,
        "pilot_gate_autoaccepted": mutate_gate_autoaccept,
        "readiness_decision_promoted": mutate_readiness_promoted,
        "extra_unmanifested_artifact": mutate_extra_file,
        "link_or_hardlink_alias": mutate_hardlink_alias,
        "completion_artifact_hash_mismatch": mutate_completion_binding,
        "completion_status_or_authority_mismatch": mutate_completion_status,
        "output_overwrite": lambda release: None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    release = args.release.resolve()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"E33F_OVERWRITE_REFUSED: output exists: {output}")
    if not release.is_dir():
        raise RuntimeError(f"E33F_RELEASE_MISSING: {release}")
    output.parent.mkdir(parents=True, exist_ok=True)

    auditor = import_auditor()
    release_before = tree_hashes(release)
    positive_audit = audit_payload(auditor, release)
    if not bool(positive_audit.get("passed", positive_audit.get("pass", False))):
        raise RuntimeError("E33F_POSITIVE_AUDIT_FAILED")

    temp_root = Path(
        tempfile.mkdtemp(prefix=".stage33f_verify.", dir=str(output.parent))
    )
    results: dict[str, Any] = {}
    try:
        for challenge, mutate in mutation_map().items():
            challenge_release = temp_root / challenge / "release"
            challenge_release.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(release, challenge_release)

            # The immutable completion stores absolute paths to the canonical
            # release.  Rebind the isolated copy before every challenge so a
            # rejection cannot be attributed merely to stale copied paths.
            rebind_completion_to_copy(challenge_release)

            if challenge == "output_overwrite":
                occupied = temp_root / challenge / "occupied_audit_output"
                occupied.mkdir(parents=True)
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(AUDITOR_PATH),
                        "--release",
                        str(release),
                        "--output",
                        str(occupied),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                rejected = proc.returncode != 0 and "E33F_OVERWRITE_REFUSED" in proc.stderr
                error = proc.stderr[-1500:]
            else:
                mutate(challenge_release)
                if challenge not in {
                    "completion_artifact_hash_mismatch",
                    "completion_status_or_authority_mismatch",
                    "extra_unmanifested_artifact",
                    "link_or_hardlink_alias",
                }:
                    # Refresh the copied completion after semantic mutations.
                    # The auditor must now reject the altered meaning itself,
                    # rather than only detecting a stale artifact hash.
                    rebind_completion_to_copy(challenge_release)
                try:
                    audit_payload(auditor, challenge_release)
                except Exception as exc:
                    rejected = True
                    error = f"{type(exc).__name__}: {exc}"
                else:
                    rejected = False
                    error = "hostile mutation unexpectedly accepted"

            results[challenge] = {
                "expected_rejection": True,
                "rejected": rejected,
                "passed": rejected,
                "error_tail": error[-1500:],
            }

        release_after = tree_hashes(release)
        if release_before != release_after:
            raise RuntimeError(
                "E33F_INPUT_MUTATION: original release changed during verification"
            )
        failed = [name for name, result in results.items() if not result["passed"]]
        if failed:
            raise RuntimeError(
                "E33F_HOSTILE_VERIFICATION_FAILED: " + ", ".join(failed)
            )

        check_n = positive_audit.get(
            "check_n", positive_audit.get("passed_check_n", len(positive_audit.get("checks", [])))
        )
        verification = {
            "schema": "pet.stage33f-core-method-qualification-pilot-synthetic-verification.v1",
            "stage": "Stage33F",
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
                "passed": True,
                "check_n": check_n,
                "status": positive_audit.get("status", "passed"),
            },
            "negative_challenge_n": len(results),
            "negative_challenges_passed_n": sum(
                bool(result["passed"]) for result in results.values()
            ),
            "negative_challenges": results,
            "input_mutation": False,
            "current_decision": "DESIGN_ONLY_Q0_NOT_POPULATED",
            "stage33e_state_unchanged": "S10_DESIGN_FROZEN_EMPIRICAL_EMPTY",
            "readiness": {
                "q0_requirements_frozen": False,
                "q1_development_pilot_complete": False,
                "q2_independent_qualification_frozen": False,
                "q3_core_method_evidence_eligible": False,
                "laboratory_execution_ready": False,
                "stage33e_core_preflight_ready": False,
            },
            "authority": {
                "laboratory_execution": False,
                "hydraulic_measurement": False,
                "empirical_analysis": False,
                "stage33e_transition": False,
                "physical_validation_claim": False,
                "degradation_claim": False,
                "numerical_execution": False,
            },
            "source_bindings": {
                "release_completion_sha256": sha256(release / "completion.json"),
                "auditor_sha256": sha256(AUDITOR_PATH),
                "verifier_sha256": sha256(Path(__file__).resolve()),
            },
            "conclusion": (
                "The independent auditor accepted the exact empirical-empty Stage33F "
                "design and rejected every hostile synthetic mutation. This qualifies "
                "only the design/audit controls, not a laboratory method."
            ),
            "stop_boundary": positive_audit.get(
                "stop_boundary",
                "stop before real inventory, identities, data, keys, laboratory work, "
                "DEM/LBM, empirical analysis or physical/degradation/coupling claims",
            ),
        }

        output_temp = temp_root / "verification_output"
        output_temp.mkdir()
        write_json(output_temp / "verification.json", verification)
        completion = {
            "schema": "pet.stage33f-core-method-qualification-pilot-synthetic-verification-completion.v1",
            "stage": "Stage33F",
            "created_utc": now_utc(),
            "status": "complete",
            "passed": True,
            "verification_path": str(output / "verification.json"),
            "verification_sha256": sha256(output_temp / "verification.json"),
            "negative_challenge_n": len(results),
            "all_negative_challenges_rejected": True,
            "input_mutation": False,
            "all_authority_closed": True,
            "no_empirical_data": True,
            "no_laboratory_execution": True,
            "no_numerical_execution": True,
        }
        write_json(output_temp / "completion.json", completion)
        os.replace(output_temp, output)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    print(
        json.dumps(
            {
                "passed": True,
                "output": str(output),
                "negative_challenge_n": len(results),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL-CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
