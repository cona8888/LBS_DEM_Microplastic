"""Argument/binding regression only: no LBM or particle integration."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import prepare_comparison_runner_v1 as runner

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stage110_evaluations/comparison_runner_regression_20260915"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def rejected(fn):
    try:
        fn()
    except (RuntimeError, ValueError):
        return True
    return False


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    protocol = json.loads(runner.PROTOCOL.read_text())
    cases = []
    for seed in (1, 2, 3):
        sample_id = protocol["population"]["stage_b_sentinel_ids"][str(seed)]
        for factor in (0.5, 1.0, 2.0):
            for shape in protocol["shapes"]:
                cases.append(runner.prepare(seed, sample_id, shape, factor, 0.01))
    reference = next(c for c in cases if c["packing_seed"] == 2
                     and c["flow_factor"] == 1.0 and c["shape"] == "rigid_prolate_ar4")
    high = next(c for c in cases if c["packing_seed"] == 2
                and c["flow_factor"] == 2.0 and c["shape"] == "rigid_prolate_ar4")
    with patch.object(runner.adapter, "run_local", return_value={"status": "mock_only"}) as dispatch:
        mock_result = runner.run_reference_diagnostic_segment(reference, 1.0)
        args = dispatch.call_args.args
        dispatch_checks = {
            "mock_dispatch_only": mock_result["status"] == "mock_only",
            "bound_runner_class": args[0] is runner.BoundRunner,
            "case_binding_attached": runner.BoundRunner.binding == reference["binding"],
            "checkpoint_starts_empty": runner.BoundRunner.checkpoint is None,
            "correct_config_and_state": args[1] == reference["config"] and args[2] == reference["initial_state"],
            "correct_seed_and_horizon": args[3] == 2 and args[4] == 0.01,
            "correct_budget": args[5] == 1.0,
        }
        calls_before = dispatch.call_count
        scaled_rejected = rejected(lambda: runner.run_reference_diagnostic_segment(high, 1.0))
        tampered = dict(reference)
        tampered["binding"] = "wrong"
        drift_rejected = rejected(lambda: runner.run_reference_diagnostic_segment(tampered, 1.0))
        checkpoint_rejected = rejected(lambda: runner.run_reference_diagnostic_segment(
            reference, 1.0, {"state": {"t": 1.0}, "state_sha256": "wrong"}))
        no_guarded_dispatch = dispatch.call_count == calls_before
    checks = {
        "all_18_sentinel_shape_flow_bindings_unique": len(cases) == 18 and len({c["binding"] for c in cases}) == 18,
        "case_source_and_input_hashes_bound": all(c["source_hashes"] and c["input_hashes"] for c in cases),
        "same_paired_initial_centre_at_all_flow_and_shape_levels": all(
            len({tuple(c["initial_state"]["position_m"]) for c in cases if c["packing_seed"] == seed}) == 1
            for seed in (1, 2, 3)),
        "scaled_flow_execution_guard": scaled_rejected,
        "tampered_spec_rejected": drift_rejected,
        "tampered_checkpoint_rejected": checkpoint_rejected,
        "guarded_cases_never_dispatched": no_guarded_dispatch,
        **dispatch_checks,
    }
    if not all(checks.values()):
        raise RuntimeError(f"runner regression failed: {checks}")
    result = {
        "status": "argument_and_binding_regression_passed_no_transport",
        "checks": checks,
        "case_bindings": [{"seed": c["packing_seed"], "sample_id": c["sample_id"],
                           "shape": c["shape"], "flow_factor": c["flow_factor"],
                           "binding": c["binding"]} for c in cases],
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                          str(Path(runner.__file__).resolve()): sha(runner.__file__),
                          str(Path(runner.adapter.__file__).resolve()): sha(runner.adapter.__file__)},
        "input_hashes": {str(p): sha(p) for p in (runner.PROTOCOL, runner.PROTOCOL.with_name("completion.json"),
                                                  runner.POP_RESULT, runner.STAGE108_MANIFEST)},
        "claim_boundary": "Pure preparation and mocked-dispatch verification. No LBM, DEM, transport, contact, restart integration, or physical flow-scaling result.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"status": result["status"],
                                    "results_sha256": sha(OUT / "results.json")})
    print(json.dumps({"status": result["status"], "checks": len(checks),
                      "cases": len(cases)}))


if __name__ == "__main__":
    main()
