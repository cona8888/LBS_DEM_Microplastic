"""Create-only preparation schema adapter; preserves both failed preparers."""
from pathlib import Path
import ast
import hashlib
import json

SELF = Path(__file__).resolve()
BASE = SELF.with_name("prepare_full_horizon_repair_proposal_v1.py")
FAILED2 = SELF.with_name("prepare_full_horizon_repair_proposal_v2.py")
assert hashlib.sha256(BASE.read_bytes()).hexdigest() == "671ebc04b7272f33c9d0fe4d1c2685b0e0fbca28d6bab382124879f129d207e6"
original = ast.parse(BASE.read_text(encoding="utf-8"))
tree = ast.parse(BASE.read_text(encoding="utf-8"))
pairs = [
    ('assert review["passed"] and review["numerical_launch_ready"] is False',
     'assert review["pure_policy_review_passed"] and review["readiness"]["numerical_launch_ready"] is False'),
    ('verify(review["source_files"])',
     'verify({str(ROOT / p): expected for p, expected in review["source_sha256"].items()})')]
for before, after in pairs:
    old, new = ast.parse(before).body[0], ast.parse(after).body[0]
    matches = [n for n in ast.walk(tree)
               if ast.dump(n, include_attributes=False) == ast.dump(old, include_attributes=False)]
    assert len(matches) == 1
    if isinstance(old, ast.Assert):
        matches[0].test = new.test
    else:
        matches[0].value = new.value
ast.fix_missing_locations(tree)
ns = dict(__file__=str(SELF), __name__="create_only_two_field_schema_adapter")
exec(compile(tree, str(SELF)+"::two-review-schema-fields", "exec"), ns)
assert not (ns["DESIGN"] / "pure_controls_01.json").exists()
assert not (ns["DESIGN"] / "proposal_01.json").exists()
prior = ns["DESIGN"] / "preparation_negative_01.json"
assert ns["read"](prior)["repair_source"]["sha256"] == ns["sha"](FAILED2)
negative = ns["DESIGN"] / "preparation_negative_02.json"
ns["commit"](negative, dict(
    schema="paper1.proposal-preparation.administrative-negative.v2",
    failed_source=ns["pin"](FAILED2), direct_root_tool_chunk="396524", actual_observed_exit_code=1,
    error="KeyError: source_files; peer review uses source_sha256 with workspace-relative keys.",
    artifact_writes_before_error=[str(prior)], prior_negative=ns["pin"](prior),
    pure_control_or_proposal_writes_before_error=0, new_transport_steps=0, new_integration_calls=0,
    both_failed_sources_preserved=True, repair_source=ns["pin"](SELF),
    repair="Consume exactly the two actual peer-review schema fields; all mechanical, gate, budget and readiness checks retained."))
original_commit = ns["commit"]


def commit(path, value):
    if Path(path).name == "proposal_01.json":
        value["administrative_preparation_negatives"] = [ns["pin"](prior), ns["pin"](negative)]
        value["source_files"].update({str(BASE): ns["sha"](BASE), str(FAILED2): ns["sha"](FAILED2)})
        value["preparation_schema_repair"] = "v3 consumes exactly the two actual peer-review schema fields; failed v1/v2 and their observed nonnumerical errors are retained."
    return original_commit(path, value)


ns["commit"] = commit
ns["main"]()
