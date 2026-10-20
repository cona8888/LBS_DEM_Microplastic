#!/usr/bin/env python3
"""Correct only the frozen-runner authorization token for redesign 03."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rejected-config", type=Path, required=True)
    parser.add_argument("--integration-failure", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cfg, failure = load(args.rejected_config), load(args.integration_failure)
    assert sha(args.rejected_config) == failure["config_sha256"]
    assert failure["passed"] is True and failure["simulation_started"] is False
    assert failure["authority"]["status_contract_correction_authorized"] is True
    before = json.loads(json.dumps(cfg))
    cfg["status"] = "authorized_stage26o_clean_sand_wall_preparation_control"
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["redesign"]["integration_contract_correction"] = "Exact runner status token restored; no physics or acceptance field changed."
    cfg["sources"].update({
        "rejected_config": str(args.rejected_config.resolve()).replace("\\", "/"),
        "rejected_config_sha256": sha(args.rejected_config),
        "integration_failure": str(args.integration_failure.resolve()).replace("\\", "/"),
        "integration_failure_sha256": sha(args.integration_failure),
    })
    for section in ("sand", "walls", "initialization", "settling", "confinement", "gravity_removal", "final_hold", "acceptance", "authority"):
        assert cfg[section] == before[section]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    target = args.output_dir / "control_config.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(target), "config_sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
