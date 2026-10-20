"""Supplementary step-doubling evidence checks; no model import at import time.

The original physical/normal-gap/force/raw auditors remain mandatory. This
module reconstructs their original timestep upper bounds, then independently
checks controller composition. It does not infer a mechanical pass from a
producer Boolean. No function integrates, launches, warms or solves contacts.
"""
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRESERVED_AUDIT_V1_SHA256 = "8210d3469c9e5b13a3b382fbf4b3c4db47482d1e999250c5e608af72ba72cb76"
_ORIGINAL_STENCIL_ADAPTER_MARKER = object()
REQUIRED_STENCIL_SOURCES = {
    "stage180_staging/audit_optimized_record_v1.py": "84d45b4453f34a0c95e4bfa6b116b49c28751ae91c14712f5246f1e3371a3f51",
    "stage189_staging/audit_contact_trial_trace_v2.py": "8575647324f5e6d8b2fca5d9713ee05045f7c8a68c8056cd2ef87d9cd5db9377",
    "stage213_staging/audit_normal_gap_v1.py": "e6940d5b9c1db1fdc4b4cf03f44788e12e2f7a5946ad9e9aa92cccafbf71b371",
    "stage243_staging/per_pose_guard_v1.py": "8a083685b2f1f28ff37fa08f75919603c0d0c22d540d32d0196cc7d2af0d5d6f",
}


def require(value, message):
    if not value:
        raise ValueError("Step-doubling policy audit: " + message)


def digest(value):
    def no_nan(item):
        if isinstance(item, float):
            require(not math.isnan(item), "NaN is not an original infinity sentinel")
        elif isinstance(item, (list, tuple)):
            for child in item:
                no_nan(child)
        elif isinstance(item, dict):
            for child in item.values():
                no_nan(child)
    no_nan(value)
    # Original checkpoint minimum-gap/health sentinels may be infinite. Preserve
    # those literal JSON values; physical endpoints and policy scales are
    # separately required finite. This is not the original API digest format.
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True,
                                    separators=(",", ":")).encode()).hexdigest()


def is_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while data := stream.read(1024 * 1024):
            result.update(data)
    return result.hexdigest()


def verify_mapping(mapping):
    require(isinstance(mapping, dict) and mapping, "nonempty immutable evidence map")
    for path, expected in mapping.items():
        require(is_sha(expected) and file_sha(path) == expected, "immutable artifact: " + str(path))


def authenticate_receipt(result_path, expected_result_sha256, expected_completion_sha256,
                         *, document_reader=None):
    """Authenticate an existing receipt and all its declared files, no replay.

    A qualified original document reader must be supplied for a compressed
    document reference. Hash authentication is explicitly not mechanical replay.
    """
    path = Path(result_path)
    completion_path = path.with_name("completion.json")
    require(is_sha(expected_result_sha256) and is_sha(expected_completion_sha256), "caller-pinned receipt pair")
    require(file_sha(path) == expected_result_sha256
            and file_sha(completion_path) == expected_completion_sha256, "sealed receipt bytes")
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    require(completion.get("results_sha256") == expected_result_sha256
            and completion.get("passed") is True, "positive immutable completion")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("format") == "dem-json-document-reference-v1":
        require(callable(document_reader), "qualified original ancillary document reader")
        value = document_reader(path)
    require(value.get("passed") is True, "original receipt passed")
    merged = {}
    for key in ("artifacts", "source_files", "physical_inputs", "evidence_files"):
        for name, expected in value.get(key, {}).items():
            require(name not in merged or merged[name] == expected, "no conflicting original evidence pins")
            merged[name] = expected
    require(merged, "receipt declares consumed evidence")
    verify_mapping(merged)
    return value


def audit_branch_caps(record, before_checkpoint, case, ctx, *, cap_entries, target_time_s):
    """Replay original old-state assembly/selector for every actual substep.

    This lazy path uses the frozen original ASSEMBLE and independent selector
    inequality, without a contact solve or advancement. The original onset
    auditor's exact-dt predicate is deliberately NOT claimed to accept a new
    half-step: here actual requested dt must be no greater than its independently
    reconstructed selected upper bound. Original mechanics still audit raw rows.
    """
    import copy
    import numpy as np
    import reconstruct_fixed_pose_v3 as reconstruction
    import audit_onset_timecap_v1 as original_selector_audit

    api = reconstruction.s.api
    spec = case["spec"]
    require(record["spec"] == spec and record["input_checkpoint_sha256"] == api.digest(before_checkpoint),
            "literal original raw input and case")
    if before_checkpoint is not None:
        require(before_checkpoint["state_sha256"] == api.digest(before_checkpoint["state"]), "original FULL input state")
        old = copy.deepcopy(before_checkpoint["state"])
    else:
        initial = spec["initial_state"]
        old = dict(t=0., steps=0, x=copy.deepcopy(initial["position_m"]),
                   p=copy.deepcopy(initial["orientation"]), q=copy.deepcopy(initial["velocity_generalized"]))
    rows = record["rows"]
    state = record["result"]["checkpoint"]["state"]
    pending = state.get("pending_trial")
    require(isinstance(cap_entries, list) and len(cap_entries) == len(rows) + int(pending is not None),
            "all actual accepted and sole pending half/coarse substeps covered")
    require(len(record["sweep_certificates"]) == len(rows), "original sweep coverage")
    cfg = spec["config"]
    a, b, _ = cfg["prolate_semiaxes_m"]
    numerics = cfg["numerics"]
    geometry = ctx.geometry_for(case)
    enrich = reconstruction.ASSEMBLE.__globals__["enrich"]
    triggered = tightened = 0
    start = old["t"]
    require(type(target_time_s) in (int, float) and math.isfinite(target_time_s)
            and start < target_time_s <= spec["horizon_s"], "prospectively bound branch target")
    with ctx.job.prior.snapshot.scope(api, spec["field_metadata"]):
        field, _, metadata = api.fields.load(spec["seed"], spec["flow_factor"], spec["cpd"])
        require(metadata == spec["field_metadata"], "original immutable field")
        for index, entry in enumerate(cap_entries):
            t, steps = old["t"], old["steps"]
            x, p, q = [np.asarray(old[k], float) for k in ("x", "p", "q")]
            require(entry["time_s"] == t and entry["steps"] == steps
                    and entry["velocity_generalized"] == q.tolist(), "actual branch old state, not macro origin")
            operands = reconstruction.ASSEMBLE(
                field, geometry, x, p, q, a, b, cfg["dynamic_viscosity_Pa_s"],
                cfg["particle_density_kg_m3"], cfg["fluid_density_kg_m3"],
                cfg["gravity_m_s2"], cfg["friction_coefficient"], np.inf, t,
                cfg["added_mass_fraction"], .2, .01, numerics["displacement_fraction"],
                numerics["angle_limit_rad"], numerics["relaxation_fraction"],
                numerics["max_dt_s"], numerics["reynolds_limit"])
            full = float(operands[8])
            base = min(full, spec["horizon_s"] - t)
            near = original_selector_audit._plain_near(enrich(
                geometry, geometry.contacts(x, p, a, b, .2 * float(geometry.r.max()))))
            chosen, triggers = original_selector_audit._decision(
                base, full, near, q, a, cfg["target_mean_interstitial_velocity_m_s"],
                True, original_selector_audit.FROZEN_POLICY)
            require(entry["untruncated_dt_s"] == full and entry["base_dt_s"] == base
                    and entry["near"] == near and entry["original_selected_dt_s"] == chosen
                    and entry["trigger_grain_ids"] == triggers, "independent original cap/selector reconstruction")
            requested = entry["requested_dt_s"]
            require(type(requested) in (int, float) and math.isfinite(requested)
                    and requested > 0, "finite positive requested controller interval")
            actual = min(chosen, requested, target_time_s - t)
            require(actual > 0 and entry["actual_trial_dt_s"] == actual,
                    "actual half-state cap and branch target independently applied")
            if index == 0 and old.get("pending_trial") is not None:
                inherited = old["pending_trial"]
                require(inherited["attempt"] == 0 and inherited["time_s"] == t
                        and inherited["dt_s"] == actual, "literal inherited pending trial")
            triggered += bool(triggers)
            tightened += actual < chosen
            if index < len(rows):
                row = rows[index]
                require(record["sweep_certificates"][index]["dt_s"] == actual, "actual original force/sweep trial dt")
                accepted = row["dt_s"]
                require(0 < accepted <= actual and t + accepted == row["time_s"], "literal accepted clock")
                require(accepted == actual or (index == len(rows) - 1
                        and record["result"]["status"] == "full_window_exit"), "only original export truncates requested dt")
                old.update(t=row["time_s"], steps=steps + 1, x=row["position_m"],
                           p=row["orientation"], q=row["velocity_generalized"])
                old.pop("pending_trial", None)
            else:
                require(pending is not None and pending["attempt"] == 0 and pending["time_s"] == t
                        and pending["dt_s"] == actual and record["result"]["status"] == "incomplete_budget",
                        "sole uncommitted pending trial retained")
    require(all(state[k] == old[k] for k in ("t", "steps", "x", "p", "q")), "complete branch endpoint")
    return dict(passed=True, start_s=start, stop_s=state["t"], accepted_rows=len(rows),
                pending_witnesses=int(pending is not None), trigger_count=triggered,
                supplemental_tightened_rows=tightened, original_caps_reconstructed_at_each_state=True,
                original_mechanical_audit_replaced=False, native_force_solves=0, new_saved_steps=0)


