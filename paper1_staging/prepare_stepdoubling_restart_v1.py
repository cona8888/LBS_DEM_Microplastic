"""Pure restart qualification contract; never launches or advances a model.

These controls prepare comparisons. A positive native qualification requires
authenticated actual executions under a new authority; synthetic fixtures are
not native evidence. Logical state/history tokens are not FULL checkpoint SHAs.
"""
import copy
import hashlib
import json
import math


SCHEMA = "paper1.stepdoubling.restart-observation.v1"
ANCHORS = ("initial", "after_coarse", "after_first_half", "first_actual_selector", "window_handoff")


def require(value, message):
    if not value:
        raise ValueError("Step-doubling restart qualification: " + message)


def digest(value):
    def no_nan(item):
        if isinstance(item, float):
            require(not math.isnan(item), "NaN cannot replace an original infinity sentinel")
        elif isinstance(item, (list, tuple)):
            for child in item:
                no_nan(child)
        elif isinstance(item, dict):
            for child in item.values():
                no_nan(child)
    no_nan(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True,
                                    separators=(",", ":")).encode()).hexdigest()


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def matrix(policy_sha256, physical_design_sha256):
    """Return an inactive manifest consumed by the future bounded qualifier."""
    require(sha(policy_sha256) and sha(physical_design_sha256), "frozen policy and physical design")
    return dict(schema="paper1.stepdoubling.restart-plan.v1",
                policy_sha256=policy_sha256, physical_design_sha256=physical_design_sha256,
                anchors=list(ANCHORS),
                exact_comparisons=["all_trial_rows", "committed_rows", "cap_journal",
                                   "full_checkpoint", "controller_cursor", "pending_reservation"],
                all_duplicate_work_charged=True, first_actual_selector_required=True,
                synthetic_controls_are_native_evidence=False, native_execution_required=True,
                numerical_authority_created=False, numerical_launch_ready=False)


def prepare_restart_contract(runtime_metadata, physical_design_sha256):
    """Freeze the required native tests without asserting they were executed."""
    require(isinstance(runtime_metadata, dict) and sha(runtime_metadata.get("policy_sha256"))
            and sha(runtime_metadata.get("adapter_source_sha256")), "prospective runtime source/policy pins")
    result = matrix(runtime_metadata["policy_sha256"], physical_design_sha256)
    result.update(adapter_source_sha256=runtime_metadata["adapter_source_sha256"],
                  initial=dict(serial_accepted_half_rows=256, split_accepted_half_rows=[128, 128]),
                  first_active=dict(rule="largest even j>0 at or before first accepted-half trigger index",
                                    coarse_shadow_trigger_is_not_accepted_trigger=True,
                                    actual_trigger_must_be_in_successor=True,
                                    no_legal_even_split="fail closed; never choose a later easier event"),
                  between_branches=["after_coarse", "after_first_half"],
                  handoff=dict(same_full_physical_state=True, original_physical_pending_trial=None,
                               new_cursor_pending_separately_bound=True),
                  comparison_scope="Exact accepted/all-trial physics, raw history, semantic controller cursor and cap decisions; administrative record identities and actual integration-record counts are compared/accounted separately, never normalized into false equality.")
    return result


