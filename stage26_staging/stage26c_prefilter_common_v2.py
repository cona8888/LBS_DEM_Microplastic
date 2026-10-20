"""Pure-Python temporal contact and terminal sand-health gates for Stage26c."""

from __future__ import print_function

from stage26b_revision2_prefilter_common_v1 import (
    all_finite,
    candidate_rank_key,
    iterative_core,
    load_json,
    sand_terminal_pass,
    sha256,
    windows_to_wsl,
    write_json_exclusive,
)


def temporal_contact_pass(history, gates):
    """Require engagement throughout and two-anchor persistence at the end."""
    if not history:
        return False
    start, end = [int(value) for value in gates["terminal_window_blocks_inclusive"]]
    rows_by_block = dict((int(row["block"]), row) for row in history)
    if sorted(rows_by_block) != list(range(1, int(gates["required_blocks"]) + 1)):
        return False
    for block in range(1, int(gates["required_blocks"]) + 1):
        row = rows_by_block[block]
        terminal = start <= block <= end
        minimum_contacts = int(
            gates["terminal_minimum_distinct_sand_contacts_per_fibre"]
            if terminal else gates["transient_minimum_distinct_sand_contacts_per_fibre"]
        )
        minimum_anchors = int(
            gates["terminal_minimum_declared_anchor_contacts_per_fibre"]
            if terminal else gates["transient_minimum_declared_anchor_contacts_per_fibre"]
        )
        if min(row["distinct_sand_contacts_by_fibre"]) < minimum_contacts:
            return False
        if min(row["declared_anchor_contacts_by_fibre"]) < minimum_anchors:
            return False
        if int(row["isolated_fibre_count"]) > int(gates["maximum_isolated_fibre_count_at_every_block"]):
            return False
    return True


def known_negative_reproduced(history):
    """The frozen negative control is reproduced when any fibre becomes isolated."""
    return bool(history) and any(
        int(row["isolated_fibre_count"]) > 0
        or min(row["distinct_sand_contacts_by_fibre"]) == 0
        for row in history
    )