def state_token(parent_token, state_header, appended_history_rows):
    """Compact logical ancestry token, explicitly NOT an original FULL digest."""
    require(is_sha(parent_token) and isinstance(state_header, dict)
            and "history" not in state_header and isinstance(appended_history_rows, list), "compact state and literal history delta")
    return digest(dict(kind="logical-state-history-token-not-full-checkpoint",
                       parent_token=parent_token, state_header=state_header,
                       appended_history_rows=appended_history_rows))


def history_node(parent_history_node, history_delta):
    require(is_sha(parent_history_node) and isinstance(history_delta, list), "literal compact history ancestry")
    return (digest(dict(parent_history_node=parent_history_node, history_delta=history_delta))
            if history_delta else parent_history_node)


def boundary_history_node(full_checkpoint, original_digest):
    history = full_checkpoint["state"]["history"]
    return digest(dict(boundary_full_checkpoint_sha256=original_digest(full_checkpoint),
                       history_sha256=digest(history), history_length=len(history)))


def reconstruct_original_cap(state, spec, field, geometry):
    """Force-free original assembly and independently selected cap at one state.

    Caller authenticates the supplied immutable field/geometry/spec and source
    mapping. Importing this module does not import this model dependency graph.
    """
    import numpy as np
    import reconstruct_fixed_pose_v3 as reconstruction
    import audit_onset_timecap_v1 as original_selector_audit
    cfg, numerics = spec["config"], spec["config"]["numerics"]
    a, b, _ = cfg["prolate_semiaxes_m"]
    x, p, q = [np.asarray(state[k], float) for k in ("x", "p", "q")]
    operands = reconstruction.ASSEMBLE(
        field, geometry, x, p, q, a, b, cfg["dynamic_viscosity_Pa_s"],
        cfg["particle_density_kg_m3"], cfg["fluid_density_kg_m3"],
        cfg["gravity_m_s2"], cfg["friction_coefficient"], np.inf, state["t"],
        cfg["added_mass_fraction"], .2, .01, numerics["displacement_fraction"],
        numerics["angle_limit_rad"], numerics["relaxation_fraction"],
        numerics["max_dt_s"], numerics["reynolds_limit"])
    full = float(operands[8])
    base = min(full, spec["horizon_s"] - state["t"])
    enrich = reconstruction.ASSEMBLE.__globals__["enrich"]
    near = original_selector_audit._plain_near(enrich(
        geometry, geometry.contacts(x, p, a, b, .2 * float(geometry.r.max()))))
    chosen, triggers = original_selector_audit._decision(
        base, full, near, q, a, cfg["target_mean_interstitial_velocity_m_s"],
        True, original_selector_audit.FROZEN_POLICY)
    return dict(time_s=state["t"], steps=state["steps"], velocity_generalized=q.tolist(),
                untruncated_dt_s=full, base_dt_s=base, near=near,
                original_selected_dt_s=chosen, trigger_grain_ids=triggers)


def audit_compact_branch_caps(branch, spec, field, geometry):
    """Actual-field replay for compact branch states, separate from mechanics."""
    old = dict(branch["before_state"])
    require(old.get("pending_trial") is None, "no original uncommitted physical trial in a positive branch")
    require(len(branch["rows"]) == len(branch["cap_entries"]) == len(branch["sweep_certificates"]), "complete branch cap and original sweep coverage")
    require(type(branch["target_time_s"]) in (int, float)
            and old["t"] < branch["target_time_s"] <= spec["horizon_s"], "frozen branch target")
    for index, (row, entry, sweep) in enumerate(zip(branch["rows"], branch["cap_entries"], branch["sweep_certificates"])):
        reference = reconstruct_original_cap(old, spec, field, geometry)
        require(all(entry[k] == v for k, v in reference.items()), "all original caps/geometry independently reconstructed at this half state")
        requested = branch["requested_dt_s"]
        require(type(requested) in (int, float) and math.isfinite(requested) and requested > 0
                and entry["requested_dt_s"] == requested and entry["target_time_s"] == branch["target_time_s"], "actual controller request and fixed target")
        trial = min(reference["original_selected_dt_s"], requested, branch["target_time_s"] - old["t"])
        require(0 < trial == entry["actual_trial_dt_s"] == sweep["dt_s"], "literal original force/sweep cap")
        require(0 < row["dt_s"] <= trial and old["t"] + row["dt_s"] == row["time_s"], "literal unshifted accepted interval")
        require(row["dt_s"] == trial or (index == len(branch["rows"]) - 1
                and branch["result_status"] == "full_window_exit"), "only original terminal export truncates a force trial")
        old.update(t=row["time_s"], steps=old["steps"] + 1, x=row["position_m"],
                   p=row["orientation"], q=row["velocity_generalized"])
    require(all(branch["after_state"][k] == old[k] for k in ("t", "steps", "x", "p", "q")), "actual compact branch endpoint")
    return dict(passed=True, caps_replayed=True, native_force_solves=0, new_saved_steps=0)


