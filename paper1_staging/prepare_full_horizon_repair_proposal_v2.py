"""Create-only schema repair of failed, preserved proposal preparation v1.

Only the actual peer-review result schema is consumed differently. No model,
numerical work, audit threshold, source binding or authority is introduced.
"""
from pathlib import Path
import ast
import hashlib
import json

SELF = Path(__file__).resolve()
BASE = SELF.with_name("prepare_full_horizon_repair_proposal_v1.py")
assert hashlib.sha256(BASE.read_bytes()).hexdigest() == "671ebc04b7272f33c9d0fe4d1c2685b0e0fbca28d6bab382124879f129d207e6"
tree = ast.parse(BASE.read_text(encoding="utf-8"))
old = ast.parse('assert review["passed"] and review["numerical_launch_ready"] is False').body[0]
new = ast.parse('assert review["pure_policy_review_passed"] and review["readiness"]["numerical_launch_ready"] is False').body[0]
matches = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)
           and ast.dump(n, include_attributes=False) == ast.dump(old, include_attributes=False)]
assert len(matches) == 1
matches[0].test = new.test
ast.fix_missing_locations(tree)
ns = dict(__file__=str(SELF), __name__="create_only_schema_repair")
exec(compile(tree, str(SELF)+"::one-review-schema-assertion", "exec"), ns)
negative = ns["DESIGN"] / "preparation_negative_01.json"
assert not (ns["DESIGN"] / "pure_controls_01.json").exists()
ns["commit"](negative, dict(
    schema="paper1.proposal-preparation.administrative-negative.v1",
    failed_source=ns["pin"](BASE), direct_root_tool_chunk="b7df36", actual_observed_exit_code=1,
    error="KeyError: passed; peer review uses pure_policy_review_passed and nested readiness.",
    artifact_writes_before_error=0, new_transport_steps=0, new_integration_calls=0,
    source_preserved=True, repair_source=ns["pin"](SELF),
    repair="Exactly one AST assertion consumes the actual peer-review schema; all original checks and proposal contents retained."))
original_commit = ns["commit"]


def commit(path, value):
    if Path(path).name == "proposal_01.json":
        value["administrative_preparation_negative"] = ns["pin"](negative)
        value["source_files"][str(BASE)] = ns["sha"](BASE)
        value["preparation_schema_repair"] = "v2 changes one peer-review schema assertion only; preserved v1 failed before artifact writes."
    return original_commit(path, value)


ns["commit"] = commit
ns["main"]()