def first_active_split(accepted_cap_journal, serial_accepted_rows):
    """Select only from accepted F1/F2 rows, preserving the first actual event."""
    require(isinstance(accepted_cap_journal, list) and type(serial_accepted_rows) is int
            and serial_accepted_rows > 0 and serial_accepted_rows % 2 == 0
            and len(accepted_cap_journal) == serial_accepted_rows, "complete pair-boundary serial observation")
    require(all(item.get("role") in {"F1", "F2"} for item in accepted_cap_journal), "coarse shadows excluded from accepted event lookup")
    found = next((i for i, item in enumerate(accepted_cap_journal) if item.get("trigger_grain_ids")), None)
    require(found is not None, "actual first accepted selector required")
    split = 2 * (found // 2)
    require(0 < split < serial_accepted_rows and split <= found, "legal even boundary before first accepted trigger")
    require(not any(item.get("trigger_grain_ids") for item in accepted_cap_journal[:split])
            and any(item.get("trigger_grain_ids") for item in accepted_cap_journal[split:]), "first actual trigger lies in successor")
    return dict(N=serial_accepted_rows, j=split, successor_accepted_rows=serial_accepted_rows-split,
                first_accepted_trigger_index=found)


def observation(*, anchor, policy_sha256, physical_design_sha256,
                full_checkpoint, controller_cursor, pending_reservation,
                all_trial_rows, committed_rows, cap_journal, work_rows,
                original_digest,
                first_selector_location=None, accepted_journal_indices=None,
                actual_native_execution=False):
    """Capture caller-supplied actual objects without changing their values.

    Full checkpoint hashing is performed only at qualification interruption or
    packet boundaries, never once per physical trial. The future runner must
    bind this observation to closed native raw/source/execution evidence.
    """
    require(anchor in ANCHORS and sha(policy_sha256) and sha(physical_design_sha256), "anchor/bindings")
    require(type(actual_native_execution) is bool, "literal execution classification")
    require(type(work_rows) is int and work_rows >= 0, "all-work row count")
    require(all(isinstance(v, list) for v in (all_trial_rows, committed_rows, cap_journal)), "literal row lists")
    require(work_rows == len(all_trial_rows), "all shadow/half/rejected/partial work retained")
    require(isinstance(full_checkpoint, dict) and isinstance(controller_cursor, dict), "FULL checkpoint and controller cursor")
    require(callable(original_digest), "source-bound original FULL digest callback")
    state = full_checkpoint["state"]
    require(all(math.isfinite(v) for v in [state["t"], *state["x"], *state["p"], *state["q"]]), "finite physical state; original nonphysical infinity sentinels preserved")
    require(full_checkpoint["state"].get("pending_trial") is None,
            "original physical pending remains None; new pending cursor is separately bound")
    require(pending_reservation is None or isinstance(pending_reservation, dict), "literal pending reservation")
    if pending_reservation is None:
        semantic_pending = None
    else:
        # Exact administrative identity is authenticated/accounted separately on
        # each execution, since serial and split calls have different record IDs.
        require(isinstance(pending_reservation.get("record_id"), str) and pending_reservation["record_id"], "actual immutable reservation identity")
        semantic_pending = {k: v for k, v in pending_reservation.items() if k not in {"record_id", "integration_record_index", "window", "utc"}}
    if anchor == "first_actual_selector":
        require(isinstance(first_selector_location, dict)
                and type(first_selector_location.get("journal_index")) is int
                and 0 <= first_selector_location["journal_index"] < len(cap_journal), "first active journal location")
        require(isinstance(accepted_journal_indices, list) and accepted_journal_indices
                and all(type(i) is int and 0 <= i < len(cap_journal) for i in accepted_journal_indices)
                and accepted_journal_indices == sorted(set(accepted_journal_indices)), "literal accepted-row journal association")
        accepted = [cap_journal[i] for i in accepted_journal_indices]
        require(all(item.get("role") in {"F1", "F2"} for item in accepted), "coarse shadow cannot qualify accepted-trigger restart")
        index = first_selector_location["journal_index"]
        position = first_selector_location.get("accepted_row_index")
        require(type(position) is int and 0 <= position < len(accepted)
                and accepted_journal_indices[position] == index and bool(cap_journal[index].get("trigger_grain_ids"))
                and not any(x.get("trigger_grain_ids") for x in accepted[:position]),
                "first actual accepted trigger, never a shadow or later convenient state")
    result = dict(schema=SCHEMA, anchor=anchor, policy_sha256=policy_sha256,
                  physical_design_sha256=physical_design_sha256,
                  original_full_checkpoint_sha256=original_digest(full_checkpoint),
                  full_checkpoint_comparison_sha256=digest(full_checkpoint),
                  controller_cursor_sha256=digest(controller_cursor),
                  pending_reservation_semantics_sha256=digest(semantic_pending),
                  all_trial_rows_sha256=digest(all_trial_rows), committed_rows_sha256=digest(committed_rows),
                  cap_journal_sha256=digest(cap_journal), work_rows=work_rows,
                  first_selector_location=copy.deepcopy(first_selector_location),
                  accepted_journal_indices=copy.deepcopy(accepted_journal_indices),
                  actual_native_execution=actual_native_execution)
    # This is a supplementary comparison digest, not the original api.digest.
    result["full_checkpoint_digest_semantics"] = "original digest callback plus separately labelled compact comparison digest; original Infinity sentinels preserved"
    return result


def compare(serial, resumed, *, native=False):
    """Exact comparison only; no tolerances, clock alignment or missing fields.

    This function does not authenticate files/execution. Its result is native
    qualification evidence only after the caller authenticates both native
    executions, original FULL codecs/audits and source/authority bindings.
    """
    require(type(native) is bool, "explicit native comparison request")
    require(isinstance(serial, dict) and isinstance(resumed, dict)
            and serial.get("schema") == resumed.get("schema") == SCHEMA, "complete observation schemas")
    required = {"schema", "anchor", "policy_sha256", "physical_design_sha256",
                "original_full_checkpoint_sha256", "full_checkpoint_comparison_sha256", "controller_cursor_sha256", "pending_reservation_semantics_sha256",
                "all_trial_rows_sha256", "committed_rows_sha256", "cap_journal_sha256",
                "work_rows", "first_selector_location", "actual_native_execution",
                "accepted_journal_indices", "full_checkpoint_digest_semantics"}
    require(set(serial) == set(resumed) == required, "all restart comparison fields present")
    require(serial == resumed, "literal raw rows, FULL history, cursor, reservations and cap decisions")
    require(serial["anchor"] in ANCHORS, "declared interruption location")
    if native:
        require(serial["actual_native_execution"] is True, "synthetic observations cannot qualify native restart")
    return dict(passed=True, exact_comparison=True, anchor=serial["anchor"],
                native_observations_declared=native,
                external_execution_and_artifact_authentication_required=True,
                native_qualification_admitted=False, new_saved_steps=0, native_calls=0)


def require_complete_matrix(receipts, policy_sha256, physical_design_sha256):
    """Check a caller-authenticated native matrix, without granting authority."""
    require(isinstance(receipts, list) and len(receipts) == len(ANCHORS), "every interruption covered")
    by_anchor = {item.get("anchor"): item for item in receipts}
    require(set(by_anchor) == set(ANCHORS), "unique complete anchor coverage")
    for item in by_anchor.values():
        require(item.get("passed") is True and item.get("authenticated_native_execution") is True
                and item.get("policy_sha256") == policy_sha256
                and item.get("physical_design_sha256") == physical_design_sha256
                and sha(item.get("execution_receipt_sha256"))
                and sha(item.get("original_audits_receipt_sha256"))
                and sha(item.get("comparison_receipt_sha256")), "authenticated native receipts and exact source scope")
    return dict(coverage_complete=True, anchors=list(ANCHORS),
                requires_fresh_receipt_authentication=True, execution_authority=False)


def retained_history_control(full_checkpoint, *, original_digest, history_store_type,
                             state_token_function, reject_unqualified_checkpoint,
                             new_policy_binding, adapter_source_sha256):
    """Read-only real-size codec fixture, never checkpoint reuse or rebinding.

    Caller authenticates the old reference/payload/seal and closed receipt and
    supplies the original qualified document reader's result. This function
    only round-trips its literal existing history and tests a pure admission
    guard; it never constructs a runtime, integration field or contact solver.
    """
    require(callable(original_digest) and callable(history_store_type)
            and callable(state_token_function) and callable(reject_unqualified_checkpoint), "explicit pure codec/admission consumers")
    require(sha(new_policy_binding) and sha(adapter_source_sha256), "new source/policy distinct from old evidence")
    full_sha = original_digest(full_checkpoint)
    require(full_checkpoint["state_sha256"] == original_digest(full_checkpoint["state"]), "original complete state digest")
    history = full_checkpoint["state"]["history"]
    require(isinstance(history, list) and history, "retained nontrivial FULL history")
    store = history_store_type(history)
    cursor = store.start(full_sha)
    restored_history = store.materialize(cursor.node)
    require(restored_history == history, "literal retained original history roundtrip")
    state = dict(full_checkpoint["state"], history=restored_history)
    restored = dict(full_checkpoint, state=state, state_sha256=original_digest(state))
    require(original_digest(restored) == full_sha and restored == full_checkpoint, "entire original FULL physical/history identity")
    header = {k: v for k, v in state.items() if k != "history"}
    header.update(history_node=cursor.node, history_length=len(history))
    parent = digest(dict(kind="fixture-only-retained-history-not-a-restart", original_full_sha256=full_sha))
    token = state_token_function(parent, header, [])
    restored_header = json.loads(json.dumps(header, sort_keys=True, allow_nan=True))
    require(state_token_function(parent, restored_header, []) == token, "compact token/header JSON roundtrip")
    rejected = False
    try:
        reject_unqualified_checkpoint(full_checkpoint, new_policy_binding, adapter_source_sha256)
    except (RuntimeError, ValueError):
        rejected = True
    require(rejected, "old bare FULL checkpoint must fail new controller admission before factory/force execution")
    return dict(passed=True, scope="read-only retained history/physical FULL codec fixture only",
                retained_original_full_checkpoint_sha256=full_sha, history_length=len(history),
                history_sha256=digest(history), token_roundtrip=True, entire_original_full_unchanged=True,
                old_unqualified_checkpoint_rejected=True, prefix_credit_granted=False,
                contract_rebinding_performed=False, checkpoint_resumed=False,
                new_saved_steps=0, native_calls=0, mechanical_replay_performed=False,
                native_restart_qualification_admitted=False, numerical_authority_created=False)


READINESS = dict(native_restarts_executed=False, native_restart_qualified=False,
                 execution_authority=False, numerical_launch_ready=False)