def independent_decision(limits, origin, coarse, first_half, second_half, *, h_s, selected_cap_s, depth):
    """Independent defect math on compact physical states, no fake FULL SHA.

    The caller must first authenticate raw histories and original mechanics.
    These dictionaries contain t,x,p,q and logical token/parent_token only.
    """
    scales = [limits[k] for k in ("speed_m_s", "position_defect_m", "director_defect", "velocity_defect_over_U", "minimum_h_s")]
    require(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in scales), "frozen positive finite scales")
    require(type(depth) is int and type(limits["maximum_halvings"]) is int
            and 0 <= depth <= limits["maximum_halvings"], "bounded halving depth")
    require(math.isfinite(h_s) and math.isfinite(selected_cap_s)
            and limits["minimum_h_s"] <= h_s <= selected_cap_s, "only original-cap tightening")
    for item in (origin, coarse, first_half, second_half):
        require(is_sha(item.get("token")) and is_sha(item.get("parent_token")), "explicit logical ancestry token")
        require(len(item["x"]) == len(item["p"]) == 3 and len(item["q"]) == 6
                and all(math.isfinite(v) for v in [item["t"], *item["x"], *item["p"], *item["q"]]), "finite full physical endpoint")
        require(abs(math.sqrt(math.fsum(v*v for v in item["p"])) - 1) <= 1e-10, "original unit director")
    middle, end = origin["t"] + h_s / 2, origin["t"] + h_s
    require(origin["t"] < middle < end and first_half["t"] == middle
            and coarse["t"] == second_half["t"] == end, "exact unshifted branch clocks")
    require(coarse["parent_token"] == first_half["parent_token"] == origin["token"]
            and second_half["parent_token"] == first_half["token"], "one literal origin and sequential half history")
    def delta(key):
        return math.sqrt(math.fsum((a-b)**2 for a, b in zip(coarse[key], second_half[key])))
    dx, dp, dq = delta("x"), delta("p"), delta("q") / limits["speed_m_s"]
    score = max(dx/limits["position_defect_m"], dp/limits["director_defect"], dq/limits["velocity_defect_over_U"])
    require(math.isfinite(score), "finite complete x,p,q discrepancy")
    if score <= 1:
        action, next_h, next_depth = "commit_literal_halves", h_s, depth
        committed = [first_half["token"], second_half["token"]]
    else:
        require(depth < limits["maximum_halvings"] and h_s / 2 >= limits["minimum_h_s"], "no forced acceptance at bounded minimum")
        action, next_h, next_depth, committed = "discard_all_and_halve", h_s/2, depth+1, []
    return dict(action=action, position_defect_m=dx, director_defect=dp,
                velocity_defect_over_U=dq, scaled_defect=score,
                next_h_s=next_h, next_halving_depth=next_depth, committed_tokens=committed)


def choose_clock_interval(time_s, selected_cap_s, minimum_h_s):
    """Final prospective endpoint-duration policy, never poststate alignment."""
    require(all(type(v) in (int, float) and math.isfinite(v) for v in (time_s, selected_cap_s, minimum_h_s))
            and selected_cap_s >= minimum_h_s > 0, "finite positive original cap and minimum")
    h = selected_cap_s
    end, middle = time_s + h, time_s + h / 2
    first, second = middle - time_s, end - middle
    tolerance = 2 * math.ulp(max(abs(time_s), abs(end)))
    require(time_s < middle < end and first > 0 and second > 0
            and abs(first-h/2) <= tolerance and abs(second-h/2) <= tolerance
            and abs(first-second) <= tolerance, "representable positive near-half endpoint durations before force")
    return dict(h_s=h, end_s=end, middle_s=middle, first_requested_dt_s=first,
                second_requested_dt_s=second, endpoint_roundoff_bound_s=tolerance)


def independent_trial_decision(limits, origin, branches, *, h_s, selected_cap_s, depth):
    """No defect is invented if a fresh half-state cap prevents common time."""
    ends = [_endpoint(v["after_state"], v["output_state_token"], v["input_state_token"]) for v in branches]
    wanted = [origin["t"]+h_s, origin["t"]+h_s/2, origin["t"]+h_s]
    if all(endpoint["t"] == target for endpoint, target in zip(ends, wanted)):
        return independent_decision(limits, origin, *ends, h_s=h_s, selected_cap_s=selected_cap_s, depth=depth)
    mismatch = []
    for branch, endpoint, target in zip(branches, ends, wanted):
        if endpoint["t"] != target:
            entry = branch["cap_entries"][0]
            require(endpoint["t"] < target and branch["result_status"] not in {"full_window_exit", "persistent_contact_dwell"}
                    and entry["actual_trial_dt_s"] == entry["original_selected_dt_s"]
                    and entry["original_selected_dt_s"] < min(branch["requested_dt_s"], target-branch["before_state"]["t"]),
                    "clock mismatch must be explained by independently replayed original half-state cap")
            mismatch.append(branch["branch_id"])
    require(mismatch and type(depth) is int and depth < limits["maximum_halvings"]
            and h_s/2 >= limits["minimum_h_s"], "cap mismatch exhausted bounded retries; never force acceptance")
    return dict(action="discard_all_and_halve", reason="cap_mismatch", position_defect_m=None,
                director_defect=None, velocity_defect_over_U=None, scaled_defect=None,
                next_h_s=h_s/2, next_halving_depth=depth+1, committed_tokens=[])


def audit_accounting(before, after, reservation, observed_rows, *, disposition):
    """Independently verify a single batch's known/negative/unknown charges."""
    keys = ("used_work_rows", "used_integration_records", "known_audited_rows",
            "known_unaccepted_rows", "unknown_reserved_rows")
    for ledger in (before, after):
        require(all(type(ledger[k]) is int and ledger[k] >= 0 for k in keys), "integer ledger counters")
        require(ledger["used_work_rows"] == sum(ledger[k] for k in keys[2:]), "literal work partition")
    require(isinstance(reservation, dict) and isinstance(reservation.get("record_id"), str)
            and reservation["record_id"] and type(reservation.get("maximum_rows")) is int
            and 0 < reservation["maximum_rows"] <= 5000, "one immutable aggregate reservation")
    require(before["reservation"] == reservation and after["reservation"] is None,
            "one reserved batch resolved exactly once")
    require(before["used_integration_records"] == after["used_integration_records"]
            and before["seen_record_ids"] == after["seen_record_ids"]
            and before["seen_record_ids"][-1] == reservation["record_id"], "actual one-batch call identity")
    require(disposition in {"audited", "known_unaccepted", "unknown"}, "explicit work classification")
    if disposition == "unknown":
        require(observed_rows is None, "known actual work cannot be relabelled unknown")
        charged, selected = reservation["maximum_rows"], "unknown_reserved_rows"
    else:
        require(type(observed_rows) is int and observed_rows >= 0, "known actual work count")
        charged = observed_rows
        selected = "known_audited_rows" if disposition == "audited" else "known_unaccepted_rows"
        require(disposition != "audited" or charged <= reservation["maximum_rows"], "overrun is never accepted")
    for key in keys[2:]:
        require(after[key] - before[key] == (charged if key == selected else 0), "no dropped or double-counted work")
    require(after["used_work_rows"] - before["used_work_rows"] == charged, "all shadow/half/partial rows charged")
    if disposition != "audited":
        require(isinstance(after.get("terminal_failure"), str) and after["terminal_failure"], "persistent negative even for zero rows")
    else:
        require(before.get("terminal_failure") is None and after.get("terminal_failure") is None, "no successor after unresolved failure")
    return dict(passed=True, classification=disposition, charged_rows=charged,
                observed_rows=observed_rows, actual_integration_records=1)


