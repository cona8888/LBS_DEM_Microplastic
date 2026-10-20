"""Patch only the verified helper-import defect in Stage26g runner v1."""

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--failure", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    failure_path = Path(args.failure).resolve()
    output = Path(args.output).resolve()
    manifest = Path(args.manifest).resolve()
    if output.exists() or manifest.exists():
        raise RuntimeError("immutable Stage26g runner-v2 artifact already exists")
    failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
    if failure.get("status") != "frozen_pre_execution_import_failure" or failure["runner_v1_sha256"] != digest(source):
        raise RuntimeError("runner-v1 failure binding mismatch")
    text = source.read_text(encoding="utf-8")
    old = "from stage26g_capture_common_v1 import advance_equilibrium_streak"
    new = "from stage26e_capture_common_v1 import advance_equilibrium_streak"
    if text.count(old) != 1:
        raise RuntimeError("unexpected Stage26g helper import count")
    text = text.replace(old, new)
    output.write_text(text, encoding="utf-8", newline="\n")
    record = {
        "schema": "lbs.stage26g-fixed-cage-runner-derivation.v2",
        "passed": True,
        "source_v1": str(source),
        "source_v1_sha256": digest(source),
        "failure_record": str(failure_path),
        "failure_record_sha256": digest(failure_path),
        "output_v2": str(output),
        "output_v2_sha256": digest(output),
        "single_change": {"old": old, "new": new},
        "builder_sha256": digest(Path(__file__)),
        "authority": {
            "fixed_fibre_execution_supported": True,
            "free_release_supported": False,
            "flow_supported": False
        }
    }
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"passed": True, "runner_v2_sha256": digest(output), "manifest_sha256": digest(manifest)}, sort_keys=True))


if __name__ == "__main__":
    main()
