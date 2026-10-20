"""Derive the held-out-capable Stage26e runner by an exact procedural patch."""

import hashlib
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
SOURCE = ROOT / "stage26_staging/run_stage26e_qualified_state_capture_v1.py"
OUTPUT = ROOT / "stage26_staging/run_stage26e_qualified_state_capture_v2.py"
EXPECTED_SOURCE = "5fb877785649b22bd402abfd40af69c8df04969a4490cf71676f2988bf7ab5f6"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    assert digest(SOURCE) == EXPECTED_SOURCE
    assert not OUTPUT.exists(), "refusing to overwrite held-out runner"
    text = SOURCE.read_text(encoding="utf-8")
    text = replace_once(text, '        "candidate07_heldout_execution_authorized",\n', "")
    text = replace_once(
        text,
        '    if trial is None or trial.get("stage26e_role") != "development_capture":\n'
        '        raise RuntimeError("trial is outside development capture authority")\n',
        '    if trial is None:\n'
        '        raise RuntimeError("trial is outside the frozen capture schedule")\n'
        '    role = trial.get("stage26e_role")\n'
        '    if role not in ("development_capture", "heldout_capture"):\n'
        '        raise RuntimeError("unexpected Stage26e evidence role")\n'
        '    if role == "heldout_capture" and cfg["authority"].get("candidate07_heldout_execution_authorized") is not True:\n'
        '        raise RuntimeError("held-out execution authority is false")\n'
        '    if role == "development_capture" and cfg["authority"].get("candidate07_heldout_execution_authorized") is True:\n'
        '        raise RuntimeError("development trial cannot use held-out authority")\n',
    )
    text = replace_once(
        text,
        '    if placement.get("passed") is not True or placement.get("record_type") != "development_capture":\n'
        '        raise RuntimeError("placement role mismatch")\n',
        '    if placement.get("passed") is not True or placement.get("record_type") != role:\n'
        '        raise RuntimeError("placement role mismatch")\n',
    )
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"{OUTPUT} {digest(OUTPUT)}")


if __name__ == "__main__":
    main()