def _endpoint(state, token, parent):
    return dict(t=state["t"], x=state["x"], p=state["p"], q=state["q"], token=token, parent_token=parent)


def _physical_header(header):
    return {k: v for k, v in header.items() if k not in {"history", "history_node", "history_length"}}


def audit_packet(packet, limits, *, input_full_checkpoint, output_full_checkpoint,
                 original_digest, audit_branch, expected_input_state_token,
                 expected_policy_sha256, expected_previous_receipt_sha256=None,
                 initial_spec=None):
    """Compose literal branch stencils and COW history into FULL boundaries.

    ``audit_branch`` is an independently source-bound adapter that runs the
    ORIGINAL mechanical stencil functions and cap replay on a decoded branch.
    It must authenticate raw observations and exact original-history deltas.
    Synthetic callbacks test this composition only and cannot qualify native
    mechanics. The original FULL-per-record auditor is not misrepresented as
    accepting compact branch state: original FULL identities are checked here
    only at the two material packet boundaries.
    """
    require(packet.get("schema") == "paper1.full-state-stepdoubling.packet.v1", "packet schema")
    require(callable(original_digest) and callable(audit_branch), "explicit original digest/stencil adapters")
    require(packet["input_full_checkpoint_sha256"] == original_digest(input_full_checkpoint)
            and packet["output_full_checkpoint_sha256"] == original_digest(output_full_checkpoint), "actual original FULL boundary hashes")
    require(all(cp["state_sha256"] == original_digest(cp["state"]) for cp in (input_full_checkpoint, output_full_checkpoint) if cp is not None), "original FULL state digest gates")
    require(is_sha(expected_policy_sha256) and packet.get("policy_sha256") == expected_policy_sha256,
            "externally frozen supplemental policy binding")
    require((input_full_checkpoint is None or input_full_checkpoint["state"].get("pending_trial") is None)
            and output_full_checkpoint["state"].get("pending_trial") is None,
            "original physical pending remains separate from new controller cursor")
    input_header = packet["input_state"]
    if input_full_checkpoint is None:
        require(isinstance(initial_spec, dict) and input_header["t"] == 0. and input_header["steps"] == 0
                and input_header["x"] == initial_spec["initial_state"]["position_m"]
                and input_header["p"] == initial_spec["initial_state"]["orientation"]
                and input_header["q"] == initial_spec["initial_state"]["velocity_generalized"],
                "original fresh initialization; None is not a fabricated FULL checkpoint")
        initial_history = []
    else:
        require(_physical_header(input_header) == _physical_header(input_full_checkpoint["state"]), "literal initial full physical state")
        initial_history = input_full_checkpoint["state"]["history"]
    require(is_sha(expected_input_state_token) and packet["input_state_token"] == expected_input_state_token,
            "prior admitted logical input, bound separately to actual FULL state")
    require(input_header["history_length"] == len(initial_history)
            and is_sha(input_header["history_node"]), "FULL input history length and explicit COW node")
    states = {packet["input_state_token"]: input_header}
    branches, branch_by_id, callbacks = packet["work_branches"], {}, []
    carried = packet.get("carried_branches", [])
    require(isinstance(branches, list) and isinstance(carried, list) and (branches or carried), "all work/carried branches retained")
    current = packet["input_state_token"]
    committed = []
    carried_trial_ids = []
    if carried:
        phase = packet["cursor_before"].get("phase")
        expected_roles = {"after_coarse": ["C"], "after_first_half": ["C", "F1"],
                          "after_second_half": ["C", "F1", "F2"],
                          "after_decision": ["C", "F1", "F2"], "publish_second_half": ["C", "F1", "F2"]}
        require(phase in expected_roles and [v["role"] for v in carried] == expected_roles[phase]
                and is_sha(expected_previous_receipt_sha256), "exact prior staged branch set")
        if phase == "publish_second_half":
            # The already-audited pair remains a COMPLETE immutable fork in
            # the prior cursor.  F1 is already physical FULL; retain all three
            # witnesses, but publish ONLY the pending F2 without new work.
            cursor_before = packet["cursor_before"]
            origin = cursor_before["origin_state_token"]
            require(cursor_before["branch_ids"] == [v["branch_id"] for v in carried]
                    and cursor_before.get("published_half_count") == 1
                    and cursor_before.get("pending_branch_id") == carried[2]["branch_id"]
                    and carried[0]["input_state_token"] == carried[1]["input_state_token"] == origin
                    and carried[2]["input_state_token"] == carried[1]["output_state_token"] == current
                    and carried[1]["after_state"] == input_header,
                    "prior complete pair anchors exactly the already-published FULL F1")
            require(origin not in states or states[origin] == carried[0]["before_state"],
                    "no conflicting prior origin header")
            states[origin] = carried[0]["before_state"]
        for branch in carried:
            parent, token, bid = branch["input_state_token"], branch["output_state_token"], branch["branch_id"]
            require(branch["previous_packet_receipt_sha256"] == expected_previous_receipt_sha256
                    and parent in states and branch["before_state"] == states[parent]
                    and branch["history_parent"] == parent and token == state_token(
                        parent, branch["after_state"], branch["history_delta"])
                    and (token not in states or states[token] == branch["after_state"])
                    and bid not in branch_by_id, "literal previously charged staged branch")
            require(branch["after_state"]["history_node"] == history_node(
                        branch["before_state"]["history_node"], branch["history_delta"])
                    and branch["after_state"]["history_length"] == branch["before_state"]["history_length"] + len(branch["history_delta"]),
                    "carried literal history node/delta")
            proof = audit_branch(branch)
            require(proof.get("prior_admission_authenticated") is True and all(proof.get(k) is True for k in
                    ("stencil_verified", "caps_replayed", "history_delta_verified", "raw_observation_verified")),
                    "prior pending cursor and original evidence authenticated")
            states[token], branch_by_id[bid] = branch["after_state"], branch
            callbacks.append(proof)
            carried_trial_ids.append(bid)
        if phase == "publish_second_half":
            cursor_before = packet["cursor_before"]
            origin = cursor_before["origin_state_token"]
            h = cursor_before["h_s"]
            t = states[origin]["t"]
            wanted = [(h, t+h), ((t+h/2)-t, t+h/2), ((t+h)-(t+h/2), t+h)]
            require(all(v["work_rows"] == len(v["rows"]) == 1
                        and v["macro_index"] == cursor_before["macro_index"]
                        and v["requested_dt_s"] == request and v["target_time_s"] == target
                        for v, (request, target) in zip(carried, wanted))
                    and carried[0]["cap_entries"][0]["original_selected_dt_s"] == cursor_before["original_selected_cap_s"],
                    "prior pending pair retains literal requests, fresh cap and all original rows")
            choice = independent_trial_decision(limits, _endpoint(states[origin], origin, origin), carried,
                       h_s=h, selected_cap_s=cursor_before["original_selected_cap_s"], depth=cursor_before["depth"])
            require(choice["action"] == "commit_literal_halves" and cursor_before["decision"] == choice,
                    "pending F2 requires independently repeated original passed pair decision")
            current = carried[2]["output_state_token"]
            committed.append(carried[2]["branch_id"])
            carried_trial_ids = []
    all_work = 0
    for branch in branches:
        bid = branch["branch_id"]
        require(isinstance(bid, str) and bid and bid not in branch_by_id
                and branch["role"] in {"C", "F1", "F2"}, "unique original branch roles")
        parent, token = branch["input_state_token"], branch["output_state_token"]
        require(parent in states and branch["before_state"] == states[parent], "literal branch input state/history")
        require(branch["history_parent"] == parent
                and state_token(parent, branch["after_state"], branch["history_delta"]) == token
                and (token not in states or states[token] == branch["after_state"]),
                "compact state/history token, never a fake FULL digest; repeated identical states remain independently charged")
        require(branch["after_state"]["history_node"] == history_node(
                    branch["before_state"]["history_node"], branch["history_delta"])
                and branch["after_state"]["history_length"] == branch["before_state"]["history_length"] + len(branch["history_delta"]),
                "independent history-node/delta recombination")
        require(type(branch["work_rows"]) is int and branch["work_rows"] == len(branch["rows"])
                and branch["work_rows"] >= 0, "every actual branch row accounted")
        require(branch["after_state"]["steps"] - branch["before_state"]["steps"] == branch["work_rows"], "original cumulative physical step count")
        proof = audit_branch(branch)
        require(isinstance(proof, dict) and all(proof.get(k) is True for k in
                ("stencil_verified", "caps_replayed", "history_delta_verified", "raw_observation_verified")),
                "independent original mechanical/cap/history/raw adapter must pass")
        callbacks.append(proof)
        all_work += branch["work_rows"]
        branch_by_id[bid], states[token] = branch, branch["after_state"]
    consumed = []
    last_macro = last_trial = -1
    pending = None
    previous_choice = previous_trial = None
    for trial in packet["trials"]:
        require(type(trial["macro_index"]) is int and type(trial["trial_index"]) is int
                and (trial["macro_index"], trial["trial_index"]) > (last_macro, last_trial), "sequential macro/retry identities")
        last_macro, last_trial = trial["macro_index"], trial["trial_index"]
        if previous_choice is not None and previous_choice["action"] == "discard_all_and_halve":
            require(trial["macro_index"] == previous_trial["macro_index"]
                    and trial["trial_index"] == previous_trial["trial_index"] + 1
                    and trial["h_s"] == previous_choice["next_h_s"]
                    and trial["depth"] == previous_choice["next_halving_depth"], "literal bounded rejection retry")
        elif previous_trial is not None:
            require(trial["macro_index"] == previous_trial["macro_index"] + 1
                    and trial["trial_index"] == 0 and trial["depth"] == 0
                    and trial["h_s"] == choose_clock_interval(states[current]["t"], trial["original_selected_cap_s"], limits["minimum_h_s"])["h_s"],
                    "new origin resets to its independently reconstructed original cap; no nominal factor escalation")
        require(trial["origin_state_token"] == current, "retry or next macro uses last literal committed state")
        ids = trial["branch_ids"]
        require(isinstance(ids, list) and 1 <= len(ids) <= 3
                and all(bid in branch_by_id and bid not in consumed for bid in ids), "every branch has one trial association")
        these = [branch_by_id[bid] for bid in ids]
        require([v["role"] for v in these] == ["C", "F1", "F2"][:len(ids)]
                and all(v["macro_index"] == trial["macro_index"] for v in these), "ordered original coarse/half trial roles")
        require(all(v["work_rows"] == 1 for v in these), "literal one original step per C/F1/F2 stencil")
        origin_time = states[current]["t"]
        wanted = [(trial["h_s"], origin_time + trial["h_s"]),
                  ((origin_time + trial["h_s"]/2)-origin_time, origin_time + trial["h_s"]/2),
                  ((origin_time + trial["h_s"])-(origin_time + trial["h_s"]/2), origin_time + trial["h_s"])]
        require(all(branch["requested_dt_s"] == request and branch["target_time_s"] == target
                    for branch, (request, target) in zip(these, wanted)), "fixed literal coarse/half requests and unshifted target clocks")
        require(these[0]["cap_entries"][0]["original_selected_dt_s"] == trial["original_selected_cap_s"],
                "trial cap is independently reconstructed at its actual accepted origin")
        require(these[0]["input_state_token"] == current
                and (len(these) < 2 or these[1]["input_state_token"] == current)
                and (len(these) < 3 or these[2]["input_state_token"] == these[1]["output_state_token"]), "exact fork and half-chain ancestry")
        consumed.extend(ids)
        if len(ids) < 3 or trial["decision"] is None:
            require(trial is packet["trials"][-1] and trial["decision"] is None, "only final uncommitted trial may be partial")
            phase = {1: "after_coarse", 2: "after_first_half", 3: "after_second_half"}[len(ids)]
            pending = dict(origin_state_token=current, branch_ids=ids, phase=phase)
            continue
        origin = _endpoint(states[current], current, current)
        ends = [_endpoint(v["after_state"], v["output_state_token"], v["input_state_token"]) for v in these]
        choice = independent_trial_decision(limits, origin, these, h_s=trial["h_s"],
                                           selected_cap_s=trial["original_selected_cap_s"], depth=trial["depth"])
        require(trial["decision"] == choice, "independently repeated full-state defect and decision")
        previous_choice, previous_trial = choice, trial
        if choice["action"] == "commit_literal_halves":
            publish = trial.get("published_half_count", 2)
            require(type(publish) is int and publish in {1, 2}, "only decision-passed literal halves publish")
            if publish == 1:
                require(trial is packet["trials"][-1], "odd accepted-row interruption only at packet end")
                pending = dict(origin_state_token=trial["origin_state_token"], branch_ids=ids,
                               phase="publish_second_half", pending_branch_id=ids[2],
                               decision=choice, published_half_count=1)
            committed.extend(ids[1:1+publish])
            current = these[publish]["output_state_token"]
    require(consumed == carried_trial_ids + [v["branch_id"] for v in branches], "no omitted shadow/rejected/partial branch and exact work order")
    require(packet["committed_branch_ids"] == committed
            and packet["output_state_token"] == current, "no coarse shadow or staged F1 promotion")
    require(_physical_header(states[current]) == _physical_header(output_full_checkpoint["state"]), "literal last committed FULL physical state")
    history = list(initial_history)
    for bid in committed:
        history.extend(branch_by_id[bid]["history_delta"])
    require(history == output_full_checkpoint["state"]["history"], "lossless accepted-only FULL history recombination")
    cursor = packet["cursor_after"]
    if pending is None and previous_choice is not None and previous_choice["action"] == "discard_all_and_halve":
        pending = dict(phase="after_rejection", origin_state_token=current, branch_ids=[],
                       h_s=previous_choice["next_h_s"], depth=previous_choice["next_halving_depth"],
                       macro_index=previous_trial["macro_index"], trial_index=previous_trial["trial_index"]+1)
    require(cursor.get("phase") == (pending["phase"] if pending else "idle"), "explicit partial controller cursor")
    if pending:
        require(all(cursor.get(k) == v for k, v in pending.items()), "staged F1/coarse bound but not committed")
    if "all_work_rows" in packet["ledger_before"]:
        before, after = packet["ledger_before"], packet["ledger_after"]
        fields = ("all_work_rows", "accepted_half_rows", "rejected_trials")
        require(set(before) == set(after) == set(fields)
                and all(type(v) is int and v >= 0 for item in (before, after) for v in item.values()), "complete semantic numeric ledger")
        rejected = sum(t["decision"] is not None and t["decision"]["action"] == "discard_all_and_halve" for t in packet["trials"])
        accepted_count = sum(len(branch_by_id[bid]["rows"]) for bid in committed)
        require(after["all_work_rows"] - before["all_work_rows"] == all_work
                and after["accepted_half_rows"] - before["accepted_half_rows"] == accepted_count
                and after["rejected_trials"] - before["rejected_trials"] == rejected, "all actual packet work and fine publication charged exactly once")
        require(packet["work_rows"] == all_work
                and type(packet["reservation"]["maximum_work_rows"]) is int
                and all_work <= packet["reservation"]["maximum_work_rows"] <= 5000, "aggregate all-work packet admission")
        accounting = dict(passed=True, semantic_work_rows=all_work, accepted_half_rows=accepted_count,
                          rejected_trials=rejected, external_actual_call_and_case_shared_ledger_required=True)
    else:
        accounting = audit_accounting(packet["ledger_before"], packet["ledger_after"], packet["reservation"],
                                      all_work, disposition="audited")
    return dict(passed=True, composition_verified=True, all_work_rows=all_work,
                committed_branch_ids=committed, pending_controller_trial=pending is not None,
                first_accepted_selector_location=first_accepted_selector(packet),
                accounting=accounting, branch_audit_count=len(callbacks),
                original_entire_record_auditor_acceptance_claimed=False,
                original_mechanical_stencil_adapter_authentication_required=True,
                native_qualification_admitted=False, new_saved_steps=0, native_force_solves=0)


