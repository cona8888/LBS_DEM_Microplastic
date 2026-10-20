"""Record the revised read-only WSL path probe without invoking YADE."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_environment_probe_02"
DISTRO = "Ubuntu"
CHECKS = [
    ("yade_executable", "-x", "/usr/bin/yade"),
    ("execution_config_readable", "-r", "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/stage26b_revision2_network_export_execution_v2.json"),
    ("network_exporter_readable", "-r", "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/export_stage26b_revision2_stage25_network_v1.py"),
    ("common_module_readable", "-r", "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/stage26b_revision2_prefilter_common_v1.py"),
    ("stage25_checkpoint_readable", "-r", "/mnt/c/MATDEM_MICROPLASTIC/stage25_runs/stage25a_pure_sand_mechanics_20260813/qualification_04/mu_0.60/load_bearing_state.yade.gz"),
]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable revised environment-probe output already exists")
    results = []
    for name, operator, path in CHECKS:
        completed = subprocess.run(
            ["wsl.exe", "-d", DISTRO, "--", "bash", "-lc", "test %s %s" % (operator, path)],
            capture_output=True, text=True, timeout=20, check=False,
        )
        results.append({
            "name": name, "operator": operator, "path_wsl": path,
            "passed": completed.returncode == 0, "return_code": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr,
        })
    passed = all(row["passed"] for row in results)
    probe = {
        "schema": "lbs.stage26b-revision2-network-export-environment-probe.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_revised_read_only_wsl_path_probe" if passed else "failed_revised_wsl_path_probe",
        "wsl_distribution": DISTRO,
        "yade_invoked": False,
        "checks": results,
        "probe_script_sha256": digest(Path(__file__)),
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "probe.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(probe, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": passed, "probe_sha256": digest(path)}, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
