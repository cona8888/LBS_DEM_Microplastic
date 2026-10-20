"""Derive the Stage26g four-support fixed-fibre runner from frozen Stage26e."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def replace_required(text, old, new, count=None):
    occurrences = text.count(old)
    if occurrences == 0 or (count is not None and occurrences != count):
        raise RuntimeError("unexpected source occurrence count for %r: %d" % (old, occurrences))
    return text.replace(old, new), occurrences


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    manifest = Path(args.manifest).resolve()
    if output.exists() or manifest.exists():
        raise RuntimeError("immutable Stage26g derived runner or manifest already exists")
    text = source.read_text(encoding="utf-8")
    transformations = []
    for old, new, count in (
        ("STAGE26E_CAPTURE", "STAGE26G_CAGE", None),
        ("Stage26e", "Stage26g", None),
        ("stage26e", "stage26g", None),
        ("candidate07_heldout_execution_authorized", "heldout_execution_authorized", None),
        ("candidate08_execution_authorized", "legacy_revision3_candidate08_execution_authorized", None),
        ("anchor_sand_body_ids", "support_sand_body_ids", 1),
        ("declared_anchors", "declared_supports", None),
        ("anchor_counts", "support_counts", None),
        ("minimum_declared_anchor_contacts", "minimum_declared_support_contacts", None),
        ("declared_anchor_contacts", "declared_support_contacts", None),
        ("if not all(value == 2 for value in insertion[\"distinct_sand_contacts_by_fibre\"]):", "if not all(value == 4 for value in insertion[\"distinct_sand_contacts_by_fibre\"]):", 1),
        ("exact two-contact insertion failed", "exact four-support insertion failed", 1),
    ):
        text, occurrences = replace_required(text, old, new, count)
        transformations.append({"old": old, "new": new, "occurrences": occurrences})
    header = (
        '"""AUTO-DERIVED Stage26g fixed four-support cage runner.\n\n'
        "Derived mechanically from the frozen Stage26e runner; no free release or flow.\n"
        '"""\n\n'
    )
    original_doc_end = text.find('"""', 3)
    if not text.startswith('"""') or original_doc_end < 0:
        raise RuntimeError("source module docstring not found")
    text = header + text[original_doc_end + 3 :].lstrip("\r\n")
    output.write_text(text, encoding="utf-8", newline="\n")
    record = {
        "schema": "lbs.stage26g-fixed-cage-runner-derivation.v1",
        "passed": True,
        "source": str(source),
        "source_sha256": digest(source),
        "output": str(output),
        "output_sha256": digest(output),
        "builder": str(Path(__file__).resolve()),
        "builder_sha256": digest(Path(__file__)),
        "transformations": transformations,
        "authority": {
            "fixed_fibre_execution_supported": True,
            "free_release_supported": False,
            "flow_supported": False,
        },
    }
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"passed": True, "runner_sha256": digest(output), "manifest_sha256": digest(manifest)}, sort_keys=True))


if __name__ == "__main__":
    main()
