from __future__ import annotations

import hashlib
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
CONTRACT = ROOT / "stage36_staging" / "STAGE36AE_PERIODIC_DRAG_COMPARATOR_CONTRACT.md"
PARENT = ROOT / "stage36_evaluations" / "stage36ad_periodic_drag_design_20260909" / "design_01" / "design.json"
OUT = ROOT / "stage36_evaluations" / "stage36ae_periodic_drag_comparator_20260909" / "qualification_01"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mobility(lam: float, c1: float) -> float:
    return 1.0 - c1 * lam + 4.19 * lam**3 - 27.4 * lam**6


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"fail closed: immutable output already exists: {OUT}")
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    if parent["flow_executed"] or parent["force_tolerance_frozen"]:
        raise SystemExit("fail closed: unexpected parent state")

    lam = 0.125
    phi = 4.0 * math.pi * lam**3 / 3.0
    m_printed = mobility(lam, 2.837)
    m_precise_c1 = mobility(lam, 2.837297)
    drag_printed = 1.0 / m_printed
    drag_precise_c1 = 1.0 / m_precise_c1
    rounding_delta = abs(drag_precise_c1 / drag_printed - 1.0)
    comparator_allowance = 0.01
    numerical_allowance = 0.02
    acceptance = comparator_allowance + numerical_allowance

    checks = {
        "parent_is_analytical_and_unrun": parent["status"] == "analytical_design_passed_flow_not_run",
        "mobility_positive": m_printed > 0.0,
        "rounding_delta_within_reference_allowance": rounding_delta <= comparator_allowance,
        "acceptance_frozen_before_flow": not parent["flow_executed"],
        "confirmation_grids_frozen": [x["N"] for x in parent["candidate_grids"] if x["force_conclusion_candidate"]] == [48, 64],
    }
    passed = all(checks.values())
    record = {
        "stage": "Stage36AE",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "comparator_qualified_force_gate_frozen_flow_not_run" if passed else "failed_closed",
        "correction_to_parent": "Stage36AD lambda^7 transcription is superseded by the primary-source lambda^6 term",
        "lambda": lam,
        "solid_volume_fraction": phi,
        "primary_relation": "M=1-2.837*lambda+4.19*lambda^3-27.4*lambda^6 (Ladd 1994 Eq. 3.5)",
        "mobility_ratio_printed_coefficients": m_printed,
        "drag_ratio_printed_coefficients": drag_printed,
        "mobility_ratio_precise_leading_constant": m_precise_c1,
        "drag_ratio_precise_leading_constant": drag_precise_c1,
        "coefficient_rounding_relative_drag_difference": rounding_delta,
        "comparator_relative_allowance": comparator_allowance,
        "numerical_relative_allowance": numerical_allowance,
        "force_relative_acceptance": acceptance,
        "resolution_shift_acceptance": 0.02,
        "confirmation_grids": [48, 64],
        "flow_executed": False,
        "checks": checks,
        "passed": passed,
        "sources": [
            {"citation": "Hasimoto (1959), JFM 5, 317-328", "doi": "10.1017/S0022112059000222"},
            {"citation": "Sangani and Acrivos (1982), IJMF 8, 343-360", "doi": "10.1016/0301-9322(82)90047-7"},
            {"citation": "Ladd (1994), JFM 271, 311-339, Eq. 3.5", "doi": "10.1017/S0022112094001771"},
        ],
        "input_hashes": {"contract": sha256(CONTRACT), "stage36ad_parent": sha256(PARENT)},
        "python": platform.python_version(),
        "next_action": "implement and statically verify the benchmark runner; do not execute flow until that implementation audit passes",
    }
    OUT.mkdir(parents=True)
    (OUT / "qualification.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    results = f"""# Stage36AE comparator qualification\n\n- Status: `{record['status']}`\n- `lambda`: {lam}\n- solid volume fraction: {phi:.12f}\n- primary Eq. (3.5) mobility: {m_printed:.12f}\n- primary Eq. (3.5) drag ratio: {drag_printed:.12f}\n- precise-leading-constant drag ratio: {drag_precise_c1:.12f}\n- rounding sensitivity: {100*rounding_delta:.6f}%\n- frozen comparator allowance: 1.0%\n- frozen numerical allowance: 2.0%\n- frozen total force gate: 3.0%\n- frozen N48-to-N64 shift gate: 2.0%\n- flow executed: no\n\nStage36AD's `lambda^7` transcription is superseded by the primary-source `lambda^6` relation. No numerical result was available when these gates were frozen.\n"""
    (OUT / "RESULTS.md").write_text(results, encoding="utf-8")
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
