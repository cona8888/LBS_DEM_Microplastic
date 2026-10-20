"""Dependency-free tests for the frozen Stage26c temporal contact gate."""

import csv
import json
from pathlib import Path

from stage26c_prefilter_common_v2 import known_negative_reproduced, temporal_contact_pass


GATES = {
    "required_blocks": 60,
    "terminal_window_blocks_inclusive": [51, 60],
    "transient_minimum_distinct_sand_contacts_per_fibre": 1,
    "transient_minimum_declared_anchor_contacts_per_fibre": 1,
    "terminal_minimum_distinct_sand_contacts_per_fibre": 2,
    "terminal_minimum_declared_anchor_contacts_per_fibre": 2,
    "maximum_isolated_fibre_count_at_every_block": 0,
}


def row(block, contacts, anchors=None):
    anchors = contacts if anchors is None else anchors
    return {
        "block": block,
        "distinct_sand_contacts_by_fibre": contacts,
        "declared_anchor_contacts_by_fibre": anchors,
        "isolated_fibre_count": sum(value == 0 for value in contacts),
    }


def historical_positive(path):
    rows = []
    with path.open(newline="") as stream:
        for raw in csv.DictReader(stream):
            contacts = json.loads(raw["contacted_sand_body_ids"])
            rows.append(row(int(raw["block"]), [len(contacts)], [len(contacts)]))
    return rows


def main():
    synthetic_pass = [row(block, [1] if block <= 50 else [2]) for block in range(1, 61)]
    assert temporal_contact_pass(synthetic_pass, GATES)
    early_isolation = list(synthetic_pass)
    early_isolation[10] = row(11, [0])
    assert not temporal_contact_pass(early_isolation, GATES)
    assert known_negative_reproduced(early_isolation)
    late_loss = list(synthetic_pass)
    late_loss[55] = row(56, [1])
    assert not temporal_contact_pass(late_loss, GATES)
    missing = synthetic_pass[:-1]
    assert not temporal_contact_pass(missing, GATES)
    history = historical_positive(
        Path(__file__).resolve().parents[1]
        / "stage26_runs/stage26a_dry_f37_insertion_20260813/qualification_03/conditioning_history.csv"
    )
    assert temporal_contact_pass(history, GATES)
    print("stage26c temporal gate v2 tests passed")


if __name__ == "__main__":
    main()