def first_accepted_selector(packet):
    """Earliest actual accepted half-row trigger; coarse shadows never count."""
    by_id = {item["branch_id"]: item for item in packet.get("carried_branches", []) + packet["work_branches"]}
    accepted_index = 0
    for bid in packet["committed_branch_ids"]:
        branch = by_id[bid]
        require(branch["role"] in {"F1", "F2"}, "first active lookup excludes coarse shadows")
        for index, entry in enumerate(branch["cap_entries"][:len(branch["rows"])]):
            if entry["trigger_grain_ids"]:
                return dict(branch_id=bid, branch_row_index=index, accepted_row_index=accepted_index)
            accepted_index += 1
    return None


def audit_history_delta(branch):
    """Independently repeat the original periodic accepted-history append."""
    after = branch["after_state"]
    require(branch["work_rows"] == len(branch["rows"]) == 1, "one original accepted step")
    terminal_before_append = branch["result_status"] in {"full_window_exit", "persistent_contact_dwell"}
    if after["steps"] % 250 == 0 and not terminal_before_append:
        expected = [[after["t"], *after["x"], *after["p"], *after["q"],
                     after["minimum_gap"], after["minimum_gap_ratio"], after["total_contact_iterations"]]]
    else:
        expected = []
    require(branch["history_delta"] == expected, "literal original history cadence and row contents")
    return dict(history_delta_verified=True)


