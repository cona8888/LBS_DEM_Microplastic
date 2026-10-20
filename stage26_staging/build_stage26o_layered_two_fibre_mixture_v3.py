"""Freeze namespace-only correction as Stage26o layered Design 03."""
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
    prior_config = ROOT / "stage26_designs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_layered_design_02" / "mixture_config.json"
    failure_path = ROOT / "stage26_evaluations" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_layered_integration_failure_02" / "failure.json"
    runner = ROOT / "stage26_staging" / "run_stage26o_layered_two_fibre_mixture_v3.py"
    adapter = ROOT / "stage26_staging" / "run_stage26o_layered_two_fibre_mixture_v2.py"
    output = ROOT / "stage26_designs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_layered_design_03"
    if output.exists():
        raise RuntimeError("immutable layered Design 03 exists")
    failure = load(failure_path)
    if not failure.get("passed") or not failure["authority"].get("namespace_integration_correction_authorized"):
        raise RuntimeError("integration failure does not authorize namespace correction")
    config = load(prior_config)
    config["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    config["integration_correction"] = {"physics_changed": False, "acceptance_gates_changed": False, "initial_geometry_changed": False, "correction": "propagate live YADE namespace through immediate mixture, nested v9, and nested core modules"}
    config["sources"]["runner"] = win(runner)
    config["sources"]["runner_sha256"] = sha256(runner)
    config["sources"]["layered_adapter_v2"] = win(adapter)
    config["sources"]["layered_adapter_v2_sha256"] = sha256(adapter)
    config["sources"]["integration_failure"] = win(failure_path)
    config["sources"]["integration_failure_sha256"] = sha256(failure_path)
    output.mkdir(parents=True)
    path = output / "mixture_config.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(config, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(path), "sha256": sha256(path), "runner_sha256": sha256(runner)}, sort_keys=True))


if __name__ == "__main__":
    main()
