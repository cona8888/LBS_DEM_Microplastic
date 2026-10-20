from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("immutable evaluation output exists")

    config = load(args.config)
    result_path = args.run / "result.json"
    completion_path = args.run / "completion.json"
    history_path = args.run / "history.csv"
    result = load(result_path)
    completion = load(completion_path)
    history_rows = list(csv.DictReader(history_path.open("r", encoding="utf-8")))
    if not history_rows:
        raise RuntimeError("empty history")

    state_binding = result.get("artifacts", {}).get("state")
    state_path = Path(state_binding["path"]) if state_binding else None
    terminal = result.get("terminal") or {}
    checks = result.get("checks") or {}
    limits = config["acceptance"]
    target_e = float(config["density_ramp"]["reference_void_ratio"])

    independent = {
        "config_hash_matches_result": result.get("source_hashes", {}).get("config") == sha256(args.config),
        "completion_binds_result": completion.get("result", {}).get("sha256") == sha256(result_path),
        "result_binds_history": result.get("artifacts", {}).get("history", {}).get("sha256") == sha256(history_path),
        "state_exists": state_path is not None and state_path.is_file(),
        "result_binds_state": state_path is not None and state_path.is_file() and state_binding.get("sha256") == sha256(state_path),
        "result_passed": result.get("passed") is True,
        "completion_passed": completion.get("passed") is True,
        "qualified_status": result.get("status") == "qualified_clean_density_controller",
        "all_runner_checks_pass": bool(checks) and all(checks.values()),
        "terminal_void_ratio": abs(float(terminal.get("container_void_ratio", math.inf)) - target_e) <= float(limits["maximum_terminal_void_ratio_error"]),
        "terminal_mean_stress": float(terminal.get("relative_mean_wall_stress_error", math.inf)) <= float(limits["maximum_relative_mean_wall_stress_error"]),
        "terminal_principal_stress": float(terminal.get("maximum_principal_wall_stress_error", math.inf)) <= float(limits["maximum_principal_wall_stress_error"]),
        "terminal_unbalanced_force": float(terminal.get("unbalanced_force", math.inf)) <= float(limits["maximum_unbalanced_force"]),
        "terminal_kinetic_energy": float(terminal.get("normalized_kinetic_energy_pV", math.inf)) <= float(limits["maximum_normalized_kinetic_energy_pV"]),
        "terminal_overlap": float(terminal.get("maximum_interobject_penetration_over_smaller_radius", math.inf)) <= float(limits["maximum_penetration_over_smaller_radius"]),
        "terminal_coordination": float(terminal.get("sand_coordination_excluding_degree_lt2_rattlers", -math.inf)) >= float(limits["minimum_sand_coordination_excluding_rattlers"]),
        "terminal_rattlers": float(terminal.get("sand_rattler_fraction_degree_lt2_iterative", math.inf)) <= float(limits["maximum_sand_rattler_fraction"]),
        "particle_count": int(terminal.get("particle_count", -1)) == int(limits["required_particle_count"]),
        "no_leakage": int(terminal.get("leaked_particle_count", -1)) == 0,
        "history_terminal_matches_result": (
            int(float(history_rows[-1]["record"])) == int(terminal.get("record", -1))
            and abs(float(history_rows[-1]["container_void_ratio"]) - float(terminal.get("container_void_ratio", math.inf))) <= 1.0e-12
        ),
        "authority_remains_bounded": not any(
            config["authority"].get(key, False)
            for key in (
                "single_fibre_execution_authorized",
                "full_mixture_execution_authorized",
                "flexible_fibre_execution_authorized",
                "flow_execution_authorized",
                "permeability_claim_authorized",
                "production_parametric_study_authorized",
            )
        ),
    }
    passed = all(independent.values())
    evaluation = {
        "schema": "lbs.stage26q-clean-density-controller-independent-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "clean_density_controller_independently_accepted" if passed else "clean_density_controller_not_accepted",
        "passed": passed,
        "claim_boundary": config["claim_boundary"],
        "checks": independent,
        "terminal": terminal,
        "sources": {
            "config": {"path": str(args.config.resolve()), "sha256": sha256(args.config)},
            "result": {"path": str(result_path.resolve()), "sha256": sha256(result_path)},
            "completion": {"path": str(completion_path.resolve()), "sha256": sha256(completion_path)},
            "history": {"path": str(history_path.resolve()), "sha256": sha256(history_path)},
            "state": {"path": str(state_path.resolve()), "sha256": sha256(state_path)} if state_path and state_path.is_file() else None,
            "evaluator": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        },
        "authority": {
            "pore_throat_extraction_authorized": passed,
            "single_fibre_execution_authorized": False,
            "full_mixture_execution_authorized": False,
            "flexible_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
            "permeability_claim_authorized": False,
            "production_parametric_study_authorized": False,
        },
    }
    args.output.mkdir(parents=True, exist_ok=False)
    output_path = args.output / "evaluation.json"
    output_path.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    print(sha256(output_path))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
