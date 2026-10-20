"""Freeze the Stage26o layered-pluviation Design 02."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def win(path):
    return str(Path(path).resolve()).replace("\\", "/")


def main():
    base_path = ROOT / "stage26_designs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_mixture_design_01" / "mixture_config.json"
    evaluation_path = ROOT / "stage26_evaluations" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_mixture_evaluation_01" / "evaluation.json"
    prior_result = ROOT / "stage26_runs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_mixture_01" / "result.json"
    prior_completion = prior_result.parent / "completion.json"
    runner = ROOT / "stage26_staging" / "run_stage26o_layered_two_fibre_mixture_v2.py"
    base_runner = ROOT / "stage26_staging" / "run_stage26o_two_fibre_mixture_v1.py"
    contract = ROOT / "stage26_staging" / "STAGE26O_LAYERED_RESEARCH_CONTRACT.md"
    output = ROOT / "stage26_designs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_layered_design_02"
    if output.exists():
        raise RuntimeError("immutable layered design exists")
    evaluation = load(evaluation_path)
    if not evaluation.get("passed") or not evaluation["authority"].get("layered_joint_deposition_redesign_authorized"):
        raise RuntimeError("attempt-01 evaluation does not authorize layered redesign")
    config = load(base_path)
    config["schema"] = "lbs.stage26o-layered-two-fibre-joint-deposition-config.v1"
    config["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    config["status"] = "authorized_stage26o_spent_development_two_fibre_mixture"
    config["research_role"] = "spent_development_layered_pluviation_small_assembly_benchmark_not_validation"
    config["physical_question"] = "Can lower-and-upper sand pluviation around two exact mobile F37 fibres form simultaneous persistent cages?"
    config["claim_boundary"] = "One wall-bounded 216-sand, two-F37 layered-pluviation development case only. No representative-volume, held-out, flow, permeability, deformation, migration, polymer-calibration, or production-parametric claim."
    config["initialization"]["mode"] = "deterministic_lower_upper_sand_bands_with_fibres_in_intervening_fall_zone"
    config["initialization"]["sand_initial_z_bands_fraction"] = [[0.0, 0.45], [0.57, 1.0]]
    config["initialization"]["fibre_pivot_fractions"] = [[0.38, 0.42, 0.50], [0.62, 0.58, 0.53]]
    config["initialization"]["deterministic_rsa_seed"] = 2026081802
    config["verification_additions"] = {"explicit_fibre_member_leakage_guard": True, "fibre_parent_position_history": True, "fibre_member_bounds_history": True, "all_physics_and_acceptance_gates_unchanged_from_attempt_01": True}
    config["sources"]["runner"] = win(runner)
    config["sources"]["runner_sha256"] = sha256(runner)
    config["sources"]["base_mixture_runner"] = win(base_runner)
    config["sources"]["base_mixture_runner_sha256"] = sha256(base_runner)
    config["sources"]["research_contract"] = win(contract)
    config["sources"]["research_contract_sha256"] = sha256(contract)
    config["sources"]["prior_mixture_evaluation"] = win(evaluation_path)
    config["sources"]["prior_mixture_evaluation_sha256"] = sha256(evaluation_path)
    config["sources"]["prior_mixture_result"] = win(prior_result)
    config["sources"]["prior_mixture_result_sha256"] = sha256(prior_result)
    config["sources"]["prior_mixture_completion"] = win(prior_completion)
    config["sources"]["prior_mixture_completion_sha256"] = sha256(prior_completion)
    output.mkdir(parents=True)
    path = output / "mixture_config.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(config, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(path), "sha256": sha256(path), "runner_sha256": sha256(runner)}, sort_keys=True))


if __name__ == "__main__":
    main()
