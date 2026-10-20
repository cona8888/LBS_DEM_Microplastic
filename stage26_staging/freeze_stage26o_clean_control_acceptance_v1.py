"""Freeze the independently verified Stage26o clean-control handoff."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser()
    for name in ("config", "runner", "result", "completion", "history", "state", "evaluation", "probe", "probe_runner", "output"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable acceptance output already exists")

    config = load(args.config)
    result = load(args.result)
    completion = load(args.completion)
    evaluation = load(args.evaluation)
    probe = load(args.probe)
    checks = {
        "config_authorized_clean_control": config["authority"]["clean_sand_control_authorized"] is True,
        "result_passed": result.get("passed") is True and result.get("qualified") is True,
        "completion_passed": completion.get("passed") is True and completion.get("qualified") is True,
        "evaluation_passed": evaluation.get("passed") is True,
        "reaction_probe_passed": probe.get("passed") is True,
        "completion_binds_result": completion.get("result_sha256") == sha256(args.result),
        "completion_binds_state": completion.get("state_sha256") == sha256(args.state),
        "result_binds_history": result["artifacts"]["history_sha256"] == sha256(args.history),
        "result_binds_state": result["artifacts"]["state_sha256"] == sha256(args.state),
        "result_binds_config": result["source_hashes"]["config"] == sha256(args.config),
        "result_binds_runner": result["source_hashes"]["runner"] == sha256(args.runner),
        "probe_binds_result": probe.get("result_sha256") == sha256(args.result),
        "probe_binds_state": probe.get("state_sha256") == sha256(args.state),
        "probe_fixed_walls": probe["checks"]["fixed_walls"] is True,
        "probe_direct_stress": probe["checks"]["mean_stress"] is True and probe["checks"]["principal_stress"] is True,
        "probe_matches_terminal": probe["checks"]["terminal_reaction_match"] is True,
    }
    passed = all(checks.values())
    payload = {
        "schema": "lbs.stage26o-clean-control-accepted-handoff.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "clean_control_accepted_spent_development_mixture_authorized" if passed else "clean_control_handoff_rejected",
        "checks": checks,
        "claim_boundary": "Wall-bounded 216-sand preparation benchmark only; not representative-volume validation or permeability evidence.",
        "authority": {
            "spent_development_mixture_authorized": passed,
            "heldout_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "sources": {
            name: {"path": str(Path(getattr(args, name)).resolve()), "sha256": sha256(getattr(args, name))}
            for name in ("config", "runner", "result", "completion", "history", "state", "evaluation", "probe", "probe_runner")
        },
        "terminal": result["terminal"],
        "rebuilt_direct_reactions": {
            "principal_stress_pa": probe["direct_reaction_stresses_pa_compression_positive"],
            "mean_stress_pa": probe["direct_mean_stress_pa"],
            "maximum_terminal_match_error": probe["maximum_terminal_reaction_match_error"],
        },
        "next_action": "run_one_spent_development_two_f37_fibre_joint_deposition_case" if passed else "stop",
    }
    output.mkdir(parents=True)
    path = output / "checkpoint_manifest.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"passed": passed, "checkpoint": str(path), "sha256": sha256(path)}, sort_keys=True))
    if not passed:
        raise RuntimeError("clean-control handoff rejected")


if __name__ == "__main__":
    main()
