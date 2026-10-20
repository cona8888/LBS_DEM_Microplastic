"""Audit Stage26c schema adapter without executing YADE."""

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
SOURCE = ROOT / "stage26_staging/prepare_stage26c_prefilter_placements_v1.py"
OUTPUT = ROOT / "stage26_evaluations/stage26c_revision3_fixed_prefilter_20260816/normalizer_source_evaluation_01/evaluation.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


text = SOURCE.read_text(encoding="utf-8")
tree = ast.parse(text)
imports = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
checks = {
    "source_compiles": tree is not None,
    "no_yade_import": "yade" not in imports,
    "no_process_launcher": "subprocess" not in imports,
    "source_hashes_are_predeclared": all(value in text for value in ("d1092744", "b151af80", "7b574d43", "c6cadd8e")),
    "positive_wrapped_as_one_fibre": '"fibre_count": 1' in text and '"fibres": [fibre]' in text,
    "multifibre_residuals_derived_from_members": "max(float(row[\"initial_normal_force_residual_relative\"])" in text,
    "immutable_output_guard": "if OUTPUT.exists()" in text,
    "no_prefilter_execution_authority": '"prefilter_yade_execution_authorized": False' in text
}
passed = all(checks.values())
evaluation = {"schema": "lbs.stage26c-prefilter-normalizer-source-evaluation.v1", "passed": passed, "checks": checks, "failures": [k for k, v in checks.items() if not v], "source_sha256": digest(SOURCE), "authority": {"normalizer_execution_authorized": passed, "prefilter_yade_execution_authorized": False}}
OUTPUT.parent.mkdir(parents=True, exist_ok=False)
OUTPUT.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": passed, "evaluation_sha256": digest(OUTPUT)}, sort_keys=True))
if not passed:
    raise SystemExit(1)
