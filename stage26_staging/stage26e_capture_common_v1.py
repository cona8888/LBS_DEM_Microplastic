"""Pure-Python event logic for Stage26e qualified-state capture."""

from stage26d_adaptive_common_v1 import row_equilibrium_pass


def advance_equilibrium_streak(streak, row, minimum_block, required_consecutive, gates):
    """Return the updated streak and a capture window, if completed on this row."""
    if row["block"] < minimum_block:
        return [], None
    updated = list(streak) + [row["block"]] if row_equilibrium_pass(row, gates) else []
    if len(updated) == required_consecutive:
        return updated, [updated[0], updated[-1]]
    if len(updated) > required_consecutive:
        raise RuntimeError("event runner continued after its frozen capture event")
    return updated, None
