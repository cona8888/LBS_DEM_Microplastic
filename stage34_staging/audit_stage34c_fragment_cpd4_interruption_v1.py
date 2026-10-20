#!/usr/bin/env python3
"""Audit the interrupted Stage34C output without modifying it."""

from __future__ import annotations

import ctypes
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage34c_cpd4_first_fragmentation_geometry_20260902"
CONFIG = ROOT / "stage34_designs" / STUDY / "gpu_config_02/resolved_config.json"
HANDOFF = ROOT / "stage34_evaluations" / STUDY / "execution_release_03/handoff.json"
RUNNER = ROOT / "stage34_staging/run_stage34c_fragment_cpd4_gpu_v1.py"
SUPERVISOR = ROOT / "stage34_staging/supervise_stage34c_fragment_cpd4_gpu_v2.ps1"
RUN_OUTPUT = ROOT / "stage34_runs" / STUDY / "gpu_confirmation_01"
SUPERVISOR_OUTPUT = RUN_OUTPUT.parent / "gpu_confirmation_01_supervisor"
OUTPUT = ROOT / "stage34_evaluations" / STUDY / "interruption_audit_01"
COMPLETED = (
    "s34c_n216_s2_A_p4_frag2_cpd4",
    "s34c_n216_s1_A_p4_frag2_cpd4",
)
NEXT_CASE = "s34c_n216_s2_B_p4_frag2_cpd4"
ARTIFACT_NAMES = ("record.json", "audit.npz", "final_fields.npz", "final_shifted_state.npz", "final_flow.vtk")
EXPECTED = {
    "config": "33f110cb29b73389ce74f1464000d4e4b51e6b418024f6282a3554cffeb0004d",
    "handoff": "94e9e861b410a086d5a689bde04bfa347c313ab133b652166cfcbdbad5590744",
    "runner": "44c7d6fab8cef09ce0147746e30efa4a489177050733fde2cf2a06fa7b0ce274",
    "supervisor": "53c414c1ae1d704ae82533f46431baac2faa873b1264de01ceabf6dcdefce4a7",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def pid_is_active(pid: int) -> bool | None:
    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
    if not handle:
        error = ctypes.get_last_error()
        return False if error in (0, 87) else None
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return None
        return int(exit_code.value) == still_active
    finally:
        kernel32.CloseHandle(handle)


def all_checks_true(record: dict) -> bool:
    return bool(record.get("passed")) and bool(record.get("checks")) and all(
        value is True for value in record["checks"].values()
    )


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable interruption audit: {OUTPUT}")
    required = (CONFIG, HANDOFF, RUNNER, SUPERVISOR, RUN_OUTPUT, SUPERVISOR_OUTPUT)
    if not all(path.exists() for path in required):
        raise RuntimeError("required original Stage34C evidence is missing")

    manifest_path = SUPERVISOR_OUTPUT / "launch_manifest.json"
    stdout_path = SUPERVISOR_OUTPUT / "stdout.log"
    stderr_path = SUPERVISOR_OUTPUT / "stderr.log"
    manifest = load(manifest_path)
    handoff = load(HANDOFF)
    stdout_lines = stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    starts = [json.loads(line.split("=", 1)[1]) for line in stdout_lines if line.startswith("STAGE34C_START=")]
    case_lines = [json.loads(line.split("=", 1)[1]) for line in stdout_lines if line.startswith("STAGE34C_CASE=")]

    bundles: dict[str, dict] = {}
    record_checks: dict[str, bool] = {}
    for case_id in COMPLETED:
        case_dir = RUN_OUTPUT / case_id
        artifacts = {name: sha(case_dir / name) for name in ARTIFACT_NAMES}
        record = load(case_dir / "record.json")
        bundles[case_id] = {
            "path": str(case_dir),
            "artifact_sha256": artifacts,
            "record_summary": {
                "passed": bool(record.get("passed")),
                "steps_completed": int(record["steps_completed"]),
                "superficial_velocity_lu": float(record["final"]["superficial_velocity_lu"]),
                "acceleration_lu": float(record["acceleration_lu"]),
            },
        }
        record_checks[case_id] = all_checks_true(record)

    actual_dirs = tuple(path.name for path in RUN_OUTPUT.iterdir() if path.is_dir())
    observed_hashes = {
        "config": sha(CONFIG), "handoff": sha(HANDOFF), "runner": sha(RUNNER),
        "supervisor": sha(SUPERVISOR), "launch_manifest": sha(manifest_path),
        "stdout": sha(stdout_path), "stderr": sha(stderr_path),
    }
    pid_active = pid_is_active(int(manifest["pid"]))
    checks = {
        "original_lineage_hashes_exact": all(observed_hashes[key] == value for key, value in EXPECTED.items()),
        "original_release_passed": handoff.get("passed") is True
            and handoff.get("status") == "stage34c_fragment_cpd4_gpu_execution_authorized",
        "launch_manifest_bound": manifest.get("status") == "running"
            and int(manifest["pid"]) == 11188
            and manifest.get("hashes", {}).get("config") == EXPECTED["config"]
            and manifest.get("hashes", {}).get("handoff") == EXPECTED["handoff"]
            and manifest.get("hashes", {}).get("runner") == EXPECTED["runner"]
            and manifest.get("hashes", {}).get("supervisor") == EXPECTED["supervisor"],
        "bound_pid_absent": pid_active is False,
        "stderr_empty": stderr_text == "",
        "no_completion_marker": not (RUN_OUTPUT / "completion.json").exists(),
        "no_failure_marker": not (RUN_OUTPUT / "failure.json").exists(),
        "exact_two_case_directories": set(actual_dirs) == set(COMPLETED) and len(actual_dirs) == 2,
        "exact_two_completed_case_lines": tuple(row["case_id"] for row in case_lines) == COMPLETED,
        "third_case_started_without_bundle": tuple(row["case_id"] for row in starts) == COMPLETED + (NEXT_CASE,)
            and not (RUN_OUTPUT / NEXT_CASE).exists(),
        "both_completed_records_passed": len(record_checks) == 2 and all(record_checks.values()),
        "all_ten_completed_artifacts_hashed": len(bundles) == 2
            and all(len(item["artifact_sha256"]) == len(ARTIFACT_NAMES) for item in bundles.values()),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage34c-fragment-cpd4-interruption-audit.v1",
        "status": "passed_recoverable_external_interruption" if passed else "failed_closed",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "unknown_external_process_termination_not_a_physics_or_numerical_failure" if passed else "unresolved",
        "checks": checks,
        "pid_observation": {"bound_pid": int(manifest["pid"]), "active": pid_active},
        "observed_hashes": observed_hashes,
        "completed_case_bundles": bundles,
        "completed_order": list(COMPLETED),
        "next_unfinished_case": NEXT_CASE,
        "original_run_output": str(RUN_OUTPUT),
        "original_supervisor_output": str(SUPERVISOR_OUTPUT),
        "authority": {
            "recovery_release": passed,
            "edit_or_overwrite_original_output": False,
            "rerun_completed_cases": False,
            "additional_physics": False,
        },
    }
    audit_path = OUTPUT / "interruption_audit.json"
    write(audit_path, audit)
    completion = {
        "schema": audit["schema"] + ".completion",
        "status": audit["status"], "passed": passed,
        "interruption_audit_sha256": sha(audit_path),
        "auditor_sha256": sha(Path(__file__).resolve()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    write(OUTPUT / "completion.json", completion)
    print(json.dumps({"passed": passed, "checks": checks, "audit": str(audit_path),
                      "audit_sha256": sha(audit_path)}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
