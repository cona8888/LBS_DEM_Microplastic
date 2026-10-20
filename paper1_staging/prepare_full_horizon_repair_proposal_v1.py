"""Create-only research decision/provisional budget; no numerical capability."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "paper1_designs/full_horizon_repair_20261018"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pin(path):
    return dict(path=str(Path(path).resolve()), sha256=sha(path))


def verify(mapping):
    for path, expected in mapping.items():
        assert sha(path) == expected, path


def commit(path, payload):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    assert not (DESIGN / "proposal_01.json").exists()
    contract_path = DESIGN / "integration_contract_01.json"
    budget_path = DESIGN / "budget_assessment_01.json"
    review_path = DESIGN / "policy_review_01.json"
    evidence_path = ROOT / "paper1_evaluations/full_horizon_repair_20261018/evidence_01/results.json"
    exit_path = ROOT / "paper1_evaluations/full_horizon_repair_20261018/execution_01/receipt_01/results.json"
    comparison_path = ROOT / "paper1_runs/full_horizon_timecap_20261016/comparison_fine/results.json"
    kernel = ROOT / "paper1_staging/full_state_stepdoubling_v1.py"
    checks = ROOT / "paper1_staging/check_full_state_stepdoubling_v1.py"
    contract, budget, evidence, closure = map(read, [contract_path, budget_path, evidence_path, exit_path])
    review, comparison = map(read, [review_path, comparison_path])
    verify(contract["source_files"])
    verify(contract["evidence_files"])
    verify({v["path"]: v["sha256"] for v in budget["baseline"]["evidence"].values()})
    verify(closure["artifacts"])
    assert closure["material_result_sha256"] == sha(evidence_path)
    assert closure["administrative_execution_closed"] and closure["all_exact_owned_analysis_identities_retired"]
    assert not contract["readiness"] and not budget["dispatch_authorized"]
    assert comparison["original_gate_values"] == contract["unchanged_original_accuracy_gates"]
    assert comparison["original_gate_values"] == budget["full_horizon_follow_on"]["exact_gates"]
    assert evidence["new_transport_steps"] == evidence["new_integration_calls"] == evidence["new_native_solver_calls"] == 0
    assert evidence["passed"] and comparison["passed"] is False
    assert review["passed"] and review["numerical_launch_ready"] is False
    verify(review["source_files"])
    tree = ast.parse(kernel.read_text(encoding="utf-8"))
    imports = [n.module for n in tree.body if isinstance(n, ast.ImportFrom)]
    imports += [name.name for n in tree.body if isinstance(n, ast.Import) for name in n.names]
    assert set(imports) <= {"dataclasses", "hashlib", "json", "math"}
    test_count = sum(isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
                     for n in ast.walk(ast.parse(checks.read_text(encoding="utf-8"))))
    assert test_count == 17
    controls = dict(schema="paper1.inactive-stepdoubling.pure-controls.v1", passed=True,
        observed_by="/root", qualified_python="C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe",
        arguments=["-B", str(checks)], blas_openmp_threads=1,
        direct_tool_chunk="53df8c", actual_observed_tool_exit_code=0, control_count=17,
        source_files={str(kernel): sha(kernel), str(checks): sha(checks)},
        kernel_direct_imports=sorted(imports),
        limitations=["Synthetic algebra and adversarial state-machine controls only.",
            "Controller cursor/ledger JSON roundtrips are not native FULL restart qualification.",
            "No external mechanical witness is authenticated by a supplied Boolean or digest alone.",
            "No model/native/transport import, run, force solve or execution authority."],
        fixed_preseal_findings=["Zero-row negative audits now retain a terminal failure.",
            "Only literal Boolean audit results can resolve a reservation.",
            "Known excess work is charged in full as negative work, never capped to its smaller reservation.",
            "Restored progress requires exact integer counters, partitions and record identities."],
        new_transport_steps=0, new_native_solver_calls=0, new_integration_calls=0,
        numerical_launch_ready=False, utc=datetime.now(timezone.utc).isoformat())
    commit(DESIGN / "pure_controls_01.json", controls)
    projection = evidence["kinematic_projection"]
    final_state = next(v for v in evidence["state_difference_table"]
                       if v["time_s"] == evidence["precontact_stop_s"])
    screen = budget["screen"]
    proposal = dict(schema="paper1.full-horizon-repair.research-decision-and-provisional-budget.v1",
        status="ENGINEERING_PREPARATION_ONLY_NOT_EXECUTABLE",
        current_request="Resolve the full-horizon accuracy bottleneck and propose the minimum qualification budget while keeping physics and accuracy gates unchanged.",
        result="Bottleneck further localized; one inactive repair candidate prepared. Neither a full-horizon repair nor a sufficient minimum full-qualification budget is established.",
        authorization_created=False, numerical_launch_ready=False, numerical_approval_requested_now=False,
        new_transport_steps=0, new_native_solver_calls=0, new_integration_calls=0,
        changed_frozen_sources=[], budgets_changed=False, heartbeat_status="PAUSED",
        paper1_qualified_cases=1, paper1_target_cases=12,
        evidence={"saved_precontact_analysis": pin(evidence_path), "saved_analysis_closed_execution": pin(exit_path),
                  "original_full_failure": pin(comparison_path), "integration_contract": pin(contract_path),
                  "budget_assessment": pin(budget_path), "independent_policy_review": pin(review_path),
                  "pure_controls": pin(DESIGN / "pure_controls_01.json")},
        source_files={str(kernel): sha(kernel), str(checks): sha(checks), str(Path(__file__).resolve()): sha(__file__)},
        scientific_diagnosis=dict(
            precontact_stop_s=evidence["precontact_stop_s"],
            precontact_position_difference_m=final_state["position_difference_norm_m"],
            precontact_director_difference=final_state["director_vector_difference_norm"],
            precontact_q_difference_over_U=final_state["q_difference_norm_over_U"],
            signed_velocity_integral_reproduces_position_drift_residual_m=evidence["position_integral_identity_residual_m"],
            later_frame_linearized_loading_lag_s=projection["estimated_lag_s"],
            observed_archived_loading_separation_s=projection["archived_separation_s"],
            observed_common_FULL_reset_loading_separation_s=projection["common_FULL_reset_separation_s"],
            interpretation="Coupled trajectory drift is already present before first loading. Its later-frame linearized geometric projection is close to the observed loading-time separation. This prioritizes trajectory-error control rather than solver-route replacement or chatter suppression.",
            limitations=[projection["limitation"],
                "Small common-state interval errors do not qualify the independently evolved full prefix.",
                "No sole cause, implementation defect, globally correct reference or convergence order established.",
                "No new force residual or complete raw/history replay was performed by this saved-NPY extraction."]),
        selected_repair=dict(
            candidate="FULL-state step-doubling guard around literal original BE/right-rule substeps",
            sequence=["Fork the identical FULL state/history for coarse h and two consecutive half intervals.",
                "Apply original force/contact/geometry/pose laws and original independent mechanical audits to every evaluated substep.",
                "Compare literal common-endpoint x,p,q using prospectively frozen supplementary defect tolerances; no extrapolation or time/sign alignment.",
                "Commit only the literal two-half FULL checkpoint/raw/history chain after its additional guard passes.",
                "Retain and charge every coarse shadow, rejected, partial and unknown trial before any successor.",
                "Bound halvings and stop at a failed minimum; never force acceptance or retry a physical/evidence failure."],
            current_code_capability="Pure decision, finite retry, controller-cursor and all-work accounting kernel only. No integration adapter, authority or launcher.",
            tolerances_frozen=False,
            original_physical_and_full_path_gate_changes=[],
            numerical_policy_auditor_requirement="Frozen audit_onset_timecap_v1.py pins exact selector-dt equality and the one-cap AST. Additional half-step caps require a separately bound compositional numerical-policy audit: re-evaluate each half-state's original base/selector cap, prove only further tightening, and bind the new AST honestly. The frozen onset-auditor function is not claimed to accept this candidate unchanged.",
            unready_items=["Compiled-loop adapter and complete all-trial raw/audit association.",
                "Original cap evaluation at every half state and terminal/export handling.",
                "Compositional numerical-policy audit and literal FULL checkpoint/history plus controller/ledger atomic commit.",
                "Native exact initial, within-pair, first-active and window-handoff restart qualification.",
                "Analytical/limiting-case controls, frozen tolerances and measured cost/storage readiness."]),
        minimum_budget=dict(
            engineering_resource_increase_needed_now=0,
            full_horizon_minimum="UNDETERMINED: no honest sufficient amount until the candidate is implemented and measured.",
            old_single_fine_production_steps=1506345, old_single_fine_production_calls=313,
            remaining_shared_steps=967902, remaining_shared_calls=213,
            old_single_fine_shortfall_steps_before_diagnostics=538443,
            old_single_fine_shortfall_calls_before_diagnostics=100,
            conditional_test_only=dict(
                status="PROVISIONAL_HARD_STOP_NOT_READY_FOR_APPROVAL_OR_DISPATCH",
                fresh_start_s=0., stop_s=.255, nominal_factors=[.125,.0625],
                maximum_hours=12, maximum_all_trial_steps=2250000,
                maximum_integration_calls=550, classification="All discarded diagnostic work; zero core admission credit.",
                maximum_new_retained_bytes=2*1024**3,
                why="Fresh t=0 exposure covers startup, first loading and the beginning of the archived persistent-error region. Another later common-state reset would not test inherited prefix drift.",
                caveat="This is an explicit bounded falsifier and cost measurement, not the minimum sufficient screen or full-path qualification. Even this limit may stop before both prefixes finish.",
                cap_amendments_if_later_approved=screen["required_exact_prospective_cap_amendments"]),
            full_qualification_after_test="Freeze a measured envelope for THREE fresh t=0 paths over 0.01PV/0.9364396280429768s. Run original complete fine-pair gate before the coarse confirmation; both original pair gates and full evidence/exit closure are required. No local prefix credit, old failed reference promotion or automatic fourth level.",
            remaining_ten_core_cases="Require an updated accepted-cost forecast and original bounded admission after this fibre is qualified; this assessment grants no successor work.",
            no_automatic_cap_clock_or_hpc_increase=True),
        original_full_path_gates=comparison["original_gate_values"],
        original_unchanged_resource_rules=dict(workers=1, threads=1, logical_cpu=14,
            native_seconds_per_record=45, maximum_unverified_records=1,
            maximum_total_retained_bytes=20*1024**3, minimum_free_bytes=20*1024**3),
        methodology_sources=[dict(title="GNU GSL implicit Euler step doubling", url="https://www.gnu.org/software/gsl/doc/html/ode-initval.html",
                scope="Supports the general full-versus-two-half stencil, not accuracy/cost of this nonsmooth DEM case."),
            dict(title="SUNDIALS CVODE tolerance advice", url="https://sundials.readthedocs.io/en/v7.2.0/cvode/Usage/",
                scope="Local tolerances are problem dependent; global behavior must be checked by refinement experiments. CVODE is not installed or proposed as this contact solver.")],
        utc=datetime.now(timezone.utc).isoformat())
    commit(DESIGN / "proposal_01.json", proposal)
    print(json.dumps(dict(proposal_sha256=sha(DESIGN / "proposal_01.json"),
                          controls_sha256=sha(DESIGN / "pure_controls_01.json"),
                          numerical_launch_ready=False, new_transport_steps=0)))


if __name__ == "__main__":
    main()