def normalized_native_decision(decision, branch_ids, by_id):
    """Exact native/canonical schema bridge; no tolerance or field omission."""
    fields = ("action", "position_defect_m", "director_defect", "velocity_defect_over_U",
              "scaled_defect", "next_h_s", "next_halving_depth")
    require(isinstance(decision, dict) and set(decision) == set(fields) | {
                "witness_semantics", "committed_state_token"} | ({"reason"} if "reason" in decision else set())
            and decision["witness_semantics"] == "controller_state_token_not_original_FULL_sha",
            "complete exact native decision fields and honest token semantics")
    require(len(branch_ids) == 3 and [by_id[bid]["role"] for bid in branch_ids] == ["C", "F1", "F2"],
            "native decision belongs to complete retained original fork")
    require(decision["action"] in {"commit_literal_halves", "discard_all_and_halve"}, "known native decision action")
    commits = [by_id[bid]["output_state_token"] for bid in branch_ids[1:]] if decision["action"] == "commit_literal_halves" else []
    require(decision["committed_state_token"] == (commits[-1] if commits else None), "actual literal F2 decision reference")
    result = {key: decision[key] for key in fields}
    result["committed_tokens"] = commits
    if "reason" in decision:
        require(decision["reason"] == "cap_mismatch", "only prospectively specified supplemental mismatch reason")
        result["reason"] = decision["reason"]
    return result


def normalized_packet_view(packet):
    """Pure native-schema view; no force, replay, acceptance or authority."""
    view = dict(packet)
    view["input_full_checkpoint_sha256"] = packet.get("input_full_checkpoint_sha256", packet["original_FULL_input_sha256"])
    view["output_full_checkpoint_sha256"] = packet.get("output_full_checkpoint_sha256", packet["original_FULL_output_sha256"])
    view["input_state"] = packet["state_headers"][packet["input_state_token"]]
    by_id = {b["branch_id"]: b for b in packet.get("carried_branches", []) + packet["work_branches"]}
    for name in ("cursor_before", "cursor_after"):
        cursor = dict(packet[name])
        if cursor.get("decision") is not None:
            cursor["decision"] = normalized_native_decision(cursor["decision"], cursor["branch_ids"], by_id)
        view[name] = cursor
    view["trials"] = []
    for observed in packet["trials"]:
        trial = dict(observed)
        if trial["decision"] is not None:
            fine_ids = trial["branch_ids"][1:]
            trial["decision"] = normalized_native_decision(trial["decision"], trial["branch_ids"], by_id)
            if len(fine_ids) == 2 and fine_ids[0] in packet["committed_branch_ids"] and fine_ids[1] not in packet["committed_branch_ids"]:
                trial["published_half_count"] = 1
        view["trials"].append(trial)
    consumed = {bid for trial in view["trials"] for bid in trial["branch_ids"]}
    unassociated = [b for b in packet["work_branches"] if b["branch_id"] not in consumed]
    if unassociated:
        cursor = packet["cursor_after"]
        require(cursor["phase"] in {"after_coarse", "after_first_half", "after_second_half"}
                and all(b["branch_id"] in cursor["branch_ids"] for b in unassociated), "explicit final predecision cursor, never an invented decision")
        view["trials"].append(dict(macro_index=cursor["macro_index"], trial_index=cursor["trial_index"],
                                   depth=cursor["depth"], h_s=cursor["h_s"],
                                   original_selected_cap_s=cursor["original_selected_cap_s"],
                                   origin_state_token=cursor["origin_state_token"], branch_ids=cursor["branch_ids"], decision=None))
    return view


