#!/usr/bin/env python3
"""Fail-closed preflight audit for the Stage28a two-fibre design."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "stage28_staging/stage28a_two_fibre_design_v1.json"
CONTRACT = ROOT / "stage28_staging/STAGE28A_TWO_FIBRE_MECHANICS_HYDRAULIC_CONTRACT.md"
OUTPUT = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/design_audit_01"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    config = load(CONFIG)
    cases = {case["case_id"]: case for case in config["cases"]}
    lineage_checks = {
        key: Path(binding["path"]).is_file()
        and digest(Path(binding["path"])) == binding["sha256"]
        for key, binding in config["lineage"].items()
    }
    checks = {
        "contract_present": CONTRACT.is_file(),
        "lineage_hashes": all(lineage_checks.values()),
        "exact_case_matrix": set(cases)
        == {
            "separated_open_open",
            "separated_open_constricted",
            "crossing_interaction",
        },
        "all_cases_two_fibres": all(case["fibre_count"] == 2 for case in cases.values()),
        "separated_controls_no_contact": all(
            cases[name]["required_terminal_fibre_fibre_contacts"] == 0
            for name in ("separated_open_open", "separated_open_constricted")
        ),
        "crossing_contact_required": cases["crossing_interaction"][
            "required_terminal_fibre_fibre_contacts_minimum"
        ]
        >= 1,
        "frozen_216_sand": config["acceptance"]["required_sand_particles"] == 216,
        "frozen_fibre_discretization": config["acceptance"]["required_nodes_per_fibre"]
        == 37
        and config["acceptance"]["required_internal_bonds_per_fibre"] == 36,
        "strict_penetration_guard": config["acceptance"][
            "maximum_penetration_over_fibre_radius"
        ]
        <= 0.01,
        "stage24_two_fibre_concentration_bound": abs(
            config["concentration"]["achieved_dry_mass_percent_reference"]
            - 0.009381481678218612
        )
        < 1e-15,
        "execution_fail_closed": bool(config["authority"]["design_audit"])
        and not any(
            config["authority"][key]
            for key in (
                "mechanics_execution",
                "gpu_execution",
                "production_concentration_campaign",
                "mobile_sand",
                "two_way_coupling",
            )
        ),
        "additivity_observable_present": "nonadditive_interaction_contrast"
        in config["hydraulic_observables"],
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage28a-two-fibre-mechanics-hydraulics-design-audit.v1",
        "status": "passed_implementation_design_authorized" if passed else "design_audit_failed",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "lineage_checks": lineage_checks,
        "source_bindings": {
            "config": {"path": str(CONFIG), "sha256": digest(CONFIG)},
            "contract": {"path": str(CONTRACT), "sha256": digest(CONTRACT)},
            "auditor": {
                "path": str(Path(__file__).resolve()),
                "sha256": digest(Path(__file__).resolve()),
            },
        },
        "authority": {
            "implementation_design": passed,
            "mechanics_execution": False,
            "gpu_execution": False,
            "production_concentration_campaign": False,
            "mobile_sand": False,
            "two_way_coupling": False,
        },
        "next_handoff": {
            "authorized": "implement and unit-test the two-fibre contact extension and build candidate geometries"
            if passed
            else "none",
            "not_authorized": "YADE mechanics execution, GPU-LBM execution, production concentration campaign, mobile sand or two-way coupling",
        },
    }
    audit_path = OUTPUT / "design_audit.json"
    write(audit_path, audit)
    print(
        json.dumps(
            {
                "passed": passed,
                "audit": str(audit_path),
                "audit_sha256": digest(audit_path),
                "failed_checks": [key for key, value in checks.items() if not value],
            },
            indent=2,
        )
    )
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