def audit_runtime_packet(packet, limits, *, checkpoint_before, checkpoint_after,
                         field, geometry, spec, binding, source_bindings,
                         mechanical_stencil_adapter, original_digest,
                         expected_policy_sha256, expected_previous_receipt_sha256=None):
    """Actual packet interface; model/force execution is never dispatched here.

    The required mechanical adapter is separately reviewed source that invokes
    the frozen ORIGINAL stencil functions on an explicitly labelled compact
    history projection. It exposes ``source_files`` and
    ``original_stencil_sources`` maps, freshly authenticated below. These maps
    and a callback are NOT by themselves native qualification: that remains an
    executed, separately closed gate under future authorization.
    """
    from dataclasses import asdict, is_dataclass
    require(callable(mechanical_stencil_adapter) and callable(original_digest), "source-bound original adapters")
    require(getattr(mechanical_stencil_adapter, "original_stencil_adapter_marker", None) is _ORIGINAL_STENCIL_ADAPTER_MARKER,
            "actual reviewed original mechanical factory; a mock cannot claim original stencil replay")
    require(isinstance(binding, str) and binding, "explicit original mechanical binding")
    verify_mapping(source_bindings)
    source_map = getattr(mechanical_stencil_adapter, "source_files", None)
    stencil_map = getattr(mechanical_stencil_adapter, "original_stencil_sources", None)
    require(isinstance(source_map, dict) and source_map and isinstance(stencil_map, dict)
            and stencil_map, "actual mechanical adapter and original stencil source associations")
    normalized = {str(Path(path).resolve()): value for path, value in source_bindings.items()}
    declared_stencils = {str(Path(path).resolve()): value for path, value in stencil_map.items()}
    require(all(declared_stencils.get(str((ROOT / relative).resolve())) == expected
                for relative, expected in REQUIRED_STENCIL_SOURCES.items()), "no original mechanical/normal/inner/cycle stencil omitted or substituted")
    for mapping in (source_map, stencil_map):
        require(all(normalized.get(str(Path(path).resolve())) == value for path, value in mapping.items()),
                "mechanical source association belongs to caller-frozen map")
        verify_mapping(mapping)
    values = asdict(limits) if is_dataclass(limits) else dict(limits)
    require(values.get("numerical_binding") == expected_policy_sha256
            and packet.get("policy_sha256") == expected_policy_sha256
            and packet.get("limits") == values, "frozen limits and policy cannot be changed after seeing errors")
    before_full = (None if checkpoint_before is None else checkpoint_before["physical_checkpoint"])
    after_full = checkpoint_after["physical_checkpoint"]
    require(packet["checkpoint"] == checkpoint_after, "actual native output envelope")
    require(checkpoint_after["published_state_token"] == packet["output_state_token"]
            and checkpoint_after["cursor"] == packet["cursor_after"]
            and checkpoint_after["numeric_ledger"] == packet["ledger_after"], "atomic FULL/controller/semantic ledger envelope")
    if checkpoint_before is not None:
        require(checkpoint_before["published_state_token"] == packet["input_state_token"]
                and checkpoint_before["cursor"] == packet["cursor_before"]
                and checkpoint_before["numeric_ledger"] == packet["ledger_before"], "authenticated previous restart envelope")
        if packet.get("carried_branches"):
            expected = checkpoint_before["pending_branches"]
            observed = [{key: value for key, value in branch.items()
                         if key != "previous_packet_receipt_sha256"} for branch in packet["carried_branches"]]
            require(observed == expected, "every carried source branch exactly equals authenticated prior controller envelope")
    require(packet.get("status") != "negative" and packet.get("error") is None,
            "negative raw output is preserved/accounted outside positive admission")
    view = normalized_packet_view(packet)
    def verify_branch(branch):
        proof = mechanical_stencil_adapter(branch, spec=spec, binding=binding,
                                           original_digest=original_digest)
        require(isinstance(proof, dict) and proof.get("stencil_verified") is True
                and proof.get("raw_observation_verified") is True, "all original mechanical predicates and raw association")
        audit_compact_branch_caps(branch, spec, field, geometry)
        audit_history_delta(branch)
        result = dict(proof, caps_replayed=True, history_delta_verified=True)
        if "previous_packet_receipt_sha256" in branch:
            require(proof.get("prior_admission_authenticated") is True, "prior staged branch receipt must be reauthenticated")
        return result
    summary = audit_packet(view, values, input_full_checkpoint=before_full,
                           output_full_checkpoint=after_full, original_digest=original_digest,
                           audit_branch=verify_branch, expected_input_state_token=packet["input_state_token"],
                           expected_policy_sha256=expected_policy_sha256,
                           expected_previous_receipt_sha256=expected_previous_receipt_sha256, initial_spec=spec)
    verify_mapping(source_bindings)
    return dict(summary, original_substep_mechanics_stencils_replayed=True,
                original_FULL_boundary_and_literal_history_checked=True,
                caller_frozen_source_maps_verified=True, native_restart_qualification_required=True)


def create_original_mechanical_adapter(spec, binding, geometry, design_sha256,
                                       gap_semantics, *, field=None,
                                       prior_receipt_authenticator=None):
    """Build the actual frozen mechanical-stencil bridge; never solve/advance.

    The temporary ``history=[]`` projection permits unchanged mechanical
    stencil functions to inspect a single disconnected shadow without hashing
    its growing FULL history. EVERY nonhistory physical state/monitor value,
    contract, observed force/cycle/geometry datum and threshold is preserved.
    This projection is explicitly NOT the original whole-record evidence
    contract; ``audit_runtime_packet`` independently recombines FULL histories.
    """
    import copy
    import reconstruct_fixed_pose_v3 as reconstruction
    q, api = reconstruction.s.q, reconstruction.s.api
    kernel = q.baseline.inner.__globals__["local"].auditor.kernel
    guard = q.guard.audit
    require(Path(kernel.__code__.co_filename).resolve() == (ROOT / "stage213_staging/audit_normal_gap_v1.py").resolve()
            and Path(guard.__code__.co_filename).resolve() == (ROOT / "stage243_staging/per_pose_guard_v1.py").resolve(),
            "actual live original normal-gap/mechanical and per-pose audit code objects")
    sources = {str((ROOT / relative).resolve()): expected for relative, expected in REQUIRED_STENCIL_SOURCES.items()}
    sources[str(Path(__file__).resolve())] = file_sha(__file__)
    # This immutable original policy JSON is constant for the scope.  Bind it
    # once, then let the packet facade freshly rehash the complete caller map
    # before/after replay; opening it for every C/F1/F2 row is unnecessary.
    numerical_contract_path = Path(q.job.WORK).resolve()
    numerical_contract_sha256 = api.sha(numerical_contract_path)
    sources[str(numerical_contract_path)] = numerical_contract_sha256
    verify_mapping(sources)
    require(is_sha(design_sha256) and isinstance(binding, str) and binding, "actual physical design/binding")
    # This is the same original metadata expectation used by Stage180; the
    # native generated checkpoint contract must correspond to this binding.
    # The actual delegated object is the later frozen composition. Its
    # original Stage180 model is reachable through the original module import.
    import audit_optimized_record_v1 as original_stencil
    effective = original_stencil.parent.model.binding_for(binding, True)
    expected_contract = original_stencil.parent.engine.prior.contracts.expected_contract(spec, effective)
    def audit_branch(branch, **scope):
        if scope:
            require(scope.get("spec", spec) == spec and scope.get("binding", binding) == binding,
                    "factory case/source scope cannot be replaced")
        require(branch.get("contract") == expected_contract, "original physical checkpoint contract, including enabled backend binding")
        before_state = copy.deepcopy(_physical_header(branch["before_state"]))
        after_state = copy.deepcopy(_physical_header(branch["after_state"]))
        require("history" not in before_state and "history" not in after_state
                and before_state.get("pending_trial") is None and after_state.get("pending_trial") is None,
                "complete physical header and original pending state remain unchanged")
        before_state["history"] = []
        after_state["history"] = copy.deepcopy(branch["history_delta"])
        before = dict(schema=1, contract=branch["contract"], state=before_state, state_sha256=api.digest(before_state))
        after = dict(schema=1, contract=branch["contract"], state=after_state, state_sha256=api.digest(after_state))
        result = copy.deepcopy(branch["compact_result"])
        result.update(checkpoint=after, history=copy.deepcopy(branch["history_delta"]),
                      stage119_repair_calls=copy.deepcopy(branch["stage119_repair_calls"]))
        require(result["status"] == branch["result_status"], "actual original branch result status")
        if "original_digest" in scope:
            require(scope["original_digest"](before) == api.digest(before)
                    and scope["original_digest"](after) == api.digest(after), "actual original API digest semantics")
        keys = ("rows", "sweep_certificates", "contact_trial_trace", "normal_gap_operand_policy",
                "early_attempts", "fallback_systems", "repairs", "certificates", "backend_calls")
        require(all(key in branch for key in keys), "all actual original observation and fallback telemetry retained")
        record = {key: copy.deepcopy(branch[key]) for key in keys}
        record.update(spec=spec, design_sha256=design_sha256, input_checkpoint_sha256=api.digest(before),
                      effective_binding=effective, minimum_gap_semantics=gap_semantics,
                      numerical_policy_contract_sha256=numerical_contract_sha256, step_cap=1, result=result)
        # kernel includes unchanged Stage180 physical/kinematic/terminal checks,
        # exact Stage189 association, and original Stage213 signed-gap policy.
        mechanical = kernel(record, spec, binding, before, geometry, design_sha256, gap_semantics)
        cycle = guard(record)
        require(mechanical.get("passed") is True and cycle.get("passed") is True,
                "all original mechanical and per-pose predicates must pass")
        proof = dict(stencil_verified=True, raw_observation_verified=True,
                     mechanical=mechanical, cycle=cycle,
                     compact_history_projection_explicit=True,
                     original_entire_record_evidence_contract_claimed=False,
                     native_force_solves=0, new_saved_steps=0)
        if "previous_packet_receipt_sha256" in branch:
            require(callable(prior_receipt_authenticator), "staged branch needs immutable previous admission authenticator")
            require(prior_receipt_authenticator(branch) is True, "prior source/raw/decision/cursor evidence authenticated")
            proof["prior_admission_authenticated"] = True
        return proof
    audit_branch.source_files = dict(sources)
    audit_branch.original_stencil_sources = {str((ROOT / relative).resolve()): expected for relative, expected in REQUIRED_STENCIL_SOURCES.items()}
    audit_branch.native_qualification_claimed = False
    audit_branch.original_stencil_adapter_marker = _ORIGINAL_STENCIL_ADAPTER_MARKER
    return audit_branch


def audit_original_smoke_record(record, spec, binding, geometry, design_sha256,
                                gap_semantics, field):
    """Fresh 32-row old-bit qualification's real original FULL-record audit.

    This is an executable future gate, not a native call. Its original cap
    predicate is independently replayed without falsely declaring the old
    one-insertion onset AST proof to cover the new administration compiler.
    The smoke caller must bind producer source proofs and exact native exits.
    """
    import reconstruct_fixed_pose_v3 as reconstruction
    q = reconstruction.s.q
    kernel = q.baseline.inner.__globals__["local"].auditor.kernel
    require(Path(kernel.__code__.co_filename).resolve() == (ROOT / "stage213_staging/audit_normal_gap_v1.py").resolve(), "actual original FULL mechanical auditor")
    mechanical = kernel(record, spec, binding, None, geometry, design_sha256, gap_semantics)
    cycle = q.guard.audit(record)
    require(mechanical.get("passed") is True and cycle.get("passed") is True, "all original physical/force/normal/cycle checks")
    entries = record.get("cap_entries", record.get("onset_timecap", {}).get("journal"))
    require(isinstance(entries, list) and len(entries) == len(record["rows"]) == 32
            and len(record["sweep_certificates"]) == 32, "exact fully observed original 32-row smoke")
    initial = spec["initial_state"]
    old = dict(t=0., steps=0, x=initial["position_m"], p=initial["orientation"], q=initial["velocity_generalized"])
    for row, proof, entry in zip(record["rows"], record["sweep_certificates"], entries):
        cap = reconstruct_original_cap(old, spec, field, geometry)
        for key, value in cap.items():
            observed = entry.get("selected_dt_s") if key == "original_selected_dt_s" and key not in entry else entry[key]
            require(observed == value, "smoke exact original selected cap and old-state operands")
        selected = cap["original_selected_dt_s"]
        require(proof["dt_s"] == selected and row["dt_s"] == selected
                and old["t"] + selected == row["time_s"], "old-bit smoke uses full original selected step without half/target substitution")
        old.update(t=row["time_s"], steps=old["steps"]+1, x=row["position_m"], p=row["orientation"], q=row["velocity_generalized"])
    state = record["result"]["checkpoint"]["state"]
    require(all(state[k] == old[k] for k in ("t", "steps", "x", "p", "q")), "fresh smoke full endpoint association")
    return dict(passed=True, accepted_rows=32, original_full_record_mechanical_audit=mechanical,
                original_per_pose_guard=cycle, original_caps_reconstructed_at_every_row=True,
                compact_history_projection_used=False, new_saved_steps=0, native_force_solves=0,
                native_execution_and_exact_comparison_receipts_required=True)


READINESS = dict(native_packet_adapter_bound=False, original_subrecord_audits_qualified=False,
                 native_restart_qualified=False, execution_authority=False, numerical_launch_ready=False)
